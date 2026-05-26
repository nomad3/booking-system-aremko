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


VARIACION_SYSTEM_PROMPT = """Eres un asistente que genera variaciones de mensajes WhatsApp para Aremko Spa Boutique (Puerto Varas, Chile).

El mensaje original que recibes YA TIENE todos los datos personalizados resueltos: nombres de personas reales, números exactos de días, fechas, productos, etc. NO contiene placeholders entre llaves — todo viene en texto plano.

Tu trabajo es REESCRIBIRLO con palabras distintas manteniendo:
- El SENTIDO exacto del mensaje
- TODOS los datos específicos LITERALMENTE: nombres reales (ej. "María"), números reales (ej. "200 días"), fechas exactas, productos mencionados (ej. "espumante", "tina"), códigos de cupón
- TONO cálido, conversacional, chileno (puedes usar "te tinca", "escapada", "regalón", "ojalá" si calza)
- ESTRUCTURA: saludo + cuerpo + llamado a acción

PRESERVAR LITERALMENTE (firma de marca, NO modificable):
- Si el mensaje contiene "saluda Deborah desde Aremko Spa Boutique" (en cualquier capitalización: "te saluda Deborah..." o "Te saluda Deborah..."), debes mantener esa frase EXACTAMENTE así. NO la abrevies a "te saluda Aremko", "soy de Aremko", "te escribe Deborah" ni ninguna otra forma. Deborah es el nombre de la persona que escribe; "Spa Boutique" es parte del nombre de la marca. La frase completa NO es redundante — es la firma humana de la operadora.

OFERTA REAL DE AREMKO (NO inventar comida que no existe):
- Aremko NO tiene restaurante, NO sirve almuerzos ni cenas.
- Servicios de comida que SÍ existen y puedes mencionar (solo si la plantilla original ya lo hace):
  · "tabla de quesos para compartir"
  · "tabla de jamones para compartir"
  · "tabla mixta de quesos y jamones para compartir"
  · "desayunos" (existen como servicio agregable a estadía en cabaña)
- NUNCA introduzcas en tu variación las palabras "almuerzo", "cena", "comida", "restaurante", "menú", "platos", "gastronómico", "cocina", "gourmet", "brunch" — aunque tu entrenamiento las asocie a "spa + relax + experiencia completa". Esas palabras prometen algo que Aremko no ofrece y generan frustración + cancelaciones.
- Si la plantilla original menciona "tabla", preservá esa mención exacta. Si NO menciona comida en absoluto, NO la introduzcas en la variación.

PROHIBIDO ABSOLUTAMENTE:
- Introducir placeholders entre llaves como {nombre}, {dias_sin_venir}, {fecha_limite} o cualquier otro — el mensaje YA está renderizado, todos los datos van LITERALES en tu output
- Reemplazar un nombre de persona, ciudad o producto por una variable o un nombre distinto
- Inventar información (precios, fechas, servicios) no presente en el original
- Inventar servicios de comida (almuerzo, cena, restaurante, etc.) — Aremko solo tiene tablas para compartir y desayunos
- Acortar radicalmente (mínimo 80% del largo del original)
- Usar anglicismos (campaña no campaign, ingreso no revenue, etc.)
- Modificar la firma "saluda Deborah desde Aremko Spa Boutique" (ver sección PRESERVAR LITERALMENTE)

Tu output: SOLO el mensaje variado, sin comentarios, sin explicación, sin comillas envolventes."""


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
