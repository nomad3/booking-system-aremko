"""
Análisis IA de encuestas de satisfacción usando OpenRouter (Claude/GPT).

Tarea 1.4 Fase C del plan maestro: cada lunes 9 AM Chile, este módulo
agrega las encuestas de la semana, las pasa a un LLM con un prompt
estructurado, y devuelve un dict con:

- resumen_ejecutivo (str)
- nps_score (int)
- alertas_operativas (list[dict]) - urgentes, requieren acción operativa
- oportunidades_comerciales (list[dict]) - segmentos / pricing / packs
- ideas_marketing (list[dict]) - frases reales para usar en redes
- followups_urgentes (list[dict]) - clientes que requieren contacto

Usado por: ventas/management/commands/analyze_surveys_weekly.py
"""
import json
import logging
from datetime import timedelta
from collections import Counter

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres un analista experto en customer success y operaciones \
de spa boutique. Tu trabajo es leer encuestas de satisfacción de clientes de \
Aremko Spa Boutique (Puerto Varas, Chile) y generar un reporte ejecutivo \
semanal con foco en acciones concretas para mejorar el negocio.

CONTEXTO de Aremko:
- Spa boutique con 3 servicios: tinas calientes, masajes, alojamiento (5 cabañas)
- Posicionamiento: "experiencia 3-en-1: masaje + tina + cabaña en bosque nativo"
- Garantía única en Puerto Varas: si la tina llega a 37°C o menos, es gratis
- 48 paneles solares + aerotermia (no usan leña)
- Junto al Río Pescado, a 20 min del centro de Puerto Varas
- Pack completo desde $190.000 para 2 personas

VOZ DE MARCA: honesta, sin marketing inflado. NO usar palabras como "experiencia única", \
"magia", "momentos inolvidables" en mayúscula.

Tu output DEBE ser JSON estricto con la estructura especificada en el user prompt. \
Sé específico, cita comentarios textuales cuando sea relevante, y prioriza \
acciones concretas sobre observaciones genéricas."""


def build_user_prompt(stats: dict, encuestas_data: list) -> str:
    """Construye el prompt user con stats agregados + texto de las encuestas."""

    # Limitar texto libre a 800 chars por encuesta para no inflar tokens
    encuestas_serializadas = []
    for e in encuestas_data[:80]:  # tope hard 80 encuestas para evitar costos altos
        item = {
            'fecha': e['fecha'],
            'nps': e.get('nps'),
            'cal_general': e.get('cal_experiencia_general'),
            'cal_calidad_precio': e.get('cal_calidad_precio'),
            'cal_temp_tina': e.get('cal_temperatura_tina'),
            'cal_atencion': e.get('cal_atencion_visita'),
            'cal_masajes': e.get('cal_servicio_masajes'),
            'servicios': e.get('servicios') or [],
            'ocasion': e.get('ocasion'),
            'como_se_entero': e.get('como_se_entero'),
        }
        if e.get('lo_que_mas_gusto'):
            item['lo_que_mas_gusto'] = e['lo_que_mas_gusto'][:800]
        if e.get('sugerencias'):
            item['sugerencias'] = e['sugerencias'][:800]
        if e.get('decepcion'):
            item['decepcion'] = e['decepcion'][:800]
        if e.get('contacto_disponible'):
            item['contacto_disponible'] = True
        encuestas_serializadas.append(item)

    return f"""Analiza las siguientes encuestas de satisfacción de Aremko de la última semana.

=== STATS AGREGADOS ===
{json.dumps(stats, indent=2, ensure_ascii=False, default=str)}

=== ENCUESTAS (anonimizadas para análisis) ===
{json.dumps(encuestas_serializadas, indent=2, ensure_ascii=False, default=str)}

=== TU OUTPUT (JSON estricto, sin markdown, sin código fences) ===

Devuelve EXACTAMENTE este formato:
{{
  "resumen_ejecutivo": "2-3 frases en español sobre el panorama de la semana. Mencionar NPS y tendencias clave.",
  "nps_calculado": <int 0-100, NPS = %promotores - %detractores>,
  "alertas_operativas": [
    {{
      "titulo": "Frase corta del problema",
      "descripcion": "Detalle específico, citando comentarios textuales si los hay",
      "evidencia_count": <int, cuántas encuestas mencionan esto>,
      "prioridad": "alta|media|baja",
      "accion_sugerida": "Qué hacer concretamente esta semana"
    }}
  ],
  "oportunidades_comerciales": [
    {{
      "titulo": "Frase corta de la oportunidad",
      "descripcion": "Insight específico (ej: segmento, pack, precio)",
      "accion_sugerida": "Qué probar"
    }}
  ],
  "ideas_marketing": [
    {{
      "tipo": "post|reel|carrusel|story|email",
      "frase_real_cliente": "Cita textual de algún comentario del cliente",
      "como_usarla": "Sugerencia concreta de cómo convertirla en contenido"
    }}
  ],
  "followups_urgentes_count": <int, cuántas encuestas con NPS<=6 o calificaciones críticas merecen contacto>,
  "metricas_clave": {{
    "promedio_calidad_precio": <float|null>,
    "promedio_temperatura_tina": <float|null>,
    "promedio_atencion": <float|null>,
    "cliente_recurrente_pct": <float, % que dijeron 'soy_cliente' en cómo_se_enteró>
  }}
}}

REGLAS:
- Si hay menos de 5 encuestas en la semana, igual generar reporte pero con tono "muestra pequeña"
- Máximo 5 items por lista (alertas, oportunidades, ideas)
- Las "ideas_marketing" SIEMPRE deben citar texto real del cliente, no inventar
- Si no hay alertas operativas (todo bien), devolver lista vacía []
- Tono profesional pero directo, sin relleno
- IMPORTANTE: solo JSON válido, sin texto adicional ni markdown"""


def aggregate_stats(encuestas_qs):
    """Calcula stats agregados de un queryset de EncuestaSatisfaccion."""
    total = encuestas_qs.count()
    if total == 0:
        return None

    from django.db.models import Avg

    nps_qs = encuestas_qs.exclude(nps_score__isnull=True)
    nps_total = nps_qs.count()
    promotores = nps_qs.filter(nps_score__gte=9).count()
    pasivos = nps_qs.filter(nps_score__gte=7, nps_score__lte=8).count()
    detractores = nps_qs.filter(nps_score__lte=6).count()

    nps = None
    if nps_total > 0:
        nps = round(100 * promotores / nps_total - 100 * detractores / nps_total, 1)

    aggs = encuestas_qs.aggregate(
        avg_general=Avg('cal_experiencia_general'),
        avg_calidad_precio=Avg('cal_calidad_precio'),
        avg_temp_tina=Avg('cal_temperatura_tina'),
        avg_atencion=Avg('cal_atencion_visita'),
        avg_masajes=Avg('cal_servicio_masajes'),
    )

    como_se_entero = Counter()
    ocasiones = Counter()
    for e in encuestas_qs.values('como_se_entero', 'ocasion_visita'):
        if e['como_se_entero']:
            como_se_entero[e['como_se_entero']] += 1
        if e['ocasion_visita']:
            ocasiones[e['ocasion_visita']] += 1

    return {
        'total_encuestas': total,
        'nps_score': nps,
        'distribucion_nps': {
            'promotores': promotores,
            'pasivos': pasivos,
            'detractores': detractores,
            'sin_nps': total - nps_total,
        },
        'promedios': {
            k: round(v, 2) if v is not None else None
            for k, v in aggs.items()
        },
        'como_se_entero': dict(como_se_entero.most_common(5)),
        'ocasiones': dict(ocasiones.most_common(5)),
        'requieren_followup': encuestas_qs.filter(
            requiere_followup=True, followup_completado=False
        ).count(),
    }


def serialize_encuestas(encuestas_qs):
    """Convierte queryset a lista de dicts para el LLM."""
    data = []
    for e in encuestas_qs.iterator():
        item = {
            'fecha': e.fecha_respuesta.strftime('%Y-%m-%d') if e.fecha_respuesta else None,
            'nps': e.nps_score,
            'cal_experiencia_general': e.cal_experiencia_general,
            'cal_calidad_precio': e.cal_calidad_precio,
            'cal_temperatura_tina': e.cal_temperatura_tina,
            'cal_atencion_visita': e.cal_atencion_visita,
            'cal_servicio_masajes': e.cal_servicio_masajes,
            'servicios': e.servicios_contratados or [],
            'ocasion': e.ocasion_visita,
            'como_se_entero': e.como_se_entero,
            'lo_que_mas_gusto': e.lo_que_mas_gusto or '',
            'sugerencias': e.sugerencias or '',
            'decepcion': e.decepcion or '',
            'contacto_disponible': bool(
                e.contacto_email or e.contacto_telefono
                or (e.cliente and (e.cliente.email or e.cliente.telefono))
            ),
        }
        data.append(item)
    return data


def call_llm(stats: dict, encuestas_data: list, model: str = None) -> dict:
    """Llama a OpenRouter con el prompt estructurado.

    Retorna dict con el análisis. Levanta excepción si falla.
    """
    from openai import OpenAI

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    if not api_key:
        raise ValueError('OPENROUTER_API_KEY no configurada')

    model = model or getattr(settings, 'SURVEY_ANALYSIS_LLM_MODEL', 'anthropic/claude-sonnet-4.6')

    client = OpenAI(api_key=api_key, base_url=base_url)
    user_prompt = build_user_prompt(stats, encuestas_data)

    logger.info(f'Llamando a {model} para análisis semanal de encuestas')

    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0.3,
        max_tokens=4000,
        response_format={'type': 'json_object'},
    )

    raw = response.choices[0].message.content or ''
    # Strip markdown fences si el LLM las agrega (defensivo)
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()
    try:
        analisis = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f'LLM no devolvió JSON válido: {e}. Raw[:500]: {raw[:500]}')
        raise ValueError(f'LLM response no es JSON válido: {e}')

    return analisis


def analyze_week(days: int = 7, end_date=None) -> dict:
    """Punto de entrada principal. Analiza encuestas de los últimos `days` días.

    Retorna dict con:
    - 'periodo_inicio', 'periodo_fin'
    - 'stats' (agregados)
    - 'analisis' (output del LLM)
    - 'encuestas_qs_count'
    - 'sin_data' (bool, True si no hay encuestas)
    """
    from ventas.models import EncuestaSatisfaccion

    if end_date is None:
        end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    encuestas_qs = EncuestaSatisfaccion.objects.filter(
        fecha_respuesta__gte=start_date,
        fecha_respuesta__lte=end_date,
    ).select_related('cliente')

    total = encuestas_qs.count()

    if total == 0:
        return {
            'periodo_inicio': start_date,
            'periodo_fin': end_date,
            'sin_data': True,
            'encuestas_qs_count': 0,
        }

    stats = aggregate_stats(encuestas_qs)
    encuestas_data = serialize_encuestas(encuestas_qs)
    analisis = call_llm(stats, encuestas_data)

    return {
        'periodo_inicio': start_date,
        'periodo_fin': end_date,
        'sin_data': False,
        'encuestas_qs_count': total,
        'stats': stats,
        'analisis': analisis,
    }


def get_followups_pendientes(days: int = 7):
    """Lista encuestas que requieren follow-up urgente, no completadas.

    Útil para incluir en el reporte semanal con datos de contacto.
    """
    from ventas.models import EncuestaSatisfaccion

    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    return EncuestaSatisfaccion.objects.filter(
        fecha_respuesta__gte=start_date,
        fecha_respuesta__lte=end_date,
        requiere_followup=True,
        followup_completado=False,
    ).select_related('cliente').order_by('nps_score', '-fecha_respuesta')
