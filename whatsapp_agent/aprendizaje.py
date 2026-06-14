"""Clasificador de correcciones del agente (H-010 parte 2).

Compara el borrador propuesto por el agente con lo que la persona realmente envió,
consulta el catálogo vivo, y clasifica la corrección para rutearla a su lugar:
- hecho_catalogo → cambio de precio/disponibilidad (lo aprueba Jorge; MVP: mostrar)
- regla → política → se agrega al Conocimiento del agente
- tono / puntual → no genera sugerencia (evita ruido)

Las funciones de prompt/parseo son puras (testeables sin DB/LLM).
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

TIPOS = {'hecho_catalogo', 'regla', 'tono', 'puntual'}
# Solo estos generan una sugerencia para aprobar (los demás son ruido).
TIPOS_ACCIONABLES = {'hecho_catalogo', 'regla'}

PROMPT_VERSION = 'clasif-f1-2026-06-14'


def build_clasificador_system(catalogo_texto, conocimiento):
    """System prompt del clasificador. Pura."""
    conocimiento = (conocimiento or '').strip() or '(sin reglas aún)'
    return f"""Eres un clasificador de correcciones del agente de Aremko Spa. Comparas lo que el
AGENTE PROPUSO (borrador) con lo que una PERSONA del equipo ENVIÓ (corregido) a un cliente.
Tu trabajo: entender QUÉ cambió y clasificar la corrección para aplicarla en el lugar correcto.

CATÁLOGO ACTUAL (precios y capacidad en vivo):
{catalogo_texto}

REGLAS/CONOCIMIENTO ACTUAL DEL AGENTE:
{conocimiento}

Clasifica la corrección en UNO de estos tipos:
- "hecho_catalogo": cambia un PRECIO, DISPONIBILIDAD o EXISTENCIA de un servicio/producto, y
  DIFIERE del catálogo de arriba (ej. el agente dijo $25.000 y se corrigió a $30.000). En
  `texto_propuesto` describe el cambio en una frase; en `ref_catalogo` pon "ítem · campo · valor".
- "regla": cambia el CÓMO o una POLÍTICA (qué se reserva online, qué ofrecer o no, condiciones,
  aclaraciones que aplican SIEMPRE). En `texto_propuesto` escribe la REGLA en UNA línea, lista
  para agregar al Conocimiento (general, no específica de un cliente).
- "tono": misma información, solo más cálida/breve/mejor redactada.
- "puntual": algo específico de ESE cliente, un saludo personalizado, o un typo. NO generaliza.

Responde SOLO un JSON válido, sin texto adicional ni explicaciones:
{{"tipo": "...", "texto_propuesto": "...", "ref_catalogo": "...", "motivo": "..."}}
Ante la duda entre regla y puntual, elige "puntual" (no ensuciar el Conocimiento)."""


def build_clasificador_user(borrador, enviado):
    """User prompt del clasificador. Pura."""
    return (
        'BORRADOR (lo que propuso el agente):\n'
        f'«{(borrador or "").strip()}»\n\n'
        'ENVIADO (lo que la persona realmente mandó al cliente):\n'
        f'«{(enviado or "").strip()}»\n\n'
        'Clasifica la corrección y responde solo el JSON.'
    )


def parse_clasificacion(texto):
    """Extrae y valida el JSON del clasificador. Pura. Devuelve dict normalizado."""
    crudo = (texto or '').strip()
    data = {}
    if crudo:
        # Tomar el primer bloque {...} por si el modelo agrega texto alrededor.
        m = re.search(r'\{.*\}', crudo, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except (ValueError, TypeError):
                data = {}
    tipo = str(data.get('tipo', '')).strip().lower()
    if tipo not in TIPOS:
        tipo = 'puntual'
    return {
        'tipo': tipo,
        'texto_propuesto': str(data.get('texto_propuesto', '')).strip()[:1000],
        'ref_catalogo': str(data.get('ref_catalogo', '')).strip()[:200],
        'motivo': str(data.get('motivo', '')).strip()[:300],
    }


def procesar_pendientes(limite=50):
    """Clasifica el feedback editado sin procesar y crea las sugerencias accionables.

    Lo usan el comando `procesar_aprendizaje` y el endpoint (H-013). Idempotente:
    marca `procesado=True` salvo en error del LLM (para reintentar). Lote acotado.
    Devuelve {procesados, creadas, errores, detalle:[...]}.
    """
    from .agent import get_config
    from .models import AgenteFeedback, SugerenciaAprendizaje

    config = get_config()
    pendientes = list(
        AgenteFeedback.objects.filter(editado=True, procesado=False)
        .order_by('created_at')[:max(1, int(limite or 50))]
    )
    procesados = creadas = errores = 0
    detalle = []
    for fb in pendientes:
        d = clasificar(config, fb.borrador, fb.enviado)
        if d.get('error'):
            errores += 1
            detalle.append({'feedback_id': fb.id, 'estado': 'error', 'error': d['error']})
            continue  # NO marcar procesado → se reintenta
        if d['tipo'] in TIPOS_ACCIONABLES:
            SugerenciaAprendizaje.objects.create(
                feedback=fb, phone=fb.phone, tipo=d['tipo'],
                texto_propuesto=d['texto_propuesto'], ref_catalogo=d['ref_catalogo'],
                motivo=d['motivo'], borrador=fb.borrador, enviado=fb.enviado,
                modelo=d.get('modelo', ''),
            )
            creadas += 1
            detalle.append({'feedback_id': fb.id, 'tipo': d['tipo'], 'texto': d['texto_propuesto'][:120]})
        else:
            detalle.append({'feedback_id': fb.id, 'tipo': d['tipo']})
        fb.procesado = True
        fb.save(update_fields=['procesado'])
        procesados += 1
    return {'procesados': procesados, 'creadas': creadas, 'errores': errores, 'detalle': detalle}


def clasificar(config, borrador, enviado):
    """Clasifica una corrección vía LLM. Devuelve dict (+'modelo','error'). No lanza."""
    from . import grounding
    from .agent import _modelo_efectivo

    base = {'tipo': 'puntual', 'texto_propuesto': '', 'ref_catalogo': '', 'motivo': '',
            'modelo': '', 'error': ''}

    if (borrador or '').strip() == (enviado or '').strip():
        base['motivo'] = 'sin cambios'
        return base

    try:
        catalogo = grounding.catalogo_vivo()
    except Exception as exc:  # noqa: BLE001
        logger.exception('Aprendizaje: error armando catálogo: %s', exc)
        catalogo = '(catálogo no disponible)'

    system = build_clasificador_system(catalogo, config.conocimiento)
    user = build_clasificador_user(borrador, enviado)
    modelo = _modelo_efectivo(config)

    try:
        from destino_puerto_varas.services.llm.openrouter_provider import OpenRouterProvider
        resultado = OpenRouterProvider().generate(
            system_prompt=system, user_prompt=user, model=modelo,
            max_tokens=300, temperature=0.0,  # determinista para clasificar
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('Aprendizaje: provider lanzó excepción: %s', exc)
        base['error'] = str(exc)[:200]
        return base

    if not resultado.ok:
        base['error'] = resultado.error[:200]
        base['modelo'] = modelo
        return base

    parsed = parse_clasificacion(resultado.text)
    parsed['modelo'] = modelo
    parsed['error'] = ''
    return parsed
