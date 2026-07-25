"""Pantalla "Publicaciones" (H-072 Fase 1) — cola de trabajo semanal de
Angélica en Django server-rendered, misma estética boutique del catálogo.

Solo lectura + el puente hacia "Crear historia" (catalogo_clips). El enganche
real (guardar la historia compuesta en la publicación) vive en
catalogo_clips.web_views.enganchar_publicacion (importa este modelo por ORM,
sin FK entre apps — ver H-072).
"""
from datetime import date, timedelta

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

    tarjetas = []
    for pub in qs:
        historias = []
        for seg in (pub.segmentos or []):
            if not isinstance(seg, dict):
                continue
            urls = seg.get('material_urls') or []
            historias.append({
                'indice': seg.get('indice'),
                'titulo': seg.get('titulo') or f"Historia {seg.get('indice')}",
                'texto': (seg.get('texto') or '')[:160],
                'tiene_material': bool(urls),
                'preview': urls[0] if urls else None,
                # H-073: solo con criterio_foto se puede ofrecer "🤖 Generar".
                'tiene_criterio': bool(seg.get('criterio_foto')),
            })
        estado_icono, estado_label = ESTADO_LABEL.get(pub.estado, ('⚪', pub.estado))
        copy_json = pub.copy_json if isinstance(pub.copy_json, dict) else {}
        tarjetas.append({
            'pub': pub,
            'texto_preview': _texto_preview(pub.copy_json),
            'tiene_material': bool(pub.material_urls),
            'material_preview': (pub.material_urls or [None])[0],
            'historias': historias,
            'estado_icono': estado_icono,
            'estado_label': estado_label,
            'tiene_criterio': bool(copy_json.get('criterio_foto')),
        })

    return render(request, 'marketing_briefs/publicaciones.html', {
        'tarjetas': tarjetas,
        'lunes': lunes,
        'es_semana_actual': lunes == hoy_lunes,
        'semana_anterior': (lunes - timedelta(days=7)).isoformat(),
        'semana_siguiente': (lunes + timedelta(days=7)).isoformat(),
        'enganchado': p.get('enganchado', ''),
    })
