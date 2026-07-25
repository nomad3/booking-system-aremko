"""Explorador web del Catálogo de Clips (H-071, Fase B1) — para el CM (Angélica).

Pantalla Django server-rendered, protegida con @staff_member_required (staff, NO
superuser): ver / filtrar / buscar el catálogo con miniaturas Cloudinary chicas.
SOLO lectura — la edición vive en el admin + PATCH API; el render llega en B2.

Consulta el ORM directo (mismo proyecto). La API REST de H-070 sigue intacta
para consumidores externos y el auto-pick futuro (B3).
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render

from .models import Clip

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
    })
