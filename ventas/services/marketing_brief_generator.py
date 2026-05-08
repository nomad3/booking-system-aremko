"""
Generador del brief semanal de marketing (Tarea 2.4 plan maestro).

Cada lunes 10 AM Chile, este módulo genera un brief listo para Jorge con:
- Calendario de la semana (publicaciones por canal y día)
- Drafts concretos: GBP, Reel #1, carrusel IG, Reel #2, email engaged
- Recordatorio de stories diarias
- Frases reales de clientes promotores para inspirar contenido
- Alertas y oportunidades del análisis IA semanal anterior

Lee como context:
- docs/MARKETING_PLAYBOOK.md (voz, personas, cadencia, hooks Víctor Eras)
- docs/AREMKO_RECURRING_TASKS.md (calendario operativo)

Usado por: ventas/management/commands/generate_weekly_marketing_brief.py
"""
import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _read_doc(rel_path: str) -> str:
    """Lee un .md del repo como string. Devuelve '' si no existe."""
    try:
        base_dir = Path(settings.BASE_DIR)
        full = base_dir / rel_path
        if not full.exists():
            return ''
        return full.read_text(encoding='utf-8')
    except Exception as exc:
        logger.warning(f'No se pudo leer {rel_path}: {exc}')
        return ''


SYSTEM_PROMPT = """Eres el director de marketing de Aremko Spa Boutique \
(Puerto Varas, Chile). Cada lunes generas un brief operativo con drafts \
listos para que Jorge solo copie/pegue y publique durante la semana.

CONTEXTO MAESTRO: el playbook que se incluye en el user prompt es la única \
fuente de verdad sobre voz de marca, buyer personas, cadencia, frases ancla, \
hooks de Víctor Eras y palabras prohibidas. Respétalo siempre.

REGLAS DE PRODUCCIÓN DE COPY:
- Voz Aremko: honesta, específica, sin marketing inflado
- NUNCA usar "experiencia única", "magia", "momentos inolvidables" en mayúscula
- Frases ancla a usar cuando aplique: "2 días aquí equivalen a una semana de vacaciones", "no usamos leña", "37°C o menos = gratis", "a metros del río Pescado"
- Para Reels: estructura 5 partes (gancho 4-7s · contexto · moraleja · solución · CTA con palabra clave)
- Citar texto real del cliente cuando esté disponible (mejor que copy inventado)
- UTMs siempre en links: el playbook tiene la convención

FORMATO DE OUTPUT: JSON estricto sin markdown ni texto adicional. \
Estructura especificada en el user prompt."""


def build_user_prompt(
    semana_inicio,
    semana_fin,
    playbook: str,
    recurring_tasks: str,
    frases_clientes: list,
    blog_posts_recientes: list,
    alertas_analisis_ia: Optional[dict],
    ga4_snapshot: Optional[dict] = None,
    gsc_snapshot: Optional[dict] = None,
    meta_snapshot: Optional[dict] = None,
) -> str:
    """Construye el user prompt con toda la info contextual."""

    return f"""Genera el brief de marketing para la semana del {semana_inicio.strftime('%d %b %Y')} al {semana_fin.strftime('%d %b %Y')}.

=== PLAYBOOK MAESTRO (tu fuente de verdad) ===
{playbook[:8000]}

=== CADENCIA OPERATIVA (qué se publica cada día) ===
{recurring_tasks[:3000]}

=== FRASES REALES DE CLIENTES PROMOTORES (últimos 30 días) ===
{json.dumps(frases_clientes[:15], indent=2, ensure_ascii=False)}

=== BLOG POSTS RECIENTES (no repetir temas, sí reciclar conceptos) ===
{json.dumps(blog_posts_recientes, indent=2, ensure_ascii=False, default=str)}

=== ANÁLISIS IA SEMANA PASADA (insights operativos a aprovechar) ===
{json.dumps(alertas_analisis_ia, indent=2, ensure_ascii=False) if alertas_analisis_ia else '(no disponible)'}

=== GA4 (sitio web aremko.cl) — ÚLTIMOS 7 DÍAS vs 7 ANTERIORES ===
{json.dumps(ga4_snapshot, indent=2, ensure_ascii=False, default=str) if ga4_snapshot else '(no disponible)'}

=== GOOGLE SEARCH CONSOLE (búsqueda orgánica) — ÚLTIMOS 7 DÍAS vs 7 ANTERIORES ===
{json.dumps(gsc_snapshot, indent=2, ensure_ascii=False, default=str) if gsc_snapshot else '(no disponible)'}

=== META: FACEBOOK + INSTAGRAM ORGÁNICO + ADS HISTORY (últimos 28 días) ===
{json.dumps(meta_snapshot, indent=2, ensure_ascii=False, default=str)[:6000] if meta_snapshot else '(no disponible — token Meta no configurado o falló la captura)'}

=== TU OUTPUT (JSON estricto) ===

{{
  "resumen_semana": "2-3 frases sobre el foco de la semana, qué amplificar, qué evitar",
  "calendario": [
    {{"dia": "Lunes", "fecha": "DD/MM", "publicaciones": [
      {{"canal": "GBP", "hora": "10:30", "tipo": "post novedad", "estado": "draft listo abajo"}}
    ]}},
    {{"dia": "Martes", "fecha": "DD/MM", "publicaciones": [
      {{"canal": "Instagram", "hora": "18:00", "tipo": "Reel", "estado": "guion abajo"}}
    ]}}
  ],
  "drafts": {{
    "gbp_post": {{
      "texto": "Copy listo para pegar (max 1500 chars)",
      "url_cta": "URL con UTM aplicado",
      "foto_sugerida": "Descripción de la foto a usar"
    }},
    "reel_martes": {{
      "concepto": "Idea ganadora en 1 frase",
      "filtro_5_50": "explicar por qué pasa el filtro Víctor Eras (simple para 5 años + atrae a 50/100)",
      "guion": [
        {{"bloque": "gancho_5s", "texto": "Frase exacta a decir o mostrar"}},
        {{"bloque": "contexto_15s", "texto": "..."}},
        {{"bloque": "moraleja_10s", "texto": "..."}},
        {{"bloque": "solucion_5s", "texto": "..."}},
        {{"bloque": "cta_palabra_clave", "texto": "Comenta TINAS y te paso..."}}
      ],
      "tomas_sugeridas": ["Toma 1: ...", "Toma 2: ..."],
      "hashtags": ["#hashtag1", "#hashtag2", "..."]
    }},
    "carrusel_miercoles": {{
      "concepto": "...",
      "slides": [
        {{"numero": 1, "imagen_sugerida": "...", "texto_overlay": "...", "caption_solo_si_aplica": ""}}
      ],
      "caption_completo": "Caption del post completo"
    }},
    "reel_jueves": {{
      "concepto": "Variación del Reel del martes si pasa RI 50%, o idea nueva",
      "guion": [],
      "tomas_sugeridas": [],
      "hashtags": []
    }},
    "email_engaged": {{
      "necesario_esta_semana": true,
      "asunto": "...",
      "preheader": "...",
      "cuerpo_texto_plano": "..."
    }}
  }},
  "stories_diarias": [
    {{"dia": "Lunes", "concepto": "...", "tipo": "detrás de escena|datos del día|naturaleza|cliente real|recordatorio práctico"}},
    {{"dia": "Martes", "concepto": "...", "tipo": "..."}}
  ],
  "recordatorios": ["Lista de cosas a no olvidar esta semana"],
  "metricas_a_revisar_viernes": ["Lista de métricas para evaluar al cierre de semana"],
  "analisis_metricas_semana": {{
    "resumen_trafico": "2-3 frases sobre GA4: sesiones, usuarios, conversiones, comparado a semana anterior. Si hay caída/subida fuerte, mencionar causa probable.",
    "top_insights_ga4": [
      "Insight 1: dato concreto + interpretación (ej: 'WhatsApp clicks subieron 35% pero phone_clicks cayó 50%, posible drop en visibilidad del CTA telefónico móvil')"
    ],
    "top_insights_gsc": [
      "Insight 1: query/página con cambio relevante (ej: 'tina caliente puerto varas escaló de pos 8 a pos 4, urgente reforzar contenido en /tinas/')"
    ],
    "acciones_de_metricas": [
      "Acción concreta sugerida basada en datos (ej: 'crear post GBP esta semana con keyword tina caliente puerto varas porque GSC muestra que es la query nº1 con CTR bajo')"
    ],
    "insights_meta_organico": [
      "Insight sobre Facebook orgánico (alcance/engagement de la página, top posts del periodo) si meta_snapshot está disponible"
    ],
    "insights_meta_instagram": [
      "Insight sobre Instagram orgánico (followers, alcance, top media) si meta_snapshot está disponible"
    ],
    "insights_meta_ads": [
      "Insight del histórico de campañas paid (39 campañas Aremko) si meta_snapshot está disponible. Si actualmente no hay campañas activas, mencionarlo y sugerir si conviene reactivar."
    ]
  }}
}}

REGLAS DE GENERACIÓN:
- Si la frase ancla 2-días-equivalen no se usó la semana anterior, incluirla en algún draft
- Si hay alerta operativa pendiente del análisis IA pasado, evitar contenido que la contradiga
- Si una frase real de cliente promotor calza con el tipo de Reel, USARLA literal (mejor que inventar)
- Si Email engaged no se justifica esta semana (poco contenido nuevo), poner necesario_esta_semana: false
- Mantener concretitud: nada de "publicar contenido relevante", siempre un draft con copy real
- Si GA4/GSC no están disponibles, dejar analisis_metricas_semana con strings que digan "(sin datos esta semana)"
- Las acciones de métricas deben ser específicas: nombrar la página, query o evento concreto"""


def get_frases_clientes_promotores(days: int = 30) -> list:
    """Trae frases reales de clientes con NPS>=9 (promotores) últimos N días.

    Útil como insumo para drafts de Reels/posts (citas auténticas pesan más
    que copy inventado).
    """
    from ventas.models import EncuestaSatisfaccion

    cutoff = timezone.now() - timedelta(days=days)
    qs = EncuestaSatisfaccion.objects.filter(
        nps_score__gte=9,
        fecha_respuesta__gte=cutoff,
    ).exclude(lo_que_mas_gusto='').exclude(lo_que_mas_gusto__isnull=True)

    frases = []
    for e in qs[:50]:
        texto = (e.lo_que_mas_gusto or '').strip()
        if 10 <= len(texto) <= 600:
            frases.append({
                'texto': texto,
                'fecha': e.fecha_respuesta.strftime('%Y-%m-%d') if e.fecha_respuesta else None,
                'nps': e.nps_score,
                'servicios': e.servicios_contratados or [],
            })
    return frases


def get_blog_posts_recientes(limit: int = 5) -> list:
    """Lista los últimos N blog posts publicados."""
    try:
        from aremko_blog.models import BlogPost
        qs = BlogPost.objects.filter(is_published=True).order_by('-published_at')[:limit]
        return [
            {
                'title': p.title,
                'slug': p.slug,
                'published_at': p.published_at.strftime('%Y-%m-%d') if p.published_at else None,
            }
            for p in qs
        ]
    except Exception as exc:
        logger.warning(f'No se pudieron cargar blog posts: {exc}')
        return []


def _strip_markdown_fences(raw: str) -> str:
    """Quita fences ```json ... ``` si el LLM las agregó.

    Algunos modelos en OpenRouter no respetan response_format=json_object al 100%
    y devuelven el JSON envuelto en markdown. Este helper lo limpia antes de json.loads.
    """
    raw = raw.strip()
    if not raw.startswith('```'):
        return raw
    lines = raw.split('\n')
    # Quitar primera línea (```json o ```)
    lines = lines[1:]
    # Quitar última línea si es ```
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    return '\n'.join(lines).strip()


def get_alertas_analisis_ia_anterior() -> Optional[dict]:
    """Devuelve el último análisis IA de encuestas para que el brief lo considere.

    Por ahora retorna None (no persistimos el análisis previo en BD).
    Si en futuro se persiste, devolver dict con resumen + alertas + ideas.
    """
    return None


def get_ga4_snapshot_safe() -> Optional[dict]:
    """Trae snapshot GA4 si está configurado, devuelve None si falla todo."""
    try:
        from .ga4_reporter import get_full_snapshot
        snap = get_full_snapshot()
        # Si todas las secciones fallaron, devolver None
        if snap.get('errors') and not snap.get('overview'):
            logger.warning(f'GA4 snapshot vacío. Errores: {snap["errors"]}')
            return None
        return snap
    except Exception as exc:
        logger.warning(f'GA4 snapshot no disponible: {exc}')
        return None


def get_gsc_snapshot_safe() -> Optional[dict]:
    """Trae snapshot GSC si está configurado, devuelve None si falla todo."""
    try:
        from .gsc_reporter import get_full_snapshot
        snap = get_full_snapshot()
        if snap.get('errors') and not snap.get('overview'):
            logger.warning(f'GSC snapshot vacío. Errores: {snap["errors"]}')
            return None
        return snap
    except Exception as exc:
        logger.warning(f'GSC snapshot no disponible: {exc}')
        return None


def get_meta_snapshot_safe(persist: bool = True) -> Optional[dict]:
    """Trae snapshot Meta (FB + IG + Ads) y opcionalmente lo persiste en BD.

    Args:
        persist: si True, guarda un MetaSnapshot con generado_por='cron_weekly'.

    Devuelve None si falla todo.
    """
    try:
        from .meta_reporter import get_snapshot_safe
        snap = get_snapshot_safe(days=28)
        if snap is None:
            logger.warning('Meta snapshot no disponible (token o conectividad)')
            return None

        if persist:
            try:
                from ..models import MetaSnapshot
                error_msg = ''
                if snap.get('errors'):
                    error_msg = '; '.join(f'{k}: {v}' for k, v in snap['errors'].items())
                MetaSnapshot.objects.create(
                    tipo='full',
                    period_days=28,
                    datos=snap,
                    generado_por='cron_weekly',
                    error=error_msg,
                )
            except Exception as exc:
                logger.warning(f'No se pudo persistir MetaSnapshot: {exc}')

        return snap
    except Exception as exc:
        logger.warning(f'Meta snapshot no disponible: {exc}')
        return None


def call_llm(
    semana_inicio,
    semana_fin,
    frases_clientes,
    blog_posts_recientes,
    alertas_analisis_ia,
    ga4_snapshot: Optional[dict] = None,
    gsc_snapshot: Optional[dict] = None,
    meta_snapshot: Optional[dict] = None,
    model: Optional[str] = None,
) -> dict:
    """Llama a OpenRouter con todo el contexto y devuelve el brief en dict."""
    from openai import OpenAI

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    if not api_key:
        raise ValueError('OPENROUTER_API_KEY no configurada')

    model = model or getattr(settings, 'MARKETING_BRIEF_LLM_MODEL', 'anthropic/claude-sonnet-4.6')

    playbook = _read_doc('docs/MARKETING_PLAYBOOK.md')
    recurring_tasks = _read_doc('docs/AREMKO_RECURRING_TASKS.md')

    if not playbook:
        raise ValueError('docs/MARKETING_PLAYBOOK.md no encontrado o vacío')

    user_prompt = build_user_prompt(
        semana_inicio=semana_inicio,
        semana_fin=semana_fin,
        playbook=playbook,
        recurring_tasks=recurring_tasks,
        frases_clientes=frases_clientes,
        blog_posts_recientes=blog_posts_recientes,
        alertas_analisis_ia=alertas_analisis_ia,
        ga4_snapshot=ga4_snapshot,
        gsc_snapshot=gsc_snapshot,
        meta_snapshot=meta_snapshot,
    )

    client = OpenAI(api_key=api_key, base_url=base_url)

    logger.info(f'Llamando a {model} para brief semanal de marketing')

    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0.6,  # algo de creatividad para los drafts
        max_tokens=16000,  # mas alto desde que se agregaron metricas GA4/GSC + reviews al contexto
        response_format={'type': 'json_object'},
    )

    raw = response.choices[0].message.content or ''
    cleaned = _strip_markdown_fences(raw)
    try:
        brief = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(f'LLM no devolvió JSON válido: {exc}. Raw[:500]: {raw[:500]} | Cleaned[:500]: {cleaned[:500]}')
        raise ValueError(f'LLM response no es JSON válido: {exc}')

    return brief


def generate_brief() -> dict:
    """Punto de entrada: genera el brief de la semana actual.

    Retorna dict con:
    - 'semana_inicio', 'semana_fin' (date)
    - 'brief' (dict del LLM)
    - 'frases_clientes_count'
    - 'blog_posts_count'
    """
    now = timezone.now()
    # Lunes de esta semana
    semana_inicio = (now - timedelta(days=now.weekday())).date()
    semana_fin = semana_inicio + timedelta(days=6)

    frases = get_frases_clientes_promotores(days=30)
    posts = get_blog_posts_recientes(limit=5)
    alertas = get_alertas_analisis_ia_anterior()
    ga4_snapshot = get_ga4_snapshot_safe()
    gsc_snapshot = get_gsc_snapshot_safe()
    meta_snapshot = get_meta_snapshot_safe(persist=True)

    brief = call_llm(
        semana_inicio=semana_inicio,
        semana_fin=semana_fin,
        frases_clientes=frases,
        blog_posts_recientes=posts,
        alertas_analisis_ia=alertas,
        ga4_snapshot=ga4_snapshot,
        gsc_snapshot=gsc_snapshot,
        meta_snapshot=meta_snapshot,
    )

    return {
        'semana_inicio': semana_inicio,
        'semana_fin': semana_fin,
        'brief': brief,
        'frases_clientes_count': len(frases),
        'blog_posts_count': len(posts),
        'ga4_snapshot': ga4_snapshot,
        'gsc_snapshot': gsc_snapshot,
        'meta_snapshot': meta_snapshot,
        'metricas_disponibles': bool(ga4_snapshot or gsc_snapshot or meta_snapshot),
    }
