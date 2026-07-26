"""Pantalla "Publicaciones" (H-072 Fase 1) — cola de trabajo semanal de
Angélica en Django server-rendered, misma estética boutique del catálogo.

Solo lectura + el puente hacia "Crear historia" (catalogo_clips). El enganche
real (guardar la historia compuesta en la publicación) vive en
catalogo_clips.web_views.enganchar_publicacion (importa este modelo por ORM,
sin FK entre apps — ver H-072).
"""
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .models import PublicacionPlanificada

ESTADO_LABEL = {
    'pendiente': ('⚪', 'Pendiente'),
    'en_produccion': ('🟡', 'En producción'),
    'lista': ('🟢', 'Lista para publicar'),
    'publicada': ('✅', 'Publicada'),
    'no_aplica': ('⚫', 'No aplica'),
}


def _texto_preview(copy_json, maximo=180):
    """Best-effort: extrae un texto legible del copy_json (shape variable según
    tipo de pieza — reel/carrusel/post/gbp/story). Nunca falla."""
    cj = copy_json if isinstance(copy_json, dict) else {}
    for key in ('texto_sugerido', 'caption_completo', 'concepto', 'titulo'):
        v = cj.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()[:maximo]
    guion = cj.get('guion')
    if isinstance(guion, list) and guion:
        partes = []
        for g in guion[:2]:
            if isinstance(g, str):
                partes.append(g)
            elif isinstance(g, dict):
                partes.append(g.get('texto') or g.get('linea') or '')
        txt = ' '.join(p for p in partes if p).strip()
        if txt:
            return txt[:maximo]
    return ''


def _qs_ver_editar(receta, pub_id, segmento=None):
    """Querystring para reabrir en el composer una historia ya compuesta
    (Jorge, 2026-07-26: "cómo puedo ver la Historia 1... para editarla").
    Soporta el modo clásico (texto) Y "3 líneas con tamaño" (receta.lineas,
    Jorge 2026-07-26) — una pieza puede haberse hecho con cualquiera de
    los dos según cuándo se generó."""
    if not receta:
        return ''
    params = {'texto': receta.get('texto', ''), 'posicion': receta.get('posicion', ''),
              'preset': receta.get('preset', ''), 'pub_id': pub_id}
    if segmento is not None:
        params['segmento'] = segmento
    for i, linea in enumerate(receta.get('lineas') or [], start=1):
        params[f'linea{i}'] = linea.get('texto', '') if isinstance(linea, dict) else ''
        params[f'linea{i}_tamano'] = linea.get('tamano', '') if isinstance(linea, dict) else ''
    return urlencode(params)


def texto_de_publicacion(pub, segmento_idx=None):
    """El texto por defecto para precargar el composer: el de la historia
    (segmento) si se pidió una en concreto; si no, el de la pieza completa."""
    if segmento_idx is not None:
        seg = next((s for s in (pub.segmentos or [])
                    if isinstance(s, dict) and s.get('indice') == segmento_idx), None)
        if seg and (seg.get('texto') or '').strip():
            return seg['texto'].strip()
    return _texto_preview(pub.copy_json, maximo=220)


@staff_member_required
def publicaciones_lista(request):
    p = request.GET
    try:
        base = date.fromisoformat(p.get('semana')) if p.get('semana') else date.today()
    except ValueError:
        base = date.today()
    lunes = base - timedelta(days=base.weekday())
    hoy_lunes = date.today() - timedelta(days=date.today().weekday())

    qs = PublicacionPlanificada.objects.filter(semana_inicio=lunes).order_by('dia', 'id')

    hoy = date.today()
    tarjetas = []
    for pub in qs:
        historias = []
        pendientes_lote = 0
        for seg in (pub.segmentos or []):
            if not isinstance(seg, dict):
                continue
            urls = seg.get('material_urls') or []
            metas = seg.get('material_meta') or []
            tiene_criterio = bool(seg.get('criterio_foto'))
            tiene_material = bool(urls)
            if tiene_criterio and not tiene_material:
                pendientes_lote += 1
            # Receta vigente (del último material enganchado) — permite
            # reabrir esta historia YA compuesta en el composer para verla
            # grande, descargarla o editarla de nuevo (Jorge, 2026-07-26).
            receta_vigente = None
            if metas and isinstance(metas[-1], dict):
                receta_vigente = metas[-1].get('receta')
            historias.append({
                'indice': seg.get('indice'),
                'titulo': seg.get('titulo') or f"Historia {seg.get('indice')}",
                'texto': (seg.get('texto') or '')[:160],
                'tiene_material': tiene_material,
                # H-074: `urls[-1]` es la vigente (última enganchada), no la
                # primera — mismo criterio "último = vigente" que ya usa
                # revision_service para fotos/video. Antes de este fix, un
                # re-generado (Fase 2 u otra vuelta del lote) no se reflejaba
                # acá: la miniatura seguía mostrando la foto vieja.
                'preview': urls[-1] if urls else None,
                # H-073: solo con criterio_foto se puede ofrecer "🤖 Generar".
                'tiene_criterio': tiene_criterio,
                'receta': receta_vigente,
                'ver_editar_qs': _qs_ver_editar(receta_vigente, pub.id, seg.get('indice')),
            })
        estado_icono, estado_label = ESTADO_LABEL.get(pub.estado, ('⚪', pub.estado))
        copy_json = pub.copy_json if isinstance(pub.copy_json, dict) else {}
        material_urls = pub.material_urls or []
        material_metas = pub.material_meta or []
        receta_vigente_pub = None
        if material_metas and isinstance(material_metas[-1], dict):
            receta_vigente_pub = material_metas[-1].get('receta')
        tarjetas.append({
            'pub': pub,
            'texto_preview': _texto_preview(pub.copy_json),
            'tiene_material': bool(material_urls),
            'material_preview': material_urls[-1] if material_urls else None,  # ver nota arriba (vigente=último)
            'historias': historias,
            'estado_icono': estado_icono,
            'estado_label': estado_label,
            'tiene_criterio': bool(copy_json.get('criterio_foto')),
            'receta': receta_vigente_pub,
            'ver_editar_qs': _qs_ver_editar(receta_vigente_pub, pub.id),
            # H-074: botón de lote — solo si queda algo por auto-generar en esta pieza.
            'pendientes_lote': pendientes_lote,
            'tiene_lote_disponible': pendientes_lote > 0,
            'es_hoy': pub.dia == hoy,
        })

    # H-074: id de la pieza de HOY con algo pendiente de auto-generar, si está
    # visible en esta semana — es lo que activa el atajo global "las de hoy".
    lote_hoy_pub_id = next(
        (t['pub'].id for t in tarjetas if t['es_hoy'] and t['tiene_lote_disponible']), None,
    )

    return render(request, 'marketing_briefs/publicaciones.html', {
        'tarjetas': tarjetas,
        'lunes': lunes,
        'es_semana_actual': lunes == hoy_lunes,
        'semana_anterior': (lunes - timedelta(days=7)).isoformat(),
        'semana_siguiente': (lunes + timedelta(days=7)).isoformat(),
        'enganchado': p.get('enganchado', ''),
        'resumen_lote': p.get('resumen', ''),
        'lote_hoy_pub_id': lote_hoy_pub_id,
    })
