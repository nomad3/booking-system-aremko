"""Explota un brief semanal en filas de PublicacionPlanificada.

Idempotente por (semana_inicio, pieza_key): re-correr sobre la misma semana
actualiza el copy de las piezas que siguen 'pendiente' y NO toca las que
Angélica ya movió de estado (en_produccion/lista/publicada) — su trabajo
nunca se pisa por una regeneración del brief.
"""

import logging
import re
from datetime import timedelta

logger = logging.getLogger(__name__)

# El copywriter mete Story 1 y Story 2 en un mismo texto (separadas por "|").
# En Instagram son historias distintas → se parten en segmentos, cada uno con
# su propia foto y revisión. Mismo criterio que el split del frontend.
_STORY_SPLIT = re.compile(r'\s*\|?\s*(?=STORY\s*\d)', re.IGNORECASE)
_STORY_PREFIX = re.compile(r'^STORY\s*\d\s*[—\-]\s*', re.IGNORECASE)


def _split_historias(texto: str) -> list:
    """Parte 'STORY 1 — … | STORY 2 — …' en segmentos limpios. Devuelve [] si
    no hay 2+ historias (una pieza de una sola imagen no lleva segmentos)."""
    if not texto:
        return []
    partes = [p.strip() for p in _STORY_SPLIT.split(texto) if p and p.strip()]
    if len(partes) <= 1:
        return []
    segmentos = []
    for i, p in enumerate(partes, start=1):
        segmentos.append({
            'indice': i,
            'titulo': f'Historia {i}',
            'texto': _STORY_PREFIX.sub('', p).strip(),
            'material_urls': [],
            'material_meta': [],
            'revision_veredicto': 'sin_revisar',
            'revision_json': [],
            'revision_resumen': '',
            'revision_at': None,
        })
    return segmentos


def _segmentos_de_slides(slides) -> list:
    """Un segmento por slide del carrusel (cada slide su foto + revisión). []
    si es menos de 2 slides. El texto del segmento es el overlay + la imagen
    sugerida, para que la IA evalúe correspondencia foto↔slide."""
    if not isinstance(slides, list) or len(slides) < 2:
        return []
    segmentos = []
    for i, s in enumerate(slides, start=1):
        if not isinstance(s, dict):
            continue
        numero = s.get('numero') or i
        texto = (s.get('texto_overlay') or '').strip()
        img = (s.get('imagen_sugerida') or '').strip()
        if img:
            texto = (texto + f'\n📷 Imagen sugerida: {img}').strip()
        segmentos.append({
            'indice': i,
            'titulo': f'Slide {numero}',
            'texto': texto,
            'prompt_imagen_ia': (s.get('prompt_imagen_ia') or '').strip(),
            'material_urls': [],
            'material_meta': [],
            'revision_veredicto': 'sin_revisar',
            'revision_json': [],
            'revision_resumen': '',
            'revision_at': None,
        })
    return segmentos


def _segmentos_de_historias(historias) -> list:
    """Un segmento por historia del día (cada una su foto + revisión). Formato
    nuevo: el día trae una lista `historias` explícita (3 o 4 según el día), en
    vez de amontonar 'STORY 1 | STORY 2' en un solo texto. El texto del segmento
    es el texto_sugerido (fallback: concepto)."""
    if not isinstance(historias, list) or not historias:
        return []
    segmentos = []
    for i, h in enumerate(historias, start=1):
        if not isinstance(h, dict):
            continue
        texto = (h.get('texto_sugerido') or h.get('texto') or h.get('concepto') or '').strip()
        segmentos.append({
            'indice': i,
            'titulo': f'Historia {i}',
            'texto': texto,
            'prompt_imagen_ia': (h.get('prompt_imagen_ia') or '').strip(),
            'material_urls': [],
            'material_meta': [],
            'revision_veredicto': 'sin_revisar',
            'revision_json': [],
            'revision_resumen': '',
            'revision_at': None,
        })
    return segmentos


def _merge_segmentos(nuevos: list, viejos: list) -> list:
    """Al re-explotar, conserva foto/revisión ya subidas (por índice); solo
    refresca titulo/texto desde el brief. El trabajo de Angélica no se pisa."""
    by_idx = {s.get('indice'): s for s in (viejos or []) if isinstance(s, dict)}
    for seg in nuevos:
        old = by_idx.get(seg['indice'])
        if not old:
            continue
        for k in ('material_urls', 'material_meta', 'revision_veredicto',
                  'revision_json', 'revision_resumen', 'revision_at'):
            if old.get(k):
                seg[k] = old[k]
    return nuevos

# Día de la semana (offset desde el lunes) por pieza fija del brief.
PIEZAS_FIJAS = [
    # (pieza_key, canal, tipo, offset_dias, responsable_default)
    ('gbp_post', 'GBP', 'post', 0, 'Angélica'),
    ('reel_martes', 'Instagram', 'reel', 1, 'Angélica'),
    ('carrusel_miercoles', 'Instagram', 'carrusel', 2, 'Angélica'),
    ('email_engaged', 'Email', 'email', 2, 'Jorge'),
    ('reel_jueves', 'Instagram', 'reel', 3, 'Angélica'),
]

DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

# Reels que además se publican en TikTok: MISMO video que su gemelo de Instagram
# (guion/tomas/audio idénticos), pero con caption y hashtags nativos tomados del
# objeto anidado "tiktok" del copy. Se explotan como filas de cola separadas.
REELS_TIKTOK = [
    # (pieza_key_tiktok, pieza_key_instagram, offset_dias)
    ('reel_martes_tiktok', 'reel_martes', 1),
    ('reel_jueves_tiktok', 'reel_jueves', 3),
]

# Recordatorio operativo para quien publica en TikTok (viaja en el copy_json).
_NOTA_TIKTOK = (
    'Subir a TikTok el archivo de video ORIGINAL exportado limpio (sin marca de '
    'agua de Instagram). No descargues el Reel ya publicado para resubirlo: el '
    'watermark de otra plataforma penaliza el alcance en TikTok.'
)


def _derivar_pieza_tiktok(pieza_key: str, hermano_ig: dict) -> dict:
    """Arma la pieza de TikTok desde su gemelo de Instagram (es el MISMO video).

    guion/tomas/audio se copian tal cual del hermano; caption y hashtags salen
    del objeto anidado `tiktok` del copy. Si el copywriter no lo escribió, cae al
    caption de Instagram (el video igual debe salir) y deja un warning. No muta el
    dict original del hermano.
    """
    derivada = dict(hermano_ig)  # copia superficial: no tocamos el hermano IG
    tiktok = derivada.pop('tiktok', None)
    if isinstance(tiktok, dict) and (tiktok.get('caption_completo') or tiktok.get('hashtags')):
        derivada['caption_completo'] = tiktok.get('caption_completo') or hermano_ig.get('caption_completo', '')
        derivada['hashtags'] = tiktok.get('hashtags') or hermano_ig.get('hashtags', [])
    else:
        logger.warning(
            f'explode_brief: {pieza_key} sin objeto tiktok en el copy — '
            'usando caption de Instagram como respaldo'
        )
        # caption_completo/hashtags ya vienen copiados del hermano IG
    derivada['nota_publicacion'] = _NOTA_TIKTOK
    return derivada


def _titulo_de(pieza: dict) -> str:
    for key in ('concepto', 'asunto', 'texto', 'tema_sugerido'):
        val = (pieza.get(key) or '').strip()
        if val:
            return val.splitlines()[0][:290]
    # Formato nuevo de historias del día: resumen desde los conceptos.
    historias = pieza.get('historias')
    if isinstance(historias, list) and historias:
        conceptos = [
            (h.get('concepto') or h.get('texto_sugerido') or '').strip().splitlines()[0]
            for h in historias if isinstance(h, dict)
        ]
        conceptos = [c for c in conceptos if c]
        if conceptos:
            return f'{len(conceptos)} historias: ' + ' · '.join(conceptos)[:280]
    return ''


def _build_hora_lookup(brief: dict) -> dict:
    """Mapa (dia_nombre, tipo) -> hora, tomado del calendario_semanal del brief.

    Las horas viven en `calendario_semanal` (pasada de análisis), separadas de
    los `drafts_completos` (copy final) que se explotan. Este puente las cruza
    por día + tipo, que es 1:1 en la práctica (una pieza por tipo por día)."""
    lookup = {}
    for dia_entry in brief.get('calendario_semanal') or []:
        if not isinstance(dia_entry, dict):
            continue
        dia_nombre = (dia_entry.get('dia') or '').strip().lower()
        for pub in dia_entry.get('publicaciones') or []:
            if not isinstance(pub, dict):
                continue
            hora = (pub.get('hora') or '').strip()
            tipo = (pub.get('tipo') or '').strip().lower()
            if hora and dia_nombre and tipo:
                lookup.setdefault((dia_nombre, tipo), hora)  # primera gana
    return lookup


def explode_brief_to_publicaciones(semana_inicio, brief: dict) -> int:
    """Crea/actualiza las PublicacionPlanificada de la semana desde el brief.

    Devuelve cuántas filas se crearon o actualizaron. Nunca lanza: cualquier
    error se loguea y devuelve lo que alcanzó a procesar (no puede tumbar la
    generación del brief del lunes).
    """
    from .models import PublicacionPlanificada

    drafts = brief.get('drafts_completos') or {}
    if not drafts:
        logger.warning('explode_brief: brief sin drafts_completos — no se generan publicaciones')
        return 0

    hora_lookup = _build_hora_lookup(brief)
    procesadas = 0

    def _hora_de(pieza, dia_nombre, tipo):
        return (pieza.get('hora') or hora_lookup.get((dia_nombre.lower(), tipo.lower()), '') or '')[:5]

    def _upsert(pieza_key, canal, tipo, dia, pieza, responsable, hora, segmentos=None):
        nonlocal procesadas
        try:
            existente = PublicacionPlanificada.objects.filter(
                semana_inicio=semana_inicio, pieza_key=pieza_key,
            ).first()
            necesario = pieza.get('necesario_esta_semana', True)
            estado_inicial = 'pendiente' if necesario else 'no_aplica'
            if existente is None:
                PublicacionPlanificada.objects.create(
                    semana_inicio=semana_inicio,
                    dia=dia,
                    hora_sugerida=hora,
                    canal=canal,
                    tipo=tipo,
                    pieza_key=pieza_key,
                    titulo=_titulo_de(pieza),
                    copy_json=pieza,
                    responsable=pieza.get('responsable') or responsable,
                    tiempo_estimado=pieza.get('tiempo_estimado') or '',
                    estado=estado_inicial,
                    segmentos=segmentos or [],
                )
                procesadas += 1
            elif existente.estado in ('pendiente', 'no_aplica'):
                # Solo se actualizan piezas que nadie tocó todavía.
                existente.dia = dia
                existente.hora_sugerida = hora
                existente.titulo = _titulo_de(pieza)
                existente.copy_json = pieza
                existente.responsable = pieza.get('responsable') or responsable
                existente.tiempo_estimado = pieza.get('tiempo_estimado') or ''
                existente.estado = estado_inicial
                # Preserva fotos/revisión ya subidas por historia (por índice).
                existente.segmentos = _merge_segmentos(segmentos, existente.segmentos) if segmentos else []
                existente.save()
                procesadas += 1
        except Exception as exc:  # noqa: BLE001 — una pieza mala no frena el resto
            logger.warning(f'explode_brief: pieza {pieza_key} falló ({exc})')

    for pieza_key, canal, tipo, offset, responsable in PIEZAS_FIJAS:
        pieza = drafts.get(pieza_key)
        if isinstance(pieza, dict) and pieza:
            dia_nombre = DIAS_SEMANA[offset]
            # Carrusel: un segmento por slide (cada slide su foto + revisión).
            segs = _segmentos_de_slides(pieza.get('slides')) if tipo == 'carrusel' else None
            _upsert(
                pieza_key, canal, tipo, semana_inicio + timedelta(days=offset),
                pieza, responsable, _hora_de(pieza, dia_nombre, tipo), segmentos=segs,
            )

    # Cross-post a TikTok: mismo video del Reel de Instagram, caption/hashtags
    # nativos. Se deriva del gemelo IG (mismo día y hora) como fila aparte.
    for pieza_key, hermano_key, offset in REELS_TIKTOK:
        hermano = drafts.get(hermano_key)
        if not (isinstance(hermano, dict) and hermano):
            continue
        dia_nombre = DIAS_SEMANA[offset]
        _upsert(
            pieza_key, 'TikTok', 'reel', semana_inicio + timedelta(days=offset),
            _derivar_pieza_tiktok(pieza_key, hermano), 'Angélica',
            _hora_de(hermano, dia_nombre, 'reel'),
        )

    stories = drafts.get('stories_diarias') or []
    for story in stories:
        if not isinstance(story, dict):
            continue
        dia_nombre = (story.get('dia') or '').strip()
        try:
            offset = DIAS_SEMANA.index(dia_nombre)
        except ValueError:
            continue
        # Formato nuevo: el día trae una lista `historias` (3 o 4). Formato viejo:
        # un solo texto_sugerido que amontona 'STORY 1 | STORY 2'. Soporta ambos.
        historias = story.get('historias')
        if isinstance(historias, list) and historias:
            segs = _segmentos_de_historias(historias)
        else:
            texto_story = story.get('texto_sugerido') or story.get('caption_completo') or ''
            segs = _split_historias(texto_story)
        _upsert(
            f'story_{dia_nombre.lower()}',
            'Instagram Stories',
            'story',
            semana_inicio + timedelta(days=offset),
            story,
            'Angélica',
            _hora_de(story, dia_nombre, 'story'),
            segmentos=segs,
        )

    logger.info(f'explode_brief: {procesadas} publicaciones creadas/actualizadas para {semana_inicio}')
    return procesadas
