"""Explorador web del Catálogo de Clips (H-071, Fase B1) — para el CM (Angélica).

Pantalla Django server-rendered, protegida con @staff_member_required (staff, NO
superuser): ver / filtrar / buscar el catálogo con miniaturas Cloudinary chicas.
SOLO lectura — la edición vive en el admin + PATCH API; el render llega en B2.

Consulta el ORM directo (mismo proyecto). La API REST de H-070 sigue intacta
para consumidores externos y el auto-pick futuro (B3).
"""
import logging
import os
from urllib.parse import quote, urlencode

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .api_views import (_validar_payload, _subir_imagen_optimizada, _orientacion,
                        _EXT_IMAGEN, _MAX_BYTES)
from .composer import receta_normalizada, url_historia, PRESETS, POSICIONES, ANCHO, ALTO
from .models import Clip, UsoClip
from .seleccionar import seleccionar_clip
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

    # Querystring sin `page` para que la paginación conserve los filtros
    # (arrastra pub_id/segmento si venimos de "Crear historia" en Publicaciones).
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
        'pub_contexto': _pub_contexto(p),
        'auto_error': _AUTO_ERROR_LABEL.get(p.get('auto_error', '')),
    })


# H-073 (Fase 2): mensajes cuando auto_generar no pudo resolver una foto sola
# y manda de vuelta acá para que Angélica elija a mano.
_AUTO_ERROR_LABEL = {
    'sin_criterio': '🤖 Esta historia no trae criterio de foto (brief antiguo) — elige manualmente.',
    'sin_foto': '🤖 No se encontró ninguna foto que calce con el criterio — elige manualmente o sube fotos de esa área.',
}


def _pub_contexto(params):
    """Si venimos de 'Crear historia' (H-072), arma el texto del banner
    'Eligiendo foto para: …'. Best-effort: nunca debe romper la página."""
    pub_id = (params.get('pub_id') or '').strip()
    if not pub_id:
        return None
    try:
        from marketing_briefs.models import PublicacionPlanificada
        pub = PublicacionPlanificada.objects.filter(id=pub_id).only('dia', 'canal', 'tipo').first()
    except Exception:  # noqa: BLE001
        pub = None
    if pub is None:
        return None
    return f'{pub.dia:%d/%m} · {pub.canal}/{pub.tipo}'


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

_ERRORES_ENGANCHE = {
    'sin_texto': 'Falta el texto de la historia.',
    'sin_publicacion': 'No se encontró la publicación — vuelve a "Publicaciones" e inténtalo de nuevo.',
    'segmento_invalido': 'El número de historia no es válido.',
    'segmento_no_existe': 'Esa historia ya no existe en la publicación (puede haber cambiado el brief).',
}


def _pub_y_segmento(params):
    """Lee pub_id/segmento de la querystring → (pub, segmento_idx, pub_id_raw, segmento_raw).
    Best-effort: nunca rompe la página (pub queda None si algo no calza)."""
    pub_id_raw = (params.get('pub_id') or '').strip()
    segmento_raw = (params.get('segmento') or '').strip()
    pub = None
    if pub_id_raw:
        try:
            from marketing_briefs.models import PublicacionPlanificada
            pub = PublicacionPlanificada.objects.filter(id=pub_id_raw).first()
        except Exception:  # noqa: BLE001
            pub = None
    segmento_idx = None
    if segmento_raw:
        try:
            segmento_idx = int(segmento_raw)
        except ValueError:
            segmento_idx = None
    return pub, segmento_idx, pub_id_raw, segmento_raw


def _criterio_de_pub_segmento(pub, segmento_idx):
    """criterio_foto (H-073): del segmento si se pidió uno en concreto; si no,
    del copy_json de la pieza completa (piezas de 1 sola imagen, ej. gbp_post).
    None si no hay — el llamador decide ofrecer manual en ese caso."""
    if segmento_idx is not None:
        seg = next((s for s in (pub.segmentos or [])
                    if isinstance(s, dict) and s.get('indice') == segmento_idx), None)
        cf = seg.get('criterio_foto') if seg else None
    else:
        cf = (pub.copy_json or {}).get('criterio_foto') if isinstance(pub.copy_json, dict) else None
    return cf if isinstance(cf, dict) else None


# H-073 (Fase 2): etiqueta legible del nivel de degradación del auto-pick,
# para el banner de transparencia en el composer.
_NIVEL_LABEL = {
    1: 'coincidencia exacta (foto hero, nunca usada)',
    2: 'coincidencia exacta',
    3: 'se relajó momento/decoración',
    4: 'foto repetida (no había ninguna fresca)',
    5: 'tiene personas — revisar antes de publicar',
}


@staff_member_required
def componer(request, clip_id):
    clip = Clip.objects.filter(id=clip_id).first()
    if clip is None or not clip.cloud_url:
        raise Http404
    p = request.GET
    pub, segmento_idx, pub_id_raw, segmento_raw = _pub_y_segmento(p)

    if 'texto' in p:
        texto = p.get('texto')
    elif pub is not None:
        from marketing_briefs.web_views import texto_de_publicacion
        texto = texto_de_publicacion(pub, segmento_idx)
    else:
        # Sin publicación de contexto (uso libre de B2-A): la descripción del clip.
        texto = clip.descripcion or ''

    receta = receta_normalizada(texto, p.get('posicion'), p.get('preset'))
    preview = url_historia(clip.cloud_url, receta)

    # H-073: si llegamos vía auto_generar, arma el banner + el link "otra foto"
    # (misma cascada, saltándose lo ya mostrado — `excluir` viaja acumulado).
    es_auto = p.get('auto') == '1'
    nivel_raw = p.get('nivel', '')
    otra_foto_url = ''
    if es_auto and pub is not None:
        qparts = {'pub_id': pub_id_raw}
        if segmento_raw:
            qparts['segmento'] = segmento_raw
        if p.get('excluir'):
            qparts['excluir'] = p['excluir']
        otra_foto_url = f"{reverse('catalogo_web:auto_generar')}?{urlencode(qparts)}"

    return render(request, 'catalogo_clips/componer.html', {
        'clip': clip,
        'receta': receta,
        'preview': preview,
        'descarga': url_historia(clip.cloud_url, receta, attachment=True),
        'presets': list(PRESETS.keys()),
        'posiciones': list(POSICIONES.keys()),
        'thumb': thumb_url(clip.cloud_url),
        'pub': pub,
        'segmento_idx': segmento_idx,
        'pub_id_param': pub_id_raw,
        'segmento_param': segmento_raw,
        'error_msg': _ERRORES_ENGANCHE.get(p.get('error', '')),
        'es_auto': es_auto,
        'nivel_label': _NIVEL_LABEL.get(int(nivel_raw)) if nivel_raw.isdigit() else '',
        'aviso_auto': p.get('aviso', ''),
        'otra_foto_url': otra_foto_url,
    })


@staff_member_required
def auto_generar(request):
    """H-073 (Fase 2): resuelve la foto SOLA (sin LLM) desde el criterio_foto
    del brief y redirige al composer ya con esa foto elegida, con el banner
    de transparencia (nivel/aviso). "Otra foto" vuelve acá con `excluir`
    acumulado para saltarse las ya mostradas — misma cascada determinista."""
    p = request.GET
    pub, segmento_idx, pub_id_raw, segmento_raw = _pub_y_segmento(p)
    if pub is None:
        raise Http404
    if segmento_raw and segmento_idx is None:
        raise Http404

    qs_manual = f'?pub_id={pub.id}' + (f'&segmento={segmento_idx}' if segmento_idx is not None else '')
    destino_manual = reverse('catalogo_web:explorador')

    criterio = _criterio_de_pub_segmento(pub, segmento_idx)
    if not criterio:
        return redirect(f'{destino_manual}{qs_manual}&auto_error=sin_criterio')

    excluir_raw = (p.get('excluir') or '').strip()
    excluir_ids = [int(x) for x in excluir_raw.split(',') if x.strip().isdigit()] if excluir_raw else []

    clip, nivel, aviso = seleccionar_clip(criterio, excluir_ids=excluir_ids)
    if clip is None:
        return redirect(f'{destino_manual}{qs_manual}&auto_error=sin_foto')

    qs_params = {'pub_id': str(pub.id), 'auto': '1', 'nivel': str(nivel)}
    if segmento_idx is not None:
        qs_params['segmento'] = str(segmento_idx)
    if aviso:
        qs_params['aviso'] = aviso
    qs_params['excluir'] = ','.join(str(i) for i in (excluir_ids + [clip.id]))

    logger.info('[H-073] auto-pick: pub=%s segmento=%s -> clip=%s nivel=%s', pub.id, segmento_idx, clip.id, nivel)
    return redirect(f"{reverse('catalogo_web:componer', args=[clip.id])}?{urlencode(qs_params)}")


@staff_member_required
@require_http_methods(['POST'])
def enganchar_publicacion(request, clip_id):
    """H-072: guarda la historia compuesta EN la publicación (ORM directo, sin
    re-subir — la cloud_url ya es Cloudinary) y registra el uso del clip
    (cimiento del anti-repetición de Fase 2)."""
    clip = Clip.objects.filter(id=clip_id).first()
    if clip is None or not clip.cloud_url:
        raise Http404
    p = request.POST
    pub_id = (p.get('pub_id') or '').strip()
    seg_raw = (p.get('segmento') or '').strip()

    def _volver(error):
        qs = f'pub_id={pub_id}&' if pub_id else ''
        qs += f'segmento={seg_raw}&' if seg_raw else ''
        return redirect(f'/marketing/catalogo/componer/{clip_id}/?{qs}error={error}')

    receta = receta_normalizada(p.get('texto'), p.get('posicion'), p.get('preset'))
    url = url_historia(clip.cloud_url, receta)
    if not url:
        return _volver('sin_texto')

    from marketing_briefs.models import PublicacionPlanificada
    pub = PublicacionPlanificada.objects.filter(id=pub_id).first() if pub_id else None
    if pub is None:
        return _volver('sin_publicacion')

    segmento_idx = None
    if seg_raw:
        try:
            segmento_idx = int(seg_raw)
        except ValueError:
            return _volver('segmento_invalido')

    item = {
        'url': url, 'tipo': 'historia', 'width': ANCHO, 'height': ALTO,
        'ratio': '9:16', 'orientacion': 'vertical',
        # La receta completa queda guardada junto al material → se puede re-editar.
        'receta': {'texto': receta['texto'], 'posicion': receta['posicion'],
                   'preset': receta['preset'], 'clip_id': clip.id, 'tipo': 'historia'},
    }

    if segmento_idx is not None:
        segs = pub.segmentos or []
        seg = next((s for s in segs if isinstance(s, dict) and s.get('indice') == segmento_idx), None)
        if seg is None:
            return _volver('segmento_no_existe')
        seg['material_urls'] = list(seg.get('material_urls') or []) + [url]
        seg['material_meta'] = list(seg.get('material_meta') or []) + [item]
        pub.segmentos = segs  # reasigna para marcar el JSONField como modificado
    else:
        pub.material_urls = list(pub.material_urls or []) + [url]
        pub.material_meta = list(pub.material_meta or []) + [item]
    pub.estado = 'lista'
    pub.save()

    UsoClip.objects.create(clip=clip, fecha=timezone.now().date(), canal=pub.canal, publicacion_id=pub.id)
    clip.ultimo_uso = timezone.now().date()
    clip.save(update_fields=['ultimo_uso'])

    logger.info('[H-072] historia enganchada: clip=%s pub=%s segmento=%s', clip.id, pub.id, segmento_idx)
    return redirect(f'/marketing/publicaciones/?enganchado={pub.id}')


def _elegir_diverso(criterio, excluidos_ids, nombres_usados, intentos=4):
    """H-074 (Fase 3): dentro de un lote, intenta no repetir `nombre_comercial`
    entre historias con el MISMO criterio genérico (deseable, no obligatorio
    — ver BRIEF_H-074 §2). Si el criterio ya pide una tina/cabaña puntual, no
    hay nada que diversificar. Si no logra una distinta en `intentos`, se
    queda con la primera candidata — la diversidad nunca hace fallar el ítem."""
    if (criterio.get('nombre_comercial') or '').strip():
        return seleccionar_clip(criterio, excluir_ids=list(excluidos_ids))
    probados = set(excluidos_ids)
    primera = None
    for _ in range(intentos):
        clip, nivel, aviso = seleccionar_clip(criterio, excluir_ids=list(probados))
        if clip is None:
            # Sin más candidatas: si ya había una (aunque repita nombre), se
            # usa esa — la diversidad nunca hace fallar el ítem. Si nunca
            # hubo ninguna, este (None, nivel, aviso) ES el resultado real.
            break
        if primera is None:
            primera = (clip, nivel, aviso)
        if clip.nombre_comercial not in nombres_usados:
            return clip, nivel, aviso
        probados.add(clip.id)
    else:
        # Se agotaron los `intentos` sin encontrar una nombre_comercial nueva.
        return primera
    return primera if primera is not None else (clip, nivel, aviso)


@staff_member_required
@require_http_methods(['POST'])
def generar_lote(request, pub_id):
    """H-074 (Fase 3): batch de auto-pick para TODAS las historias
    auto-generables (con criterio_foto, sin material aún) de una
    publicación. Anti-repetición DURA entre ellas dentro del lote
    (`excluir_ids` acumulado; `seleccionar_clip` ya excluye el histórico de
    60 días) + diversidad de `nombre_comercial` deseable. Nunca toca
    historias que YA tienen material (enganchadas a mano o por un lote
    anterior) — esas se re-generan una por una desde el composer (Fase 2),
    no acá. "Lista" no es "publicada": Angélica revisa después."""
    from marketing_briefs.models import PublicacionPlanificada
    pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
    if pub is None:
        raise Http404

    segs = pub.segmentos or []
    generadas = con_aviso = a_manual = 0
    excluidos, nombres_usados = set(), set()

    for seg in segs:
        if not isinstance(seg, dict) or seg.get('material_urls'):
            continue  # ya tiene material — regla dura: el lote no la toca
        criterio = seg.get('criterio_foto')
        if not isinstance(criterio, dict) or not (criterio.get('area') or '').strip():
            a_manual += 1
            continue

        clip, nivel, aviso = _elegir_diverso(criterio, excluidos, nombres_usados)
        if clip is None:
            a_manual += 1
            continue

        texto = (seg.get('texto') or seg.get('titulo') or '').strip()
        receta = receta_normalizada(texto, None, None)
        url = url_historia(clip.cloud_url, receta)
        if not url:
            a_manual += 1
            continue

        seg['material_urls'] = list(seg.get('material_urls') or []) + [url]
        seg['material_meta'] = list(seg.get('material_meta') or []) + [{
            'url': url, 'tipo': 'historia', 'width': ANCHO, 'height': ALTO,
            'ratio': '9:16', 'orientacion': 'vertical',
            'receta': {'texto': receta['texto'], 'posicion': receta['posicion'],
                       'preset': receta['preset'], 'clip_id': clip.id, 'tipo': 'historia'},
        }]

        UsoClip.objects.create(clip=clip, fecha=timezone.now().date(), canal=pub.canal, publicacion_id=pub.id)
        clip.ultimo_uso = timezone.now().date()
        clip.save(update_fields=['ultimo_uso'])

        excluidos.add(clip.id)
        if clip.nombre_comercial:
            nombres_usados.add(clip.nombre_comercial)
        generadas += 1
        if aviso:
            con_aviso += 1

    pub.segmentos = segs
    if generadas:
        pub.estado = 'lista'
    pub.save()

    resumen = f'Generé {generadas} historia{"s" if generadas != 1 else ""}'
    if con_aviso:
        resumen += f' · {con_aviso} con aviso de degradación'
    if a_manual:
        resumen += f' · {a_manual} para Manual'
    logger.info('[H-074] lote pub=%s: %s generadas, %s con aviso, %s a manual',
                pub.id, generadas, con_aviso, a_manual)
    return redirect(f'/marketing/publicaciones/?lote={pub.id}&resumen={quote(resumen)}')


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
    # H-072: si venimos de "Crear historia" (Publicaciones), arrastrar pub_id/segmento
    # al botón "Usar en historia" para que el composer precargue el texto del brief.
    pub_id = (request.GET.get('pub_id') or '').strip()
    segmento = (request.GET.get('segmento') or '').strip()
    componer_qs = ''
    if pub_id:
        componer_qs = f'?pub_id={pub_id}' + (f'&segmento={segmento}' if segmento else '')

    return render(request, 'catalogo_clips/detalle.html', {
        'clip': clip,
        'campos': campos,
        'imagen': clip.cloud_url,
        'thumb_og': thumb_url(clip.cloud_url, 'w_900,q_auto,f_auto'),
        'puede_editar': request.user.has_perm('catalogo_clips.change_clip'),
        'atributos': clip.atributos or {},
        'guardado': request.GET.get('guardado', ''),
        'componer_qs': componer_qs,
        'pub_contexto': _pub_contexto(request.GET),
    })
