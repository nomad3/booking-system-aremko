"""Explota un brief semanal en filas de PublicacionPlanificada.

Idempotente por (semana_inicio, pieza_key): re-correr sobre la misma semana
actualiza el copy de las piezas que siguen 'pendiente' y NO toca las que
Angélica ya movió de estado (en_produccion/lista/publicada) — su trabajo
nunca se pisa por una regeneración del brief.
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

# Día de la semana (offset desde el lunes) por pieza fija del brief.
PIEZAS_FIJAS = [
    # (pieza_key, canal, tipo, offset_dias, responsable_default)
    ('gbp_post', 'GBP', 'post', 0, 'Daniela'),
    ('reel_martes', 'Instagram', 'reel', 1, 'Daniela'),
    ('carrusel_miercoles', 'Instagram', 'carrusel', 2, 'Daniela'),
    ('email_engaged', 'Email', 'email', 2, 'Jorge'),
    ('reel_jueves', 'Instagram', 'reel', 3, 'Daniela'),
]

DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def _titulo_de(pieza: dict) -> str:
    for key in ('concepto', 'asunto', 'texto', 'tema_sugerido'):
        val = (pieza.get(key) or '').strip()
        if val:
            return val.splitlines()[0][:290]
    return ''


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

    procesadas = 0

    def _upsert(pieza_key, canal, tipo, dia, pieza, responsable):
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
                    canal=canal,
                    tipo=tipo,
                    pieza_key=pieza_key,
                    titulo=_titulo_de(pieza),
                    copy_json=pieza,
                    responsable=pieza.get('responsable') or responsable,
                    tiempo_estimado=pieza.get('tiempo_estimado') or '',
                    estado=estado_inicial,
                )
                procesadas += 1
            elif existente.estado in ('pendiente', 'no_aplica'):
                # Solo se actualizan piezas que nadie tocó todavía.
                existente.dia = dia
                existente.titulo = _titulo_de(pieza)
                existente.copy_json = pieza
                existente.responsable = pieza.get('responsable') or responsable
                existente.tiempo_estimado = pieza.get('tiempo_estimado') or ''
                existente.estado = estado_inicial
                existente.save()
                procesadas += 1
        except Exception as exc:  # noqa: BLE001 — una pieza mala no frena el resto
            logger.warning(f'explode_brief: pieza {pieza_key} falló ({exc})')

    for pieza_key, canal, tipo, offset, responsable in PIEZAS_FIJAS:
        pieza = drafts.get(pieza_key)
        if isinstance(pieza, dict) and pieza:
            _upsert(pieza_key, canal, tipo, semana_inicio + timedelta(days=offset), pieza, responsable)

    stories = drafts.get('stories_diarias') or []
    for story in stories:
        if not isinstance(story, dict):
            continue
        dia_nombre = (story.get('dia') or '').strip()
        try:
            offset = DIAS_SEMANA.index(dia_nombre)
        except ValueError:
            continue
        _upsert(
            f'story_{dia_nombre.lower()}',
            'Instagram Stories',
            'story',
            semana_inicio + timedelta(days=offset),
            story,
            'Daniela',
        )

    logger.info(f'explode_brief: {procesadas} publicaciones creadas/actualizadas para {semana_inicio}')
    return procesadas
