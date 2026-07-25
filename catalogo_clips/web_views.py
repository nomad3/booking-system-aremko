"""Explorador web del Catálogo de Clips (H-071, Fase B1) — para el CM (Angélica).

Pantalla Django server-rendered, protegida con @staff_member_required (staff, NO
superuser): ver / filtrar / buscar el catálogo con miniaturas Cloudinary chicas.
SOLO lectura — la edición vive en el admin + PATCH API; el render llega en B2.

Consulta el ORM directo (mismo proyecto). La API REST de H-070 sigue intacta
para consumidores externos y el auto-pick futuro (B3).
"""
import logging
import os

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect, render

from .api_views import (_validar_payload, _subir_imagen_optimizada, _orientacion,
                        _EXT_IMAGEN, _MAX_BYTES)
from .composer import receta_normalizada, url_historia, PRESETS, POSICIONES
from .models import Clip
from .tagging import etiquetar_imagen

logger = logging.getLogger(__name__)

# Miniatura del grid: chica y recortada 4:5 (NO servir la de 1440 en el grid).
THUMB_TRANSF = 'w_400,c_fill,ar_4:5,q_auto,f_auto'


def thumb_url(cloud_url, transf=THUMB_TRANSF):
    """Deriva la miniatura insertando la transformación tras /upload/.

    Si la URL ya trae una transformación (ej. las de la ingesta llevan
    `f_auto,q_auto`), queda ENCADENADA — válido en Cloudinary."""
    if not cloud_url or '/upload/' not in cloud_url:
        return cloud_url or ''
    return cloud_url.replace('/upload/', f'/upload/{transf}/', 1)


_MOMENTO_ICONO = {'noche': '🌙', 'atardecer': '🌅', 'dia': '☀️'}


def _card(clip):
    return {
        'id': clip.id,
        'thumb': thumb_url(clip.cloud_url),
        'area': clip.get_area_display(),
        'nombre': clip.nombre_comercial,
        'keeper': clip.keeper,
        'vapor': clip.vapor.startswith('sí'),
        'momento_icono': _MOMENTO_ICONO.get(clip.momento, ''),
        'decorada': clip.decoracion == 'con',
        'revisar': clip.estado == 'revisar',
        'descartado': clip.estado == 'descartado',
        'archivo': clip.archivo,
    }


def _filtrar(qs, p):
    """querystring → queryset (server-side). Mismos filtros del brief §3."""
    if p.get('area'):
        qs = qs.filter(area=p['area'])
    if p.get('nombre_comercial'):
        qs = qs.filter(nombre_comercial=p['nombre_comercial'])
    if p.get('momento'):
        qs = qs.filter(momento=p['momento'])
    if p.get('estacion'):
        qs = qs.filter(estacion=p['estacion'])
    if p.get('vapor') == 'si':
        qs = qs.filter(vapor__in=['sí', 'sí (IA)'])
    elif p.get('vapor') == 'no':
        qs = qs.filter(vapor='no')
    if p.get('decoracion') in ('con', 'sin'):
        qs = qs.filter(decoracion=p['decoracion'])
    if p.get('keeper') == '1':
        qs = qs.filter(keeper=True)
    if p.get('estado'):
        qs = qs.filter(estado=p['estado'])
    if p.get('q'):
        q = p['q'].strip()
        qs = qs.filter(Q(archivo__icontains=q) | Q(nombre_comercial__icontains=q) |
                       Q(descripcion__icontains=q) | Q(nota__icontains=q) |
                       Q(etiquetas__icontains=q))
    return qs


@staff_member_required
def explorador(request):
    p = request.GET
    qs = Clip.objects.all()
    # Vista inicial: sin descartadas (toggle "ver todas"). Un filtro explícito de
    # estado manda sobre el default.
    if p.get('todas') != '1' and not p.get('estado'):
        qs = qs.exclude(estado='descartado')
    qs = _filtrar(qs, p)

    total = qs.count()
    por_area = {r['area']: r['n'] for r in qs.values('area').annotate(n=Count('id'))}
    resumen = ' · '.join(
        f'{n} {dict(Clip.AREAS).get(a, a)}' for a, n in
        sorted(por_area.items(), key=lambda kv: -kv[1]))

    paginator = Paginator(qs, 48)
    page = paginator.get_page(p.get('page') or 1)

    # Dropdowns desde la taxonomía real (areas/nombres presentes en la BD).
    areas_db = (Clip.objects.values_list('area', flat=True).distinct())
    areas = [(a, dict(Clip.AREAS).get(a, a)) for a in sorted(set(areas_db))]
    nombres = list(Clip.objects.exclude(nombre_comercial='')
                   .values_list('nombre_comercial', flat=True)
                   .distinct().order_by('nombre_comercial'))

    # Querystring sin `page` para que la paginación conserve los filtros.
    qd = request.GET.copy()
    qd.pop('page', None)
    qs_sin_page = qd.urlencode()

    return render(request, 'catalogo_clips/explorador.html', {
        'cards': [_card(c) for c in page.object_list],
        'page': page,
        'total': total,
        'resumen': resumen,
        'areas': areas,
        'nombres': nombres,
        'momentos': Clip.MOMENTOS,
        'estaciones': Clip.ESTACIONES,
        'estados': Clip.ESTADOS,
        'f': {k: p.get(k, '') for k in ('area', 'nombre_comercial', 'momento', 'estacion',
                                        'vapor', 'decoracion', 'keeper', 'estado', 'q', 'todas')},
        'qs_sin_page': qs_sin_page,
    })


# ---------------------------------------------------------------------------
# Ingesta web (B1.5) — Angélica sube la foto desde el navegador, la IA propone
# la taxonomía y ella confirma con botones. Reusa el MISMO motor de H-070
# (_subir_imagen_optimizada + etiquetar_imagen), sin pasar por la API X-API-KEY:
# acá la auth es la sesión staff.
# ---------------------------------------------------------------------------

APTO_PARA_OPCIONES = ['hero', 'blog', 'instagram_feed', 'historia', 'gbp', 'ads']


def _ctx_confirmar(draft, archivo, cloud_url, error=''):
    """Contexto de la fase 'confirmar' (draft nuevo de la IA o re-render tras error)."""
    return {
        'modo': 'confirmar',
        'draft': draft,
        'archivo': archivo,
        'cloud_url': cloud_url,
        'thumb': thumb_url(cloud_url),
        'areas': Clip.AREAS,
        'momentos': Clip.MOMENTOS,
        'estaciones': Clip.ESTACIONES,
        'vapores': Clip.VAPOR,
        'permisos': Clip.PERMISOS,
        'calidades': Clip.CALIDADES,
        'apto_opciones': APTO_PARA_OPCIONES,
        'nombres': list(Clip.objects.exclude(nombre_comercial='')
                        .values_list('nombre_comercial', flat=True)
                        .distinct().order_by('nombre_comercial')),
        'error': error,
    }


def _draft_desde_post(p):
    """Reconstruye el draft desde el form (para guardar o re-render tras error)."""
    return {
        'area': p.get('area', ''),
        'nombre_comercial': p.get('nombre_comercial', '').strip(),
        'momento': p.get('momento', 'indistinto'),
        'estacion': p.get('estacion', 'indistinto'),
        'vapor': p.get('vapor', 'no'),
        'decoracion': p.get('decoracion', ''),
        'personas': p.get('personas') == '1',
        'permiso': p.get('permiso', 'libre'),
        'calidad': p.get('calidad', 'media'),
        'keeper': p.get('keeper') == '1',
        'descripcion': p.get('descripcion', '').strip(),
        'orientacion': p.get('orientacion', ''),
        'estado': p.get('estado', 'ok'),
        'etiquetas': [t.strip() for t in (p.get('etiquetas') or '').split(',') if t.strip()],
        'apto_para': p.getlist('apto_para'),
    }


@staff_member_required
def ingesta_web(request):
    """Fase 1 (GET): form de subida. Fase 2 (POST con foto): Cloudinary + draft IA."""
    if request.method != 'POST':
        return render(request, 'catalogo_clips/ingesta.html', {'modo': 'subir'})

    f = request.FILES.get('imagen')
    if f is None:
        return render(request, 'catalogo_clips/ingesta.html',
                      {'modo': 'subir', 'error': 'Elige una foto primero.'})
    ext = os.path.splitext(f.name or '')[1].lower()
    if ext not in _EXT_IMAGEN:
        msg = f'Formato no soportado ({ext or "sin extensión"}). Usa JPG, PNG o WEBP.'
        if ext == '.heic':
            msg += ' Tip: al subirla desde Safari del iPhone se convierte sola a JPG; si llegó como HEIC, reintenta eligiéndola desde Fotos.'
        return render(request, 'catalogo_clips/ingesta.html', {'modo': 'subir', 'error': msg})
    if f.size and f.size > _MAX_BYTES:
        return render(request, 'catalogo_clips/ingesta.html',
                      {'modo': 'subir', 'error': f'{f.name} pesa más de 16 MB. Sube una versión más liviana.'})

    try:
        subida = _subir_imagen_optimizada(f)
    except Exception as exc:  # noqa: BLE001
        logger.error('ingesta_web: falló subir %s (%s)', f.name, exc)
        return render(request, 'catalogo_clips/ingesta.html',
                      {'modo': 'subir', 'error': 'No se pudo subir la foto. Reintenta en un momento.'})

    draft = etiquetar_imagen(subida['cloud_url'])
    if not draft.get('orientacion'):
        draft['orientacion'] = _orientacion(subida.get('width'), subida.get('height'))
    return render(request, 'catalogo_clips/ingesta.html',
                  _ctx_confirmar(draft, f.name, subida['cloud_url']))


@staff_member_required
def ingesta_guardar(request):
    """Fase 3 (POST): guarda el clip confirmado por la operadora (upsert por archivo)."""
    if request.method != 'POST':
        return redirect('catalogo_web:ingesta')

    p = request.POST
    archivo = (p.get('archivo') or '').strip()
    cloud_url = (p.get('cloud_url') or '').strip()
    draft = _draft_desde_post(p)

    data = dict(draft, archivo=archivo, cloud_url=cloud_url, tipo='foto', fuente='ingesta_web')
    limpio, err = _validar_payload(data, parcial=False)
    if err:
        return render(request, 'catalogo_clips/ingesta.html',
                      _ctx_confirmar(draft, archivo, cloud_url, error=err))

    # Regla dura del negocio (igual que el saneo IA): con personas, derechos a revisar.
    if limpio.get('personas'):
        limpio['permiso'] = 'revisar_derechos'

    archivo_final = limpio.pop('archivo')
    clip, creado = Clip.objects.update_or_create(archivo=archivo_final, defaults=limpio)
    return redirect(f'/marketing/catalogo/{clip.id}/?guardado={"nueva" if creado else "actualizada"}')


# ---------------------------------------------------------------------------
# Componer historia (B2-A) — receta → URL Cloudinary. El preview ES el JPG final.
# ---------------------------------------------------------------------------

@staff_member_required
def componer(request, clip_id):
    clip = Clip.objects.filter(id=clip_id).first()
    if clip is None or not clip.cloud_url:
        raise Http404
    p = request.GET
    # Texto por defecto: la descripción del clip (Angélica lo reemplaza por el suyo).
    texto = p.get('texto') if 'texto' in p else (clip.descripcion or '')
    receta = receta_normalizada(texto, p.get('posicion'), p.get('preset'))
    preview = url_historia(clip.cloud_url, receta)
    return render(request, 'catalogo_clips/componer.html', {
        'clip': clip,
        'receta': receta,
        'preview': preview,
        'descarga': url_historia(clip.cloud_url, receta, attachment=True),
        'presets': list(PRESETS.keys()),
        'posiciones': list(POSICIONES.keys()),
        'thumb': thumb_url(clip.cloud_url),
    })


@staff_member_required
def detalle(request, clip_id):
    clip = Clip.objects.filter(id=clip_id).first()
    if clip is None:
        raise Http404
    campos = [
        ('Área', clip.get_area_display()),
        ('Nombre comercial', clip.nombre_comercial or '—'),
        ('Momento', clip.get_momento_display()),
        ('Estación', clip.get_estacion_display()),
        ('Vapor', clip.vapor),
        ('Decoración', clip.decoracion or '—'),
        ('Personas', 'Sí' if clip.personas else 'No'),
        ('Permiso', clip.get_permiso_display()),
        ('Calidad', clip.get_calidad_display()),
        ('Keeper', '⭐ Sí' if clip.keeper else 'No'),
        ('Estado', clip.get_estado_display()),
        ('Orientación', clip.orientacion or '—'),
        ('Fuente', clip.fuente or '—'),
        ('Origen', clip.origen or '—'),
        ('Etiquetas', ', '.join(clip.etiquetas or []) or '—'),
        ('Apto para', ', '.join(clip.apto_para or []) or '—'),
        ('Nota', clip.nota or '—'),
    ]
    return render(request, 'catalogo_clips/detalle.html', {
        'clip': clip,
        'campos': campos,
        'imagen': clip.cloud_url,
        'thumb_og': thumb_url(clip.cloud_url, 'w_900,q_auto,f_auto'),
        'puede_editar': request.user.has_perm('catalogo_clips.change_clip'),
        'atributos': clip.atributos or {},
        'guardado': request.GET.get('guardado', ''),
    })
