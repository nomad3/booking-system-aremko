"""API de publicaciones planificadas para aremko-cli (la cola de Angélica).

Auth: header X-API-KEY == settings.AUTOMATION_API_KEY (la key vive
server-side en el backend Go de aremko-cli, nunca en el navegador).
"""

import json
import logging
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PublicacionPlanificada

logger = logging.getLogger(__name__)

# Extensiones de imagen aceptadas en la Fase 2 (fotos/carruseles/historias).
_EXT_IMAGEN = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
_MAX_BYTES = 16 * 1024 * 1024  # 16 MB por archivo, mismo tope que la bandeja.

ESTADOS_VALIDOS = {choice[0] for choice in PublicacionPlanificada.ESTADO_CHOICES}


def _api_key_ok(request) -> bool:
    expected = getattr(settings, 'AUTOMATION_API_KEY', '') or ''
    provided = request.headers.get('X-API-KEY', '')
    return bool(expected) and provided == expected


def _serialize(p: PublicacionPlanificada) -> dict:
    return {
        'id': p.id,
        'semana_inicio': p.semana_inicio.isoformat(),
        'dia': p.dia.isoformat(),
        'canal': p.canal,
        'tipo': p.tipo,
        'pieza_key': p.pieza_key,
        'titulo': p.titulo,
        'copy_json': p.copy_json,
        'responsable': p.responsable,
        'tiempo_estimado': p.tiempo_estimado,
        'estado': p.estado,
        'material_urls': p.material_urls,
        'revision_veredicto': p.revision_veredicto,
        'revision_resumen': p.revision_resumen,
        'revision_json': p.revision_json,
        'revision_at': p.revision_at.isoformat() if p.revision_at else None,
        'notas_revision': p.notas_revision,
        'published_url': p.published_url,
        'metricas': p.metricas,
        'notas': p.notas,
        'updated_at': p.updated_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(['GET'])
def publicaciones_semana(request):
    """Lista las publicaciones de una semana (default: la semana en curso).

    Query params:
        semana: YYYY-MM-DD (cualquier día; se normaliza al lunes). Opcional.
    """
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    try:
        semana_param = (request.GET.get('semana') or '').strip()
        if semana_param:
            base = date.fromisoformat(semana_param)
        else:
            base = date.today()
        lunes = base - timedelta(days=base.weekday())

        qs = PublicacionPlanificada.objects.filter(semana_inicio=lunes).order_by('dia', 'id')
        items = [_serialize(p) for p in qs]
        return JsonResponse({
            'semana_inicio': lunes.isoformat(),
            'total': len(items),
            'publicaciones': items,
        })
    except ValueError:
        return JsonResponse({'error': 'Parámetro semana inválido (usar YYYY-MM-DD)'}, status=400)
    except Exception as exc:  # noqa: BLE001
        logger.error(f'publicaciones_semana: {exc}', exc_info=True)
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def publicacion_actualizar(request, pub_id: int):
    """Actualiza estado / notas / published_url de una publicación.

    Body JSON: {"estado": "...", "published_url": "...", "notas": "..."}
    (todos opcionales; solo se tocan los campos presentes).
    """
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
    if pub is None:
        return JsonResponse({'error': f'Publicación {pub_id} no existe'}, status=404)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body no es JSON válido'}, status=400)

    cambios = []
    estado = payload.get('estado')
    if estado is not None:
        if estado not in ESTADOS_VALIDOS:
            return JsonResponse(
                {'error': f'Estado inválido. Válidos: {sorted(ESTADOS_VALIDOS)}'}, status=400,
            )
        pub.estado = estado
        cambios.append('estado')

    if 'published_url' in payload:
        pub.published_url = (payload.get('published_url') or '')[:500]
        cambios.append('published_url')

    if 'notas' in payload:
        pub.notas = payload.get('notas') or ''
        cambios.append('notas')

    if not cambios:
        return JsonResponse({'error': 'Nada que actualizar (enviar estado, published_url o notas)'}, status=400)

    pub.save(update_fields=cambios + ['updated_at'])
    logger.info(f'publicacion_actualizar: #{pub_id} campos {cambios}')
    return JsonResponse({'success': True, 'publicacion': _serialize(pub)})


@csrf_exempt
@require_http_methods(['GET'])
def publicacion_detalle(request, pub_id: int):
    """Devuelve una publicación (para polling del estado de revisión)."""
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)
    pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
    if pub is None:
        return JsonResponse({'error': f'Publicación {pub_id} no existe'}, status=404)
    return JsonResponse({'success': True, 'publicacion': _serialize(pub)})


def _run_revision_background(pub_id: int):
    """Corre la revisión IA en un thread (la llamada al modelo tarda más que
    el timeout del cliente HTTP del backend Go — por eso va fire-and-forget y
    Angélica ve el resultado por polling)."""
    try:
        from .revision_service import revisar_material
        pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
        if pub is not None:
            revisar_material(pub)
    except Exception as exc:  # noqa: BLE001
        logger.error(f'_run_revision_background #{pub_id}: {exc}', exc_info=True)
        try:
            PublicacionPlanificada.objects.filter(id=pub_id).update(revision_veredicto='sin_revisar')
        except Exception:  # noqa: BLE001
            pass


@csrf_exempt
@require_http_methods(['POST'])
def publicacion_material(request, pub_id: int):
    """Recibe fotos (multipart, campo 'files'), las sube a Cloudinary, y dispara
    la revisión IA en background. Responde de inmediato con estado 'revisando'.
    """
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
    if pub is None:
        return JsonResponse({'error': f'Publicación {pub_id} no existe'}, status=404)

    archivos = request.FILES.getlist('files') or request.FILES.getlist('file')
    if not archivos:
        return JsonResponse({'error': 'No se recibió ningún archivo (campo "files")'}, status=400)

    try:
        from cloudinary_storage.storage import MediaCloudinaryStorage
        storage = MediaCloudinaryStorage()
    except Exception as exc:  # noqa: BLE001
        logger.error(f'publicacion_material: storage Cloudinary no disponible ({exc})')
        return JsonResponse({'error': 'Almacenamiento de imágenes no disponible'}, status=503)

    urls = list(pub.material_urls or [])
    for f in archivos:
        ext = ('.' + f.name.rsplit('.', 1)[-1].lower()) if '.' in f.name else ''
        if ext not in _EXT_IMAGEN:
            return JsonResponse(
                {'error': f'Formato no soportado: {f.name}. Solo imágenes ({", ".join(sorted(_EXT_IMAGEN))}).'},
                status=400,
            )
        if f.size and f.size > _MAX_BYTES:
            return JsonResponse({'error': f'{f.name} supera el máximo de 16 MB.'}, status=400)
        nombre = f'publicaciones/{pub.semana_inicio.isoformat()}/{uuid.uuid4().hex}{ext}'
        try:
            guardado = storage.save(nombre, f)
            urls.append(storage.url(guardado))
        except Exception as exc:  # noqa: BLE001
            logger.error(f'publicacion_material: falló subir {f.name} ({exc})')
            return JsonResponse({'error': f'No se pudo subir {f.name}'}, status=502)

    pub.material_urls = urls
    pub.revision_veredicto = 'revisando'
    pub.save(update_fields=['material_urls', 'revision_veredicto', 'updated_at'])

    from threading import Thread
    Thread(target=_run_revision_background, args=(pub.id,), daemon=True).start()

    return JsonResponse({'success': True, 'publicacion': _serialize(pub)})
