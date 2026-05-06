"""
Procesamiento IA de reviews externas (Google Maps, TripAdvisor).

Tarea 2.8 fase 2 plan maestro. Dos funciones:
- extract_from_screenshot(): lee imagen multimodal y extrae autor/fecha/rating/texto/idioma
- generate_response(): genera respuesta lista para publicar según rating

Usado por: ventas/admin.py (botones del ReviewAdmin)
"""
import base64
import json
import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


SYSTEM_EXTRACT = """Eres un asistente que extrae datos estructurados de \
screenshots de reviews de Google Maps o TripAdvisor sobre Aremko Spa Boutique.

Tu output es JSON estricto con esta estructura:
{
  "autor": "Nombre del autor que aparece arriba del review",
  "fecha_review": "YYYY-MM-DD",
  "rating": <int del 1 al 5>,
  "texto": "Texto completo del comentario. Si solo dejó estrellas sin texto, devolver string vacío.",
  "idioma": "es | en | pt | otro"
}

Reglas:
- Cuenta las estrellas visualmente: 5 estrellas llenas = rating 5
- Para fechas relativas ("hace 3 días", "hace 1 mes", "hace 2 años"), calcular la fecha exacta sabiendo que HOY es {fecha_actual}
- Si no puedes detectar algún campo con seguridad, devolver null en ese campo
- Si la imagen NO es un review (no tiene estrellas ni autor visible), devolver {"error": "no es un review válido"}
- NO incluir texto fuera del JSON, ni markdown, ni explicaciones"""


SYSTEM_RESPOND_POSITIVO = """Eres parte del equipo de Aremko Spa Boutique \
(Puerto Varas, Chile) respondiendo a un review POSITIVO (4-5 estrellas) de \
un cliente.

Voz: cercana, agradecida, sin marketing inflado, primera persona del plural \
("agradecemos", "esperamos verte de vuelta"). NUNCA usar palabras como \
"experiencia única", "magia", "momentos inolvidables".

Estructura de la respuesta:
1. Agradecimiento que mencione algo específico de lo que el cliente destacó \
   (si dejó solo estrellas sin texto, agradecer la calificación general)
2. Invitación natural a volver
3. Cerrar con "Saludos, equipo Aremko" o equivalente

Largo: 200-350 caracteres. NO firmar con nombre propio.

Idioma de respuesta: el mismo del review (es / en / pt).

Output: SOLO el texto de la respuesta, sin comillas, sin "Respuesta:", sin nada \
extra antes o después."""


SYSTEM_RESPOND_NEGATIVO = """Eres parte del equipo de Aremko Spa Boutique \
(Puerto Varas, Chile) respondiendo a un review NEGATIVO (1-3 estrellas) de \
un cliente.

Voz: humilde, empática, sin defensividad. NUNCA justificar, contradecir ni \
minimizar lo que el cliente sintió.

Estructura de la respuesta:
1. Empatía genuina: reconocer que la experiencia no fue la esperada
2. Disculpas específicas por lo mencionado (si dejó solo estrellas sin texto, \
   disculparse de forma general por no haber cumplido sus expectativas)
3. Ofrecer canal directo para hablar: WhatsApp +56 9 5790 2525 (textual)
4. Cierre breve invitando al contacto directo

Largo: 250-450 caracteres. NO firmar con nombre propio. NO defender Aremko, \
NO justificar, NO mencionar políticas.

Idioma de respuesta: el mismo del review (es / en / pt).

Output: SOLO el texto de la respuesta, sin comillas, sin etiquetas, sin nada \
extra antes o después."""


def _strip_fences(raw: str) -> str:
    """Quita fences ``` de respuestas LLM si las agrega."""
    raw = (raw or '').strip()
    if not raw.startswith('```'):
        return raw
    lines = raw.split('\n')
    lines = lines[1:]
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    return '\n'.join(lines).strip()


def _llm_client():
    from openai import OpenAI
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    if not api_key:
        raise ValueError('OPENROUTER_API_KEY no configurada')
    return OpenAI(api_key=api_key, base_url=base_url)


def _image_to_base64(image_field) -> str:
    """Lee un ImageField y devuelve la imagen en base64 (para data URL)."""
    image_field.open('rb')
    try:
        data = image_field.read()
        return base64.b64encode(data).decode('utf-8')
    finally:
        image_field.close()


def _detect_image_mime(image_field) -> str:
    """Detecta MIME type del archivo según extensión. Default png."""
    name = (getattr(image_field, 'name', '') or '').lower()
    if name.endswith('.jpg') or name.endswith('.jpeg'):
        return 'image/jpeg'
    if name.endswith('.webp'):
        return 'image/webp'
    if name.endswith('.gif'):
        return 'image/gif'
    return 'image/png'


def extract_from_screenshot(image_field, fuente: str) -> dict:
    """Llama LLM multimodal con el screenshot y extrae datos del review.

    Retorna dict con: autor, fecha_review (str ISO), rating (int), texto, idioma.
    Levanta excepción si el LLM falla o si la respuesta no es JSON válido.
    Si el LLM detecta que la imagen no es un review, retorna {"error": "..."}.
    """
    model = getattr(settings, 'REVIEW_EXTRACTION_LLM_MODEL', 'anthropic/claude-sonnet-4.6')

    fecha_actual = timezone.localdate().isoformat()
    system = SYSTEM_EXTRACT.replace('{fecha_actual}', fecha_actual)

    image_b64 = _image_to_base64(image_field)
    mime = _detect_image_mime(image_field)

    client = _llm_client()
    logger.info(f'Llamando a {model} para extracción de review ({fuente})')
    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': [
                {'type': 'text',
                 'text': f'Extrae los datos de este review de {fuente}. Output JSON estricto.'},
                {'type': 'image_url',
                 'image_url': {'url': f'data:{mime};base64,{image_b64}'}},
            ]},
        ],
        temperature=0.0,
        max_tokens=1000,
        response_format={'type': 'json_object'},
    )
    raw = response.choices[0].message.content or ''
    cleaned = _strip_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(f'LLM extract no devolvió JSON válido. Raw[:300]: {raw[:300]}')
        raise ValueError(f'Respuesta IA no es JSON válido: {exc}')
    return data


def generate_response(rating: int, texto: str, idioma: str = 'es', autor: str = '') -> str:
    """Genera la respuesta sugerida según el rating del review.

    1-3 estrellas: empatía + disculpas + canal directo WhatsApp.
    4-5 estrellas: agradecer + invitar a volver.
    """
    if rating is None:
        raise ValueError('No se puede generar respuesta sin rating')

    if rating <= 3:
        system = SYSTEM_RESPOND_NEGATIVO
    else:
        system = SYSTEM_RESPOND_POSITIVO

    model = getattr(settings, 'REVIEW_RESPONSE_LLM_MODEL', 'anthropic/claude-sonnet-4.6')

    user_prompt = f"""Datos del review al que respondes:
- Autor: {autor or '(no especificado)'}
- Rating: {rating} de 5 estrellas
- Idioma del review: {idioma}
- Texto del review: {texto.strip() if texto else '(solo dejó estrellas, sin comentario escrito)'}

Genera la respuesta apropiada siguiendo las reglas del system prompt."""

    client = _llm_client()
    logger.info(f'Llamando a {model} para generar respuesta a review {rating}★')
    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0.5,
        max_tokens=600,
    )
    return (response.choices[0].message.content or '').strip()
