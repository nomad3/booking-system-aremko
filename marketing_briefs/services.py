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
    ('gbp_post', 'GBP', 'post', 0, 'Angélica'),
    ('reel_martes', 'Instagram', 'reel', 1, 'Angélica'),
    ('carrusel_miercoles', 'Instagram', 'carrusel', 2, 'Angélica'),
    ('email_engaged', 'Email', 'email', 2, 'Jorge'),
    ('reel_jueves', 'Instagram', 'reel', 3, 'Angélica'),
]

DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def _titulo_de(pieza: dict) -> str:
    for key in ('concepto', 'asunto', 'texto', 'tema_sugerido'):
        val = (pieza.get(key) or '').strip()
        if val:
            return val.splitlines()[0][:290]
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

    def _upsert(pieza_key, canal, tipo, dia, pieza, responsable, hora):
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
                existente.save()
                procesadas += 1
        except Exception as exc:  # noqa: BLE001 — una pieza mala no frena el resto
            logger.warning(f'explode_brief: pieza {pieza_key} falló ({exc})')

    for pieza_key, canal, tipo, offset, responsable in PIEZAS_FIJAS:
        pieza = drafts.get(pieza_key)
        if isinstance(pieza, dict) and pieza:
            dia_nombre = DIAS_SEMANA[offset]
            _upsert(
                pieza_key, canal, tipo, semana_inicio + timedelta(days=offset),
                pieza, responsable, _hora_de(pieza, dia_nombre, tipo),
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
        _upsert(
            f'story_{dia_nombre.lower()}',
            'Instagram Stories',
            'story',
            semana_inicio + timedelta(days=offset),
            story,
            'Angélica',
            _hora_de(story, dia_nombre, 'story'),
        )

    logger.info(f'explode_brief: {procesadas} publicaciones creadas/actualizadas para {semana_inicio}')
    return procesadas
