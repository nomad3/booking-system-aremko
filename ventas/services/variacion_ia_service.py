"""
variacion_ia_service
====================

Genera variaciones de mensajes WhatsApp usando LLM (Gemini Flash Lite vía
OpenRouter) para evitar que múltiples clientes reciban exactamente el mismo
texto — reduce el riesgo de detección anti-spam y suena menos robótico.

Diseño on-demand (NO batch):
  - Se llama cuando el endpoint /siguiente/ carga un contacto
  - Toggle global vía settings.OVC_USAR_VARIACIONES_IA (default False)
  - Timeout corto (3s default); si tarda más, fallback a None
  - Si LLM falla por cualquier razón (timeout, 401, vacío, exception),
    devuelve None y el caller usa el mensaje_renderizado original

Costo estimado: ~$4/mes con Gemini Flash Lite a 50 envíos/día.

Uso:
    from ventas.services.variacion_ia_service import generar_variacion_mensaje

    variado = generar_variacion_mensaje(contacto.mensaje_renderizado)
    # variado es str si funcionó, None si fallback
"""

from __future__ import annotations

import logging
from typing import Optional


logger = logging.getLogger(__name__)


VARIACION_SYSTEM_PROMPT = """Eres un asistente que genera variaciones de mensajes WhatsApp para un spa boutique chileno (Aremko, Puerto Varas).

Reglas estrictas (no negociables):
- Mantén el SENTIDO exacto del mensaje original
- Mantén el TONO cálido, conversacional, chileno (puedes usar "te tinca", "escapada", "regalón" si aplica)
- Mantén la ESTRUCTURA: saludo + cuerpo + llamado a acción
- PRESERVA EXACTAMENTE los placeholders entre llaves: {nombre}, {dias_sin_venir}, {ultimo_servicio}, {servicio_recomendado}, {sugerencia_dia}, {sugerencia_hora}, {cupon_codigo}, {mes_proximo}, {fecha_limite}, {ultima_visita_humanizada}
- NO inventes información (precios, fechas, servicios) no presente en el original
- NO acortes radicalmente (mínimo 80% del largo original)
- NO uses anglicismos (campaña no campaign, ingreso no revenue, etc.)
- Tu output: SOLO el mensaje variado, sin comentarios, sin explicación"""


def generar_variacion_mensaje(mensaje_original: str) -> Optional[str]:
    """Llama a OpenRouter para variar el mensaje WhatsApp.

    Args:
        mensaje_original: texto ya renderizado con placeholders resueltos.

    Returns:
        str con el mensaje variado si todo OK.
        None si:
          - Setting OVC_USAR_VARIACIONES_IA = False
          - OPENROUTER_API_KEY no configurada
          - openai SDK no instalado
          - LLM timeout, 401, error de red, respuesta vacía
          - Excepción cualquiera

    El caller hace fallback a mensaje_original cuando recibe None.

    Side effects:
      - logger.warning si LLM falla (para monitoreo). NO loggea contenido del
        mensaje (puede contener PII), solo el tipo de error.
    """
    from django.conf import settings

    # ---- Gate por toggle ----
    if not getattr(settings, 'OVC_USAR_VARIACIONES_IA', False):
        return None

    if not mensaje_original or not mensaje_original.strip():
        return None

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        logger.warning("OVC variación IA activa pero OPENROUTER_API_KEY ausente")
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("OVC variación IA: openai SDK no instalado")
        return None

    timeout = getattr(settings, 'OVC_VARIACION_TIMEOUT_SECONDS', 3)
    model = getattr(settings, 'OVC_VARIACION_LLM_MODEL', 'google/gemini-2.0-flash-lite-001')
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': VARIACION_SYSTEM_PROMPT},
                {'role': 'user',
                 'content': f'Mensaje original:\n{mensaje_original}\n\nGenera UNA variación natural:'},
            ],
            temperature=0.7,
            max_tokens=400,
        )
        variado = (response.choices[0].message.content or '').strip()
        if not variado:
            logger.warning("OVC variación IA: respuesta vacía del LLM")
            return None
        return variado
    except Exception as exc:
        # Captura timeout, 401, network errors, malformed response, etc.
        logger.warning(f"OVC variación IA falló ({type(exc).__name__}): {exc}")
        return None
