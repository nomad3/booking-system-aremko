"""API del Catálogo de Clips (H-070 §4) — para aremko-cli / scripts de semilla.

Auth: header `X-API-KEY == settings.AUTOMATION_API_KEY` (patrón marketing_briefs).

Endpoints:
  POST  /marketing/api/catalogo/ingesta/  — imagen → Cloudinary optimizada → IA propone
                                            taxonomía → devuelve DRAFT (sin persistir).
  POST  /marketing/api/catalogo/          — guarda confirmado (upsert idempotente por `archivo`).
  GET   /marketing/api/catalogo/          — lista con filtros.
  PATCH /marketing/api/catalogo/<id>/     — edita taxonomía / estado / keeper.
"""
import json
import logging
import os
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Clip
from . import tagging

logger = logging.getLogger(__name__)

_EXT_IMAGEN = {'.jpg', '.jpeg', '.png', '.webp'}
_MAX_BYTES = 16 * 1024 * 1024  # las masters pesadas NO deben llegar acá (se optimiza igual)


def _api_key_ok(request) -> bool:
    expected = getattr(settings, 'AUTOMATION_API_KEY', '') or ''
    provided = request.headers.get('X-API-KEY', '')
    return bool(expected) and provided == expected


def _subir_imagen_optimizada(f):
    """Sube a Cloudinary SOLO la versión optimizada (brief: `q_auto,f_auto,c_limit,w_1440`;
    el master pesado queda local). La transformación es INCOMING: lo almacenado ya
    queda ≤1440px con calidad auto → Cloudinary liviano."""
    import cloudinary
    import cloudinary.uploader

    if not cloudinary.config().cloud_name:
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
            api_key=os.environ.get('CLOUDINARY_API_KEY', ''),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET', ''),
            secure=True,
        )
    try:
        f.seek(0)
    except Exception:  # noqa: BLE001
        pass
    resp = cloudinary.uploader.upload(
        f,
        public_id=f'catalogo_clips/{uuid.uuid4().hex}',
        transformation=[{'width': 1440, 'crop': 'limit', 'quality': 'auto'}],
        resource_type='image',
    )
    url = resp.get('secure_url') or resp.get('url') or ''
    if not url:
        raise ValueError('Cloudinary no devolvió URL de la imagen subida')
    # Entrega optimizada: f_auto al servir (el asset almacenado ya viene limitado).
    url_servir = url.replace('/upload/', '/upload/f_auto,q_auto/') if '/upload/' in url else url
    return {'cloud_url': url_servir, 'width': resp.get('width'), 'height': resp.get('height'),
            'bytes': resp.get('bytes'), 'format': resp.get('format')}


def _orientacion(w, h):
    if not (w and h):
        return ''
    if abs(w - h) <= min(w, h) * 0.05:
        return 'cuadrada'
    return 'horizontal' if w > h else 'vertical'


@csrf_exempt
@require_http_methods(['POST'])
def catalogo_ingesta(request):
    """Imagen → Cloudinary optimizada → etiquetado IA → draft SIN persistir."""
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    f = request.FILES.get('imagen') or (list(request.FILES.values())[0] if request.FILES else None)
    if f is None:
        return JsonResponse({'error': "Falta el archivo (campo multipart 'imagen')."}, status=400)
    ext = os.path.splitext(f.name or '')[1].lower()
    if ext not in _EXT_IMAGEN:
        return JsonResponse(
            {'error': f'Formato no soportado: {f.name}. Solo {", ".join(sorted(_EXT_IMAGEN))} (Fase A es foto).'},
            status=400)
    if f.size and f.size > _MAX_BYTES:
        return JsonResponse({'error': f'{f.name} supera 16 MB — sube una versión optimizada, no el master.'},
                            status=400)

    try:
        subida = _subir_imagen_optimizada(f)
    except Exception as exc:  # noqa: BLE001
        logger.error('catalogo_ingesta: falló subir %s (%s)', f.name, exc)
        return JsonResponse({'error': f'No se pudo subir {f.name} a Cloudinary'}, status=502)

    draft = tagging.etiquetar_imagen(subida['cloud_url'])
    if not draft.get('orientacion'):
        draft['orientacion'] = _orientacion(subida.get('width'), subida.get('height'))

    return JsonResponse({
        'archivo': f.name,
        'cloud_url': subida['cloud_url'],
        'width': subida.get('width'), 'height': subida.get('height'),
        'draft': draft,          # borrador propuesto por la IA — el operador confirma/corrige
        'persistido': False,     # explícito: la ingesta NO guarda
    })


# Campos aceptados al guardar/editar (el resto se ignora — defensa de shape).
_CAMPOS_TEXTO = {'archivo': 255, 'cloud_url': 500, 'nombre_comercial': 100, 'descripcion': 300,
                 'orientacion': 12, 'fuente': 30, 'origen': 120, 'nota': 10000}
_CAMPOS_CHOICE = {
    'tipo': {'foto', 'video'},
    'area': tagging.AREAS,
    'momento': tagging.MOMENTOS,
    'estacion': tagging.ESTACIONES,
    'vapor': {'no', 'sí', 'sí (IA)'},   # el operador SÍ puede marcar 'sí (IA)'
    'decoracion': tagging.DECORACION,
    'permiso': tagging.PERMISOS,
    'calidad': tagging.CALIDADES,
    'estado': tagging.ESTADOS,
}
_CAMPOS_BOOL = {'personas', 'keeper'}
_CAMPOS_LISTA = {'etiquetas', 'apto_para'}


def _validar_payload(data, parcial=False):
    """dict del cliente → (campos_limpios, error). Valida choices/largos/tipos."""
    limpio = {}
    for campo, largo in _CAMPOS_TEXTO.items():
        if campo in data:
            limpio[campo] = str(data[campo] or '').strip()[:largo]
    for campo, permitidos in _CAMPOS_CHOICE.items():
        if campo in data:
            v = str(data[campo] or '').strip()
            if campo == 'decoracion' and v == '':
                limpio[campo] = ''
                continue
            if v not in permitidos:
                return None, f'{campo} inválido: {v!r} (permitidos: {sorted(permitidos)})'
            limpio[campo] = v
    for campo in _CAMPOS_BOOL:
        if campo in data:
            limpio[campo] = bool(data[campo])
    for campo in _CAMPOS_LISTA:
        if campo in data:
            if not isinstance(data[campo], list):
                return None, f'{campo} debe ser lista'
            limpio[campo] = [str(x).strip()[:60] for x in data[campo][:20] if str(x).strip()]
    if 'atributos' in data:
        if not isinstance(data['atributos'], dict):
            return None, 'atributos debe ser objeto'
        limpio['atributos'] = data['atributos']
    if not parcial:
        if not limpio.get('archivo'):
            return None, 'archivo es obligatorio'
        if not limpio.get('cloud_url'):
            return None, 'cloud_url es obligatorio (la imagen ya debe estar en Cloudinary)'
        if 'area' not in limpio:
            return None, 'area es obligatoria'
    return limpio, None


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def catalogo_lista(request):
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    if request.method == 'POST':
        # Guardar CONFIRMADO (la taxonomía ya la ajustó el operador). Idempotente:
        # upsert por `archivo` — la semilla local→nube puede correr N veces.
        try:
            data = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Body JSON inválido'}, status=400)
        limpio, err = _validar_payload(data, parcial=False)
        if err:
            return JsonResponse({'error': err}, status=400)
        limpio.setdefault('fuente', 'ingesta_api')
        archivo = limpio.pop('archivo')
        clip, creado = Clip.objects.update_or_create(archivo=archivo, defaults=limpio)
        return JsonResponse({'clip': clip.to_dict(), 'creado': creado},
                            status=201 if creado else 200)

    # GET — explorar el catálogo (para el front de aremko-cli).
    qs = Clip.objects.all()
    p = request.GET
    if p.get('area'):
        qs = qs.filter(area=p['area'])
    if p.get('nombre_comercial'):
        qs = qs.filter(nombre_comercial__icontains=p['nombre_comercial'])
    if p.get('keeper') in ('true', '1'):
        qs = qs.filter(keeper=True)
    elif p.get('keeper') in ('false', '0'):
        qs = qs.filter(keeper=False)
    if p.get('vapor'):
        qs = qs.filter(vapor=p['vapor'])
    if p.get('momento'):
        qs = qs.filter(momento=p['momento'])
    if p.get('estado'):
        qs = qs.filter(estado=p['estado'])
    if p.get('tipo'):
        qs = qs.filter(tipo=p['tipo'])
    if p.get('apto_para'):
        qs = qs.filter(apto_para__contains=[p['apto_para']])
    if p.get('q'):
        from django.db.models import Q
        q = p['q']
        qs = qs.filter(Q(archivo__icontains=q) | Q(nombre_comercial__icontains=q) |
                       Q(descripcion__icontains=q) | Q(nota__icontains=q))
    try:
        limit = min(max(int(p.get('limit', 100)), 1), 500)
        offset = max(int(p.get('offset', 0)), 0)
    except (TypeError, ValueError):
        limit, offset = 100, 0
    total = qs.count()
    clips = [c.to_dict() for c in qs[offset:offset + limit]]
    return JsonResponse({'total': total, 'limit': limit, 'offset': offset, 'clips': clips})


@csrf_exempt
@require_http_methods(['PATCH'])
def catalogo_detalle(request, clip_id):
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)
    clip = Clip.objects.filter(id=clip_id).first()
    if clip is None:
        return JsonResponse({'error': f'Clip {clip_id} no existe'}, status=404)
    try:
        data = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)
    limpio, err = _validar_payload(data, parcial=True)
    if err:
        return JsonResponse({'error': err}, status=400)
    if not limpio:
        return JsonResponse({'error': 'Nada que actualizar'}, status=400)
    limpio.pop('archivo', None)  # la clave de upsert no se edita por PATCH
    for campo, valor in limpio.items():
        setattr(clip, campo, valor)
    clip.save()
    return JsonResponse({'clip': clip.to_dict()})
