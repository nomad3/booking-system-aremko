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


SYSTEM_PROMPT = """Eres el director de marketing y planificación comercial de Aremko Spa Boutique (Puerto Varas, Chile). Cada lunes 10 AM generas el brief semanal — el documento maestro que ordena el trabajo de toda la semana para Jorge (dueño), Daniela (manager de redes) y el equipo.

NATURALEZA DEL BRIEF: el brief NO es un calendario simple. Es un análisis ejecutivo + diagnóstico cruzado de TODAS las fuentes de datos del negocio (web, redes, paid, encuestas, reviews, pipeline comercial) + planificación operativa concreta + drafts listos para copiar/pegar. Su rol: que cualquier persona del equipo Aremko que lo abra el lunes en la mañana entienda el estado del negocio y sepa exactamente qué tiene que hacer cada día.

ESTRUCTURA OBLIGATORIA: el output debe empezar siempre con un RESUMEN EJECUTIVO de máximo 6-8 frases que cualquiera pueda leer en 60 segundos. Después, secciones extensas y detalladas. La regla es: corto arriba para que el dueño tome decisiones rápido, largo abajo para que el equipo operativo no necesite preguntar nada.

CONTEXTO MAESTRO:
- Playbook (incluido abajo): voz de marca, 3 buyer personas, 8 diferenciales priorizados, frases ancla, hooks Víctor Eras, palabras prohibidas. Es la fuente de verdad inviolable.
- Calendario Chile: feriados, fechas comerciales, temporadas turísticas. Usar para anticipar.
- Objetivo de la semana (si Jorge lo escribió): es la PRIORIDAD #1, todo el contenido de la semana debe servir a ese objetivo.

REGLAS DE PRODUCCIÓN DE COPY:
- Voz Aremko: honesta, específica, sin marketing inflado
- Español latinoamericano (NUNCA voseo argentino: usar "tú", "puedes", "quieres", no "vos podés")
- NUNCA usar "experiencia única", "magia", "momentos inolvidables" en mayúscula
- Frases ancla a usar cuando aplique: "2 días aquí equivalen a una semana de vacaciones", "no usamos leña", "37°C o menos = gratis", "a metros del río Pescado"
- Para Reels: estructura 5 partes (gancho 4-7s · contexto · moraleja · solución · CTA con palabra clave)
- Citar texto real del cliente cuando esté disponible (mejor que copy inventado)
- UTMs siempre en links: el playbook tiene la convención
- Cada draft debe tener estimación de tiempo de producción (ej: "30 min Daniela") y responsable

ANÁLISIS CRUZADO REQUERIDO:
- Cruzar siempre Voz del Cliente (encuestas + reviews) con datos de tráfico web (GA4) y redes (Meta) para identificar gaps específicos
- Si una keyword sube en GSC pero no convierte → revisar contenido de la página de aterrizaje
- Si los reviews mencionan algo positivo recurrente → convertir en hook de contenido
- Si los reviews mencionan algo negativo → alerta operativa Y oportunidad de mostrar mejora pública
- Si hay paid corriendo con costo por interacción alto → proponer cambio específico (objective, segmentación, creativo)
- Si el pipeline de reservas muestra disponibilidad concreta → vincularla a contenido de la semana

EXTENSIÓN DEL OUTPUT: NO hay límite de longitud. El brief debe ser todo lo extenso que sea necesario. Si una sección requiere 1000 palabras, son 1000 palabras. Lo único que está prohibido es relleno vacío (frases que no agregan información).

FORMATO DE OUTPUT: JSON estricto sin markdown ni texto adicional. Estructura completa especificada en el user prompt."""


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
    meta_analysis: Optional[dict] = None,
    objetivo_semana: Optional[dict] = None,
    reviews_resumen: Optional[dict] = None,
    calendario_chile: Optional[str] = None,
    pipeline_reservas: Optional[dict] = None,
) -> str:
    """Construye el user prompt con toda la info contextual."""

    return f"""Genera el brief de marketing para la semana del {semana_inicio.strftime('%d %b %Y')} al {semana_fin.strftime('%d %b %Y')}.

=== OBJETIVO DEFINIDO POR JORGE PARA ESTA SEMANA ===
{(f"Semana del {objetivo_semana['semana_inicio']} (vigencia: {'semana actual' if objetivo_semana.get('es_de_semana_actual') else 'semana anterior — Jorge no lo actualizó'}):" + chr(10) + chr(10) + objetivo_semana['objetivo']) if objetivo_semana else '(Jorge NO definió objetivo para esta semana — usar diagnóstico cruzado para inferir prioridades, mencionar la falta del objetivo en la sección de recordatorios)'}

=== PLAYBOOK MAESTRO (tu fuente de verdad inviolable) ===
{playbook[:10000]}

=== CADENCIA OPERATIVA (qué se publica cada día) ===
{recurring_tasks[:3500]}

=== CALENDARIO CHILE (feriados + fechas comerciales + temporadas) ===
{(calendario_chile[:6000]) if calendario_chile else '(no disponible — usar conocimiento general de feriados Chile y temporadas turísticas Puerto Varas)'}

=== FRASES REALES DE CLIENTES PROMOTORES (NPS>=9, últimos 30 días) ===
{json.dumps(frases_clientes[:20], indent=2, ensure_ascii=False)}

=== ANÁLISIS IA ENCUESTAS (resumen del último análisis del lunes 9 AM) ===
{json.dumps(alertas_analisis_ia, indent=2, ensure_ascii=False, default=str)[:6000] if alertas_analisis_ia else '(no disponible — el análisis IA semanal de encuestas no corrió esta semana o no se persistió)'}

=== REVIEWS EXTERNAS (TripAdvisor + Google Reviews) ===
{json.dumps(reviews_resumen, indent=2, ensure_ascii=False, default=str)[:5000] if reviews_resumen else '(no disponible)'}

=== PIPELINE COMERCIAL INTERNO (Aremko BD Django) ===
INSTRUCCIONES PARA ANALIZAR:
- Compara ultima_semana vs semana_anterior usando los % en tendencia_7d_vs_anterior. Si cae >20% en algún indicador clave, mencionarlo en alerta crítica.
- Mira por_categoria del último mes para entender la mezcla del negocio (% Tinas vs Masajes vs Alojamientos vs Productos).
- Si en metodos_pago_analisis.cambios_detectados hay un canal NUEVO (ej: "Flow aparece esta semana, 0 en las 3 previas"), MENCIONARLO explícitamente como hallazgo importante. Es información operativa de transición.
- packs_ultima_semana muestra cuántas reservas son de 1 solo servicio vs 2+. El pack premium 3-en-1 (tina + masaje + alojamiento) es el producto estrella del playbook — si hay 0 esta semana, es alerta. Si crece, comunicarlo.
- combinaciones_top revela qué packs están comprando los clientes naturalmente (ej: "Tinas + Productos: 12 reservas"). Esto debe guiar el contenido de la semana.
- tasa_recurrencia_ultima_semana_pct: si >30% es retención sólida; si <10% el negocio depende de adquisición.
- top_recurrentes son los clientes más leales de los últimos 30 días — útiles para email engaged personalizado o campañas WhatsApp directas.
- anticipacion_reserva.promedio_dias dice con cuántos días de antelación reservan en promedio. Si baja a 1-2 días → la gente decide en el momento (priorizar paid de inmediatez); si sube a 7+ → planifican (priorizar contenido educativo + email).
- disponibilidad_proxima_semana: reservas YA agendadas para los próximos 7 días. Si los servicios top están saturados, comunicar como "última disponibilidad". Si están vacíos, paid + descuento.
- comparativa_mensual_misma_fecha: COMPARA el mismo rango del mes en curso (ej: 1-9 mayo) vs el mes anterior (ej: 1-9 abril) DESGLOSADO POR FAMILIA: tinas, masajes, cabañas, productos_otros. Esta es la comparativa de estacionalidad mes a mes. Para cada familia, indica reservas_pct_cambio e ingresos_pct_cambio. Si una familia cae >20% intermensual, es alerta. Si crece >30%, oportunidad de capitalizar (ej: "Tinas crecieron 45% vs abril → empujar contenido de tinas con baja temperatura"). Reportar también el total general (todas las familias agregadas).
- Si reservation_started en GA4 es muy superior a reservas_pagadas en pipeline (ej: 232 GA4 vs 55 BD), eso indica que la mayoría de las conversiones cierran fuera del web (WhatsApp, llamada). Mencionarlo como insight.
- IMPORTANTE: si en los DATOS aparece la clave "_errores", MENCIONA EXPLICITAMENTE en una alerta operativa de la sección comercial: "Errores parciales del pipeline: <lista>". No inventes ni infiera datos faltantes; di "sin datos por error técnico" y ESCRIBE EL ERROR para que Jorge lo vea.
- Si aparece "_falla_total: true", reporta como alerta crítica que el pipeline interno completo falló y NO uses datos derivados.

DATOS:
{json.dumps(pipeline_reservas, indent=2, ensure_ascii=False, default=str) if pipeline_reservas else '(no disponible)'}

=== BLOG POSTS RECIENTES (no repetir temas, sí reciclar conceptos) ===
{json.dumps(blog_posts_recientes, indent=2, ensure_ascii=False, default=str)}

=== GA4 (sitio web aremko.cl) — ÚLTIMOS 7 DÍAS vs 7 ANTERIORES ===
{json.dumps(ga4_snapshot, indent=2, ensure_ascii=False, default=str) if ga4_snapshot else '(no disponible)'}

=== GOOGLE SEARCH CONSOLE (búsqueda orgánica) — ÚLTIMOS 7 DÍAS vs 7 ANTERIORES ===
{json.dumps(gsc_snapshot, indent=2, ensure_ascii=False, default=str) if gsc_snapshot else '(no disponible)'}

=== META: FACEBOOK + INSTAGRAM ORGÁNICO + ADS (últimos 28 días, todas las cuentas) ===
{json.dumps(meta_snapshot, indent=2, ensure_ascii=False, default=str)[:8000] if meta_snapshot else '(no disponible)'}

=== ANÁLISIS IA META PRE-PROCESADO (alertas + oportunidades + acciones) ===
{json.dumps(meta_analysis, indent=2, ensure_ascii=False, default=str)[:6000] if meta_analysis else '(no disponible)'}

=== TU OUTPUT (JSON estricto, sin markdown) ===

{{
  "resumen_ejecutivo": {{
    "semana_referencia": "DD-mm-YYYY al DD-mm-YYYY",
    "headline": "1 frase: el dato/decisión más importante de esta semana, lo que hay que entender en 5 segundos",
    "puntos_clave": [
      "4-6 bullets críticos que cualquiera del equipo debe saber: estado del negocio + lo que hay que hacer + por qué importa. Cada bullet 1-2 frases máximo. Concretos, con números reales del snapshot."
    ],
    "objetivo_de_la_semana": "Texto del objetivo definido por Jorge (literal). Si no hay, escribir '(no definido — recordar a Jorge que lo escriba en /admin/ventas/weeklyobjective/add/)'",
    "alerta_critica_si_existe": "Solo si hay algo URGENTE que requiere acción inmediata (caída de tráfico, review negativo grave, campaña paid con costo descontrolado). Si no hay, omitir este campo o poner null."
  }},

  "fechas_clave_proximas_4_semanas": [
    {{"fecha": "DD-mm-YYYY", "evento": "...", "implicancia_marketing": "qué hay que hacer al respecto"}}
  ],

  "diagnostico_extenso": {{
    "voz_del_cliente": {{
      "sentimiento_general": "Análisis del NPS, encuestas y reviews de la semana. Cita textual de 2-3 clientes.",
      "alertas_operativas": [
        {{"alerta": "...", "fuente": "encuesta|review|llamada", "frecuencia": "cuántas veces apareció", "accion_sugerida": "..."}}
      ],
      "oportunidades_de_contenido": [
        "Cosas positivas que mencionan clientes y se pueden convertir en hooks de Reels/posts"
      ],
      "follow_ups_urgentes_count": "Número de encuestas con NPS bajo pendientes de contacto"
    }},

    "redes_sociales": {{
      "facebook_diagnostico": "Análisis extenso de FB: cantidad de posts, engagement total, top post del periodo, comparación con semana anterior si hay datos. Mínimo 4-5 frases. Identificar qué funcionó y qué no.",
      "instagram_diagnostico": "Análisis extenso de IG: alcance, ratio alcance/followers, follower growth, top media del periodo, frecuencia de publicación. Mínimo 4-5 frases.",
      "paid_ads_diagnostico": "Análisis extenso de paid ads: cuántas campañas activas en TODAS las cuentas, inversión total CLP del periodo, costo por interacción, conversiones. Si hay objetivo desalineado (ej: LINK_CLICKS hacia WhatsApp), MENCIONARLO. Mínimo 5-6 frases.",
      "comparacion_organico_vs_paid": "Cuánto del engagement total viene de paid vs orgánico. Si paid genera 95% del engagement, mencionarlo explícitamente con números.",
      "top_3_aprendizajes_de_contenido": [
        "Insight 1 sobre qué tipo de contenido rinde mejor con datos concretos",
        "Insight 2",
        "Insight 3"
      ]
    }},

    "web_y_seo": {{
      "trafico_resumen": "Análisis extenso de GA4 últimos 7 días vs anteriores. Mínimo 4 frases con números. Mencionar fuentes de tráfico, top páginas, eventos custom (whatsapp_click, reservation_started, reservation_completed).",
      "embudo_reservas": "Tasa de reservation_started → reservation_completed. Si hay caída, alerta. Si subió, celebrar.",
      "seo_resumen": "Análisis extenso de GSC. Top queries, posiciones, CTR. Identificar queries con CTR bajo en buena posición (oportunidad rápida) y queries en posición 11-20 (oportunidad de subir a top 10).",
      "top_3_acciones_seo_esta_semana": [
        "Acción específica 1 — qué página, qué keyword, qué cambio",
        "Acción 2",
        "Acción 3"
      ]
    }},

    "comercial_y_pipeline": {{
      "reservas_resumen": "Cuántas reservas se crearon ESTA semana, cuántas pagaron, ticket promedio CLP, total facturado. Mínimo 4 frases con números reales del campo ultima_semana.",
      "tendencia_vs_semana_anterior": "% cambio reservas pagadas y facturado vs semana anterior (campos tendencia_7d_vs_anterior). Si subió o bajó fuerte (>20%), proponer hipótesis de causa y acción.",
      "comparacion_mes": "Resumen de últimos 30 días: total reservas pagadas, facturado total, ticket promedio. Sirve para dar contexto mensual del negocio.",
      "mezcla_por_categoria": "Distribución por familia de servicios (Tinas, Masajes, Alojamientos, Productos) en última semana y último mes. % de cada uno. Detectar si la mezcla cambió.",
      "analisis_packs_vs_simples": "Cuántas reservas pack (2+ servicios) vs simples (1 servicio). Ticket promedio de cada uno. Si packs son raros, oportunidad de upsell. Pack 3-en-1 (tina+masaje+alojamiento): cuántas vendió esta semana. Combinaciones más vendidas (ej: tinas + productos).",
      "canales_pago_y_cambios": "Distribución última semana (Flow, MercadoPago, Tarjeta, Transferencia, GiftCard, etc.). Si hay canales NUEVOS aparecidos esta semana (cambios_detectados), MENCIONARLO como hallazgo. Comparar con últimos 30 días.",
      "comportamiento_cliente": "Tasa de recurrencia (% reservas de la semana de clientes que ya habían venido), top clientes recurrentes últimos 30d, anticipación promedio (días entre fecha_reserva y fecha_agendamiento).",
      "disponibilidad_proxima_semana": "Cuántas reservas ya hay confirmadas para los próximos 7 días. Servicios saturados (comunicar 'última disponibilidad') vs servicios con huecos (priorizar paid).",
      "comparativa_mensual_misma_fecha": "TABLA comparativa por FAMILIA del rango (1-N mes actual) vs (1-N mes anterior), donde N=día actual. Para CADA familia (Tinas, Masajes, Cabañas, Productos): N° reservas mes actual vs anterior + % cambio, e ingresos mes actual vs anterior + % cambio. Indicar también el total. Esta comparativa muestra estacionalidad mes a mes y si Día de la Madre/feriados movieron una familia más que otra. Si una familia cae >20%, alerta operativa. Si crece >30%, oportunidad para empujar más esa familia.",
      "abandonos_flow": "Cuántos PendingReservation iniciados/expirados/confirmados, qué dice del checkout y de la nueva pasarela Flow.",
      "implicancia_comunicacional": "Recomendaciones de contenido específicas basadas en TODO lo anterior. Ej: 'Como esta semana se vendieron más Tinas que Masajes y la categoría Alojamientos cayó 30%, proponer Reel del Reel del 27-abr enfocado en cabaña con tina'."
    }}
  }},

  "calendario_semanal": [
    {{"dia": "Lunes", "fecha": "DD/MM", "publicaciones": [
      {{"canal": "GBP|Facebook|Instagram|Stories|Email|WhatsApp Broadcast", "hora": "10:30", "tipo": "post|reel|carrusel|story|email", "concepto_corto": "qué se publica", "estado": "draft listo en sección drafts"}}
    ]}},
    {{"dia": "Martes", "fecha": "DD/MM", "publicaciones": []}},
    {{"dia": "Miércoles", "fecha": "DD/MM", "publicaciones": []}},
    {{"dia": "Jueves", "fecha": "DD/MM", "publicaciones": []}},
    {{"dia": "Viernes", "fecha": "DD/MM", "publicaciones": []}},
    {{"dia": "Sábado", "fecha": "DD/MM", "publicaciones": []}},
    {{"dia": "Domingo", "fecha": "DD/MM", "publicaciones": []}}
  ],

  "drafts_completos": {{
    "gbp_post": {{
      "necesario_esta_semana": true,
      "responsable": "Daniela",
      "tiempo_estimado": "20 min",
      "texto": "Copy listo para pegar en Google Business Profile (max 1500 chars)",
      "url_cta": "URL con UTM completo",
      "foto_sugerida": "Descripción detallada de la foto a usar y de dónde sacarla (galería propia, foto del día, etc.)"
    }},
    "reel_martes": {{
      "necesario_esta_semana": true,
      "responsable": "Daniela",
      "tiempo_estimado": "1.5 horas (grabación + edición + caption)",
      "concepto": "Idea ganadora en 1 frase",
      "filtro_5_50": "Por qué pasa el filtro Víctor Eras (simple para 5 años + atrae a 50)",
      "duracion_objetivo_segundos": 30,
      "guion": [
        {{"bloque": "gancho_5s", "texto": "Frase exacta a decir o mostrar — debe ser hookcable"}},
        {{"bloque": "contexto_15s", "texto": "..."}},
        {{"bloque": "moraleja_10s", "texto": "..."}},
        {{"bloque": "solucion_5s", "texto": "..."}},
        {{"bloque": "cta_palabra_clave", "texto": "Comenta TINAS y te paso..."}}
      ],
      "tomas_sugeridas": [
        "Toma 1: descripción específica con encuadre",
        "Toma 2: ...",
        "Toma 3: ..."
      ],
      "audio_sugerido": "Sonido del río Pescado real | música de tendencia | voz en off",
      "caption_completo": "Caption listo para pegar (max 2200 chars)",
      "hashtags": ["#hashtag1", "#hashtag2", "#PuertoVaras", "#sur de Chile"]
    }},
    "carrusel_miercoles": {{
      "necesario_esta_semana": true,
      "responsable": "Daniela",
      "tiempo_estimado": "2 horas",
      "concepto": "...",
      "numero_de_slides": 6,
      "slides": [
        {{"numero": 1, "imagen_sugerida": "...", "texto_overlay": "...", "rol": "hook"}},
        {{"numero": 2, "imagen_sugerida": "...", "texto_overlay": "...", "rol": "desarrollo"}}
      ],
      "caption_completo": "Caption del post completo (max 2200 chars)"
    }},
    "reel_jueves": {{
      "necesario_esta_semana": true,
      "responsable": "Daniela",
      "tiempo_estimado": "1.5 horas",
      "concepto": "Variación del Reel del martes si pasó RI 50%, o idea nueva",
      "guion": [],
      "tomas_sugeridas": [],
      "audio_sugerido": "",
      "caption_completo": "",
      "hashtags": []
    }},
    "stories_diarias": [
      {{"dia": "Lunes", "concepto": "...", "tipo": "detrás de escena|datos del día|naturaleza|cliente real|recordatorio práctico|encuesta", "texto_sugerido": "..."}},
      {{"dia": "Martes", "concepto": "...", "tipo": "...", "texto_sugerido": "..."}},
      {{"dia": "Miércoles", "concepto": "...", "tipo": "...", "texto_sugerido": "..."}},
      {{"dia": "Jueves", "concepto": "...", "tipo": "...", "texto_sugerido": "..."}},
      {{"dia": "Viernes", "concepto": "...", "tipo": "...", "texto_sugerido": "..."}},
      {{"dia": "Sábado", "concepto": "...", "tipo": "...", "texto_sugerido": "..."}},
      {{"dia": "Domingo", "concepto": "...", "tipo": "...", "texto_sugerido": "..."}}
    ],
    "email_engaged": {{
      "necesario_esta_semana": true,
      "responsable": "Jorge",
      "tiempo_estimado": "30 min",
      "asunto": "...",
      "preheader": "...",
      "cuerpo_html_resumen": "Estructura del email (no HTML completo, sino qué bloques: hero, párrafo intro, CTA, bloque secundario, footer)",
      "cuerpo_texto_plano_completo": "Versión texto plano del email completo",
      "segmento_destinatario": "Engaged (clic+open en últimos 90 días)|Toda la lista|Recientes 30d"
    }},
    "post_blog_si_aplica": {{
      "necesario_esta_semana": false,
      "responsable": "Jorge con skill /blog-aremko",
      "tema_sugerido": "Si aplica, qué post del blog escribir esta semana basado en GSC top queries y huecos editoriales"
    }}
  }},

  "ideas_contenido_proximas_2_semanas": [
    {{"semana": "siguiente", "tema": "...", "tipo": "Reel|Carrusel|Post blog|Email", "razon": "Por qué este tema"}}
  ],

  "acciones_paid_ads_recomendadas": [
    {{"accion": "Pausar campaña X|Crear nueva con objective Y|Cambiar segmentación de Z", "responsable": "Jorge|Daniela", "esfuerzo": "bajo|medio|alto", "razon": "Datos concretos del snapshot Meta", "metrica_a_mover": "..."}}
  ],

  "alertas_operativas_no_marketing": [
    "Cosas que detectamos en encuestas/reviews que NO son marketing pero importan (temperatura tina, limpieza, atención). Si Jorge no las resuelve operativamente, el marketing no funciona."
  ],

  "metricas_a_revisar_viernes": [
    "Lista específica de métricas para evaluar al cierre de la semana. Cada una con valor objetivo si aplica."
  ],

  "preguntas_abiertas_para_jorge": [
    "Cosas que el LLM detectó pero necesita decisión humana. Ej: '¿Querés que pausemos la campaña X que tiene CPC alto, o le damos 1 semana más?'"
  ],

  "recordatorios": [
    "Cosas operativas a no olvidar (renovar token Meta si aplica, actualizar objetivo de la semana en admin, etc.)"
  ]
}}

REGLAS DE GENERACIÓN:
- El RESUMEN EJECUTIVO debe ser corto. El resto puede ser todo lo extenso necesario.
- Si Jorge definió objetivo de la semana, todo el contenido y las acciones DEBEN servir a ese objetivo. Es prioridad #1.
- Si la frase ancla "2 días equivalen a una semana de vacaciones" no se usó la semana anterior, incluirla en algún draft.
- Si una frase real de cliente promotor calza con el tipo de Reel, USARLA literal.
- Si Email engaged no se justifica esta semana, poner necesario_esta_semana: false con explicación breve.
- Si un canal/dato no está disponible, poner "(sin datos)" en el campo y NO inventar.
- Las acciones de métricas deben ser específicas: nombrar página/query/evento concreto.
- En español latinoamericano. NO voseo argentino bajo ninguna circunstancia.
- Si hay paid corriendo con objective desalineado al embudo (ej: LINK_CLICKS hacia WhatsApp), MENCIONARLO en alertas y proponer cambio en acciones_paid_ads_recomendadas.
- Cruzar datos: si GSC dice que "tinas calientes puerto varas" subió de pos 8 a pos 4 Y reviews mencionan "el sonido del río", hacer un Reel sobre tinas con audio del río — datos cruzados generan acciones específicas.
"""


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

    Lee WeeklySurveyAnalysis (persistido por survey_ai_analyzer cada lunes 9 AM).
    """
    try:
        from .survey_ai_analyzer import get_latest_analysis
        return get_latest_analysis()
    except Exception as exc:
        logger.warning(f'No se pudo obtener analisis IA encuestas anterior: {exc}')
        return None


def get_objetivo_semana_safe() -> Optional[dict]:
    """Devuelve el objetivo definido por Jorge para la semana actual.

    Lee WeeklyObjective. Si no hay objetivo para la semana en curso, intenta
    el de la semana anterior (puede que Jorge se haya olvidado de actualizarlo).
    """
    try:
        from datetime import date, timedelta
        from ..models import WeeklyObjective

        hoy = date.today()
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        lunes_anterior = lunes_actual - timedelta(days=7)

        # Primero buscar objetivo de la semana actual
        obj = WeeklyObjective.objects.filter(semana_inicio=lunes_actual).first()
        if not obj:
            # Fallback: semana anterior (puede aplicar todavia)
            obj = WeeklyObjective.objects.filter(semana_inicio=lunes_anterior).first()

        if not obj:
            return None

        return {
            'semana_inicio': obj.semana_inicio.isoformat(),
            'objetivo': obj.objetivo,
            'es_de_semana_actual': obj.semana_inicio == lunes_actual,
            'updated_at': obj.updated_at.isoformat() if obj.updated_at else None,
        }
    except Exception as exc:
        logger.warning(f'No se pudo obtener objetivo de la semana: {exc}')
        return None


def get_reviews_resumen_safe() -> Optional[dict]:
    """Resumen de reviews externas (TripAdvisor + Google Reviews) para el brief.

    Combina:
    - Ultimo ReviewSnapshot (semanal manual: rating + total + deltas)
    - Reviews individuales (Review model) de los ultimos 14 dias
    """
    try:
        from datetime import timedelta
        from django.utils import timezone as dj_tz
        from ..models import ReviewSnapshot, Review

        result = {}

        # Ultimo snapshot manual
        last_snap = ReviewSnapshot.objects.order_by('-fecha').first()
        if last_snap:
            result['snapshot'] = {
                'fecha': last_snap.fecha.isoformat() if last_snap.fecha else None,
                'google_rating': float(last_snap.google_rating) if last_snap.google_rating else None,
                'google_total': last_snap.google_total,
                'google_url': last_snap.google_url,
                'tripadvisor_rating': float(last_snap.tripadvisor_rating) if last_snap.tripadvisor_rating else None,
                'tripadvisor_total': last_snap.tripadvisor_total,
                'tripadvisor_url': last_snap.tripadvisor_url,
                'notas': last_snap.notas,
            }

        # Reviews individuales recientes (extraidas con IA, con texto completo)
        cutoff = dj_tz.now().date() - timedelta(days=14)
        reviews = Review.objects.filter(
            fecha_review__gte=cutoff,
        ).order_by('-fecha_review')[:30]

        result['reviews_recientes'] = [
            {
                'fuente': r.fuente,
                'fecha': r.fecha_review.isoformat() if r.fecha_review else None,
                'autor': r.autor,
                'rating': r.rating,
                'texto': r.texto[:500] if r.texto else '',
                'sentimiento': r.sentimiento,
                'temas': r.temas_detectados,
                'idioma': r.idioma,
                'respuesta_publicada': r.respuesta_publicada,
            }
            for r in reviews
        ]
        result['reviews_recientes_count'] = len(result['reviews_recientes'])

        return result if result else None
    except Exception as exc:
        logger.warning(f'No se pudo obtener resumen de reviews: {exc}')
        return None


def get_calendario_chile_safe() -> str:
    """Lee docs/AREMKO_CALENDARIO_CHILE.md y lo devuelve como string."""
    return _read_doc('docs/AREMKO_CALENDARIO_CHILE.md')


def _agg_periodo(VentaReserva, Pago, ReservaServicio, since, until) -> dict:
    """Agregados de un periodo (since, until) — helper interno para get_pipeline_reservas_safe."""
    from django.db.models import Count, Sum, Avg, Q
    ventas = VentaReserva.objects.filter(fecha_reserva__gte=since, fecha_reserva__lt=until)
    creadas = ventas.count()
    pagadas_qs = ventas.filter(estado_pago='pagado')
    pagadas = pagadas_qs.count()
    # Nota: usar alias distintos al nombre del campo para evitar
    # FieldError "Cannot compute Avg('total'): 'total' is an aggregate"
    agg = pagadas_qs.aggregate(suma_total=Sum('total'), promedio_total=Avg('total'))

    # Por categoria de servicio
    categorias = list(
        ReservaServicio.objects
        .filter(venta_reserva__in=pagadas_qs)
        .values('servicio__categoria__nombre')
        .annotate(reservas=Count('id'), ingresos=Sum('servicio__precio_base'))
        .order_by('-ingresos')
    )

    # Por metodo de pago (Pagos del periodo)
    pagos_periodo = Pago.objects.filter(fecha_pago__gte=since, fecha_pago__lt=until)
    metodos = {p['metodo_pago']: p['c'] for p in pagos_periodo.values('metodo_pago').annotate(c=Count('id'))}
    metodos_total = sum(metodos.values())

    return {
        'creadas': creadas,
        'pagadas': pagadas,
        'tasa_conversion_pct': round(pagadas / creadas * 100, 1) if creadas else 0,
        'total_facturado': float(agg['suma_total'] or 0),
        'ticket_promedio': float(agg['promedio_total'] or 0),
        'por_categoria': categorias,
        'metodos_pago_count': metodos,
        'metodos_pago_total_transacciones': metodos_total,
    }


def _detectar_packs(VentaReserva, ReservaServicio, since, until) -> dict:
    """Identifica reservas pack (2+ servicios) vs simples (1 servicio).
    Detecta combinaciones más vendidas y el pack 3-en-1 completo.
    """
    from django.db.models import Count, Avg
    from collections import Counter

    ventas_periodo = VentaReserva.objects.filter(
        fecha_reserva__gte=since,
        fecha_reserva__lt=until,
        estado_pago='pagado',
    ).annotate(n_servicios=Count('reservaservicios'))

    # Reservas con 2+ servicios
    pack_qs = ventas_periodo.filter(n_servicios__gte=2)
    simple_qs = ventas_periodo.filter(n_servicios=1)
    pack_count = pack_qs.count()
    simple_count = simple_qs.count()

    pack_avg = pack_qs.aggregate(avg=Avg('total'))['avg'] or 0
    simple_avg = simple_qs.aggregate(avg=Avg('total'))['avg'] or 0

    # Combinaciones más vendidas (categorías por venta)
    combo_counter = Counter()
    pack_3en1 = 0
    for v in pack_qs.prefetch_related('reservaservicios__servicio__categoria'):
        cats = sorted({
            (r.servicio.categoria.nombre if r.servicio and r.servicio.categoria else 'Sin categoría')
            for r in v.reservaservicios.all()
        })
        combo_str = ' + '.join(cats)
        combo_counter[combo_str] += 1
        # Pack 3-en-1: tinas + masajes + alojamientos
        cats_lower = {c.lower() for c in cats}
        if any('tina' in c for c in cats_lower) and any('masaje' in c for c in cats_lower) and any('aloj' in c or 'cabaña' in c or 'cabana' in c for c in cats_lower):
            pack_3en1 += 1

    return {
        'reservas_pack_2plus': pack_count,
        'reservas_simples_1': simple_count,
        'ticket_promedio_pack': float(pack_avg),
        'ticket_promedio_simple': float(simple_avg),
        'pack_premium_3en1': pack_3en1,
        'combinaciones_top': [
            {'combo': combo, 'count': c}
            for combo, c in combo_counter.most_common(8)
        ],
    }


def _ventas_por_familia_rango(VentaReserva, ReservaServicio, since_date, until_date) -> dict:
    """Agrega ventas pagadas en (since_date, until_date] por familia de servicio.

    Familias detectadas (por nombre de categoria): Cabañas/Alojamientos, Masajes, Tinas.
    Devuelve dict con conteo de reservas y suma de ingresos por familia.
    """
    from django.db.models import Count, Sum
    from datetime import datetime, time

    # Convertir dates a datetimes para comparar contra fecha_reserva (datetime)
    since_dt = datetime.combine(since_date, time.min)
    until_dt = datetime.combine(until_date, time.max)

    rs_qs = ReservaServicio.objects.filter(
        venta_reserva__fecha_reserva__gte=since_dt,
        venta_reserva__fecha_reserva__lte=until_dt,
        venta_reserva__estado_pago='pagado',
    ).select_related('servicio', 'servicio__categoria', 'venta_reserva')

    familia_data = {
        'tinas': {'reservas': 0, 'ingresos': 0.0, 'ventas_unicas': set()},
        'masajes': {'reservas': 0, 'ingresos': 0.0, 'ventas_unicas': set()},
        'cabanas': {'reservas': 0, 'ingresos': 0.0, 'ventas_unicas': set()},
        'productos_otros': {'reservas': 0, 'ingresos': 0.0, 'ventas_unicas': set()},
    }
    for rs in rs_qs:
        cat = (rs.servicio.categoria.nombre if rs.servicio and rs.servicio.categoria else '').lower()
        if 'tina' in cat:
            key = 'tinas'
        elif 'masaje' in cat:
            key = 'masajes'
        elif 'aloj' in cat or 'cabaña' in cat or 'cabana' in cat:
            key = 'cabanas'
        else:
            key = 'productos_otros'
        familia_data[key]['reservas'] += 1
        # Precio por servicio: precio_unitario_venta si existe, sino precio_base × cantidad
        try:
            precio_u = float(rs.precio_unitario_venta) if rs.precio_unitario_venta else float(rs.servicio.precio_base)
        except Exception:
            precio_u = 0.0
        familia_data[key]['ingresos'] += precio_u * (rs.cantidad_personas or 1)
        familia_data[key]['ventas_unicas'].add(rs.venta_reserva_id)

    # Convertir sets a counts
    for k in familia_data:
        familia_data[k]['ventas_unicas'] = len(familia_data[k]['ventas_unicas'])

    # Total reservas pagadas en el rango (para % de mezcla)
    total_ventas_pagadas = VentaReserva.objects.filter(
        fecha_reserva__gte=since_dt,
        fecha_reserva__lte=until_dt,
        estado_pago='pagado',
    ).aggregate(c=Count('id'), s=Sum('total'))

    return {
        'desde': since_date.isoformat(),
        'hasta': until_date.isoformat(),
        'total_reservas_pagadas': total_ventas_pagadas['c'] or 0,
        'total_facturado': float(total_ventas_pagadas['s'] or 0),
        'familias': familia_data,
    }


def _comparativa_mensual_misma_fecha(VentaReserva, ReservaServicio) -> dict:
    """Compara ventas por familia del rango (dia 1 al dia actual) del mes
    en curso vs el mismo rango del mes anterior.

    Por ejemplo, si hoy es 9 de mayo, compara 1-9 mayo vs 1-9 abril.
    """
    from datetime import date, timedelta
    import calendar

    hoy = date.today()
    inicio_actual = hoy.replace(day=1)
    fin_actual = hoy

    # Mes anterior
    if inicio_actual.month == 1:
        mes_ant_year = inicio_actual.year - 1
        mes_ant_month = 12
    else:
        mes_ant_year = inicio_actual.year
        mes_ant_month = inicio_actual.month - 1
    inicio_anterior = date(mes_ant_year, mes_ant_month, 1)
    # Limitar dia: si el mes anterior tiene menos dias que hoy.day, ajustar
    ultimo_dia_mes_ant = calendar.monthrange(mes_ant_year, mes_ant_month)[1]
    dia_fin = min(hoy.day, ultimo_dia_mes_ant)
    fin_anterior = date(mes_ant_year, mes_ant_month, dia_fin)

    actual = _ventas_por_familia_rango(VentaReserva, ReservaServicio, inicio_actual, fin_actual)
    anterior = _ventas_por_familia_rango(VentaReserva, ReservaServicio, inicio_anterior, fin_anterior)

    # Calcular % de cambio por familia
    def _pct(a, b):
        if not b:
            return None
        return round((a - b) / b * 100, 1)

    cambios_por_familia = {}
    for fam in ['tinas', 'masajes', 'cabanas', 'productos_otros']:
        act = actual['familias'][fam]
        ant = anterior['familias'][fam]
        cambios_por_familia[fam] = {
            'reservas_actual': act['reservas'],
            'reservas_anterior': ant['reservas'],
            'reservas_pct_cambio': _pct(act['reservas'], ant['reservas']),
            'ingresos_actual': round(act['ingresos']),
            'ingresos_anterior': round(ant['ingresos']),
            'ingresos_pct_cambio': _pct(act['ingresos'], ant['ingresos']),
        }

    return {
        'rango_actual': f"{inicio_actual.isoformat()} a {fin_actual.isoformat()}",
        'rango_anterior': f"{inicio_anterior.isoformat()} a {fin_anterior.isoformat()}",
        'totales': {
            'reservas_actual': actual['total_reservas_pagadas'],
            'reservas_anterior': anterior['total_reservas_pagadas'],
            'reservas_pct_cambio': _pct(actual['total_reservas_pagadas'], anterior['total_reservas_pagadas']),
            'facturado_actual': round(actual['total_facturado']),
            'facturado_anterior': round(anterior['total_facturado']),
            'facturado_pct_cambio': _pct(actual['total_facturado'], anterior['total_facturado']),
        },
        'por_familia': cambios_por_familia,
    }


def get_pipeline_reservas_safe(days: int = 7) -> Optional[dict]:
    """Resumen comercial completo del pipeline Aremko.

    Cada bloque tiene su propio try/except para que un fallo aislado no
    deje al brief sin TODOS los datos. Los errores parciales se exponen
    en la clave '_errores' del output (visible en el brief).
    """
    from datetime import timedelta
    try:
        from django.db.models import Count, Sum, Avg
        from django.utils import timezone as dj_tz
        from ..models import VentaReserva, Pago, PendingReservation, ReservaServicio
    except Exception as exc:
        logger.warning(f'No se pudo importar modelos para pipeline: {exc}', exc_info=True)
        return {'_errores': [f'Imports fallaron: {exc}']}

    ahora = dj_tz.now()
    sem1_inicio = ahora - timedelta(days=7)
    sem2_inicio = ahora - timedelta(days=14)
    sem4_inicio = ahora - timedelta(days=30)
    prox_semana = ahora + timedelta(days=7)

    errores = []
    out = {
        'periodo_dias_default': 7,
        'fecha_corte': ahora.isoformat(),
    }

    # === Bloque A: periodos agregados ===
    try:
        ultima_semana = _agg_periodo(VentaReserva, Pago, ReservaServicio, sem1_inicio, ahora)
        semana_anterior = _agg_periodo(VentaReserva, Pago, ReservaServicio, sem2_inicio, sem1_inicio)
        ultimo_mes = _agg_periodo(VentaReserva, Pago, ReservaServicio, sem4_inicio, ahora)
        sem3_atras = _agg_periodo(VentaReserva, Pago, ReservaServicio, sem4_inicio, sem1_inicio)

        def _pct_change(actual, anterior):
            if not anterior:
                return None
            return round((actual - anterior) / anterior * 100, 1)

        out['ultima_semana'] = ultima_semana
        out['ultimo_mes'] = ultimo_mes
        out['tendencia_7d_vs_anterior'] = {
            'reservas_creadas_pct': _pct_change(ultima_semana['creadas'], semana_anterior['creadas']),
            'reservas_pagadas_pct': _pct_change(ultima_semana['pagadas'], semana_anterior['pagadas']),
            'facturado_pct': _pct_change(ultima_semana['total_facturado'], semana_anterior['total_facturado']),
            'ticket_promedio_pct': _pct_change(ultima_semana['ticket_promedio'], semana_anterior['ticket_promedio']),
            'datos_anterior': {
                'creadas': semana_anterior['creadas'],
                'pagadas': semana_anterior['pagadas'],
                'facturado': semana_anterior['total_facturado'],
                'ticket': semana_anterior['ticket_promedio'],
            },
        }

        # Métodos de pago con detección de cambios
        metodos_actual = ultima_semana['metodos_pago_count']
        metodos_3sem_previas = sem3_atras['metodos_pago_count']
        cambios_canales = []
        for metodo in metodos_actual:
            if metodos_actual.get(metodo, 0) > 0 and metodos_3sem_previas.get(metodo, 0) == 0:
                cambios_canales.append(
                    f"{metodo}: aparece esta semana ({metodos_actual[metodo]} pagos), 0 las 3 semanas previas — CANAL NUEVO"
                )
        for metodo in metodos_3sem_previas:
            count_previo = metodos_3sem_previas.get(metodo, 0)
            if metodos_actual.get(metodo, 0) == 0 and count_previo >= 3:
                cambios_canales.append(
                    f"{metodo}: desaparece esta semana, tenia {count_previo} pagos las 3 semanas previas"
                )
        out['metodos_pago_analisis'] = {
            'ultima_semana': metodos_actual,
            'ultimo_mes': ultimo_mes['metodos_pago_count'],
            'tres_semanas_previas': metodos_3sem_previas,
            'cambios_detectados': cambios_canales,
        }
    except Exception as exc:
        errores.append(f'periodos_agregados: {type(exc).__name__}: {exc}')
        logger.warning(f'Pipeline bloque periodos fallo: {exc}', exc_info=True)

    # === Bloque B: top servicios última semana ===
    try:
        out.setdefault('ultima_semana', {})['top_servicios'] = list(
            ReservaServicio.objects
            .filter(venta_reserva__fecha_reserva__gte=sem1_inicio, venta_reserva__estado_pago='pagado')
            .values('servicio__nombre', 'servicio__categoria__nombre')
            .annotate(c=Count('id'))
            .order_by('-c')[:10]
        )
    except Exception as exc:
        errores.append(f'top_servicios: {type(exc).__name__}: {exc}')
        logger.warning(f'Pipeline bloque top_servicios fallo: {exc}', exc_info=True)

    # === Bloque C: packs ===
    try:
        out['packs_ultima_semana'] = _detectar_packs(VentaReserva, ReservaServicio, sem1_inicio, ahora)
    except Exception as exc:
        errores.append(f'packs: {type(exc).__name__}: {exc}')
        logger.warning(f'Pipeline bloque packs fallo: {exc}', exc_info=True)

    # === Bloque D: comportamiento cliente (recurrencia + top recurrentes) ===
    try:
        ventas_sem = VentaReserva.objects.filter(
            fecha_reserva__gte=sem1_inicio, fecha_reserva__lt=ahora,
            estado_pago='pagado',
        ).select_related('cliente')
        total_sem = ventas_sem.count()
        recurrentes_count = 0
        for v in ventas_sem:
            if not v.cliente:
                continue
            previas = VentaReserva.objects.filter(
                cliente=v.cliente, estado_pago='pagado', fecha_reserva__lt=v.fecha_reserva,
            ).count()
            if previas >= 1:
                recurrentes_count += 1
        tasa_recurrencia = round(recurrentes_count / total_sem * 100, 1) if total_sem else 0
        top_recurrentes = list(
            VentaReserva.objects
            .filter(fecha_reserva__gte=sem4_inicio, estado_pago='pagado', cliente__isnull=False)
            .values('cliente__id', 'cliente__nombre', 'cliente__telefono')
            .annotate(reservas=Count('id'), gasto=Sum('total'))
            .filter(reservas__gte=2)
            .order_by('-reservas', '-gasto')[:10]
        )
        out['clientes'] = {
            'tasa_recurrencia_ultima_semana_pct': tasa_recurrencia,
            'recurrentes_ultima_semana': recurrentes_count,
            'total_pagadas_ultima_semana': total_sem,
            'top_recurrentes_ultimos_30d': top_recurrentes,
        }
    except Exception as exc:
        errores.append(f'comportamiento_cliente: {type(exc).__name__}: {exc}')
        logger.warning(f'Pipeline bloque clientes fallo: {exc}', exc_info=True)

    # === Bloque E: anticipación de reserva ===
    try:
        anticipacion_data = []
        for rs in ReservaServicio.objects.filter(
            venta_reserva__fecha_reserva__gte=sem1_inicio,
            venta_reserva__estado_pago='pagado',
        ).select_related('venta_reserva')[:200]:
            try:
                fecha_creacion = rs.venta_reserva.fecha_reserva.date()
                diff = (rs.fecha_agendamiento - fecha_creacion).days
                if diff >= 0:
                    anticipacion_data.append(diff)
            except Exception:
                continue
        if anticipacion_data:
            out['anticipacion_reserva'] = {
                'promedio_dias': round(sum(anticipacion_data) / len(anticipacion_data), 1),
                'min_dias': min(anticipacion_data),
                'max_dias': max(anticipacion_data),
                'mediana_dias': sorted(anticipacion_data)[len(anticipacion_data) // 2],
                'samples': len(anticipacion_data),
            }
        else:
            out['anticipacion_reserva'] = {}
    except Exception as exc:
        errores.append(f'anticipacion: {type(exc).__name__}: {exc}')
        logger.warning(f'Pipeline bloque anticipacion fallo: {exc}', exc_info=True)

    # === Bloque F: disponibilidad próxima semana ===
    try:
        reservas_proxima_semana = ReservaServicio.objects.filter(
            fecha_agendamiento__gte=ahora.date(),
            fecha_agendamiento__lte=prox_semana.date(),
            venta_reserva__estado_pago='pagado',
        ).count()
        servicios_top_proxima_semana = list(
            ReservaServicio.objects
            .filter(
                fecha_agendamiento__gte=ahora.date(),
                fecha_agendamiento__lte=prox_semana.date(),
                venta_reserva__estado_pago='pagado',
            )
            .values('servicio__nombre', 'servicio__categoria__nombre')
            .annotate(reservas=Count('id'))
            .order_by('-reservas')[:10]
        )
        out['disponibilidad_proxima_semana'] = {
            'reservas_confirmadas': reservas_proxima_semana,
            'top_servicios_agendados': servicios_top_proxima_semana,
        }
    except Exception as exc:
        errores.append(f'disponibilidad: {type(exc).__name__}: {exc}')
        logger.warning(f'Pipeline bloque disponibilidad fallo: {exc}', exc_info=True)

    # === Bloque G: PendingReservation (abandonos Flow) ===
    try:
        pending_qs = PendingReservation.objects.filter(created_at__gte=sem1_inicio)
        out['flow_abandonos_ultima_semana'] = {
            'pending_total': pending_qs.count(),
            'iniciados_aun_no_pagados': pending_qs.filter(estado='iniciado').count(),
            'expirados_sin_pago': pending_qs.filter(estado='expirado').count(),
            'confirmados_pago_exitoso': pending_qs.filter(estado='confirmado').count(),
            'rechazados': pending_qs.filter(estado='rechazado').count(),
        }
    except Exception as exc:
        errores.append(f'pending_flow: {type(exc).__name__}: {exc}')
        logger.warning(f'Pipeline bloque pending_flow fallo: {exc}', exc_info=True)

    # === Bloque H: comparativa mensual misma fecha (1-N mes actual vs 1-N mes anterior) ===
    try:
        out['comparativa_mensual_misma_fecha'] = _comparativa_mensual_misma_fecha(VentaReserva, ReservaServicio)
    except Exception as exc:
        errores.append(f'comparativa_mensual: {type(exc).__name__}: {exc}')
        logger.warning(f'Pipeline bloque comparativa_mensual fallo: {exc}', exc_info=True)

    if errores:
        out['_errores'] = errores

    # Si NINGUN bloque produjo datos, marcar como falla total
    bloques_con_datos = [
        k for k in out.keys()
        if k not in ('_errores', 'periodo_dias_default', 'fecha_corte') and out.get(k)
    ]
    if not bloques_con_datos:
        out['_falla_total'] = True

    return out


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


def get_meta_snapshot_safe(persist: bool = True, with_analysis: bool = True) -> Optional[dict]:
    """Trae snapshot Meta (FB + IG + Ads), genera analisis IA y persiste en BD.

    Args:
        persist: si True, guarda un MetaSnapshot con generado_por='cron_weekly'.
        with_analysis: si True, llama meta_analyzer para analisis IA y lo
            cachea en MetaSnapshot.analisis_ia.

    Devuelve dict con keys 'snapshot' y 'analysis' (ambos opcionalmente None
    si falla parcial). Devuelve None si falla todo.
    """
    try:
        from .meta_reporter import get_snapshot_safe
        snap = get_snapshot_safe(days=28)
        if snap is None:
            logger.warning('Meta snapshot no disponible (token o conectividad)')
            return None

        analysis = None
        if with_analysis:
            try:
                from .meta_analyzer import analyze_snapshot
                analysis = analyze_snapshot(snap)
                logger.info('Meta analysis IA generado correctamente para brief semanal')
            except Exception as exc:
                logger.warning(f'Meta analysis IA fallo (snapshot OK igual): {exc}')

        if persist:
            try:
                from ..models import MetaSnapshot
                import json
                error_msg = ''
                if snap.get('errors'):
                    error_msg = '; '.join(f'{k}: {v}' for k, v in snap['errors'].items())
                analisis_str = ''
                if analysis:
                    analisis_str = json.dumps(analysis, ensure_ascii=False, indent=2)
                MetaSnapshot.objects.create(
                    tipo='full',
                    period_days=28,
                    datos=snap,
                    analisis_ia=analisis_str,
                    generado_por='cron_weekly',
                    error=error_msg,
                )
            except Exception as exc:
                logger.warning(f'No se pudo persistir MetaSnapshot: {exc}')

        return {'snapshot': snap, 'analysis': analysis}
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
    meta_analysis: Optional[dict] = None,
    objetivo_semana: Optional[dict] = None,
    reviews_resumen: Optional[dict] = None,
    calendario_chile: Optional[str] = None,
    pipeline_reservas: Optional[dict] = None,
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
        meta_analysis=meta_analysis,
        objetivo_semana=objetivo_semana,
        reviews_resumen=reviews_resumen,
        calendario_chile=calendario_chile,
        pipeline_reservas=pipeline_reservas,
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
        max_tokens=32000,  # brief extenso con resumen ejecutivo + diagnostico + drafts + acciones
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
    meta_bundle = get_meta_snapshot_safe(persist=True, with_analysis=True)
    meta_snapshot = meta_bundle.get('snapshot') if meta_bundle else None
    meta_analysis = meta_bundle.get('analysis') if meta_bundle else None
    objetivo_semana = get_objetivo_semana_safe()
    reviews_resumen = get_reviews_resumen_safe()
    calendario_chile = get_calendario_chile_safe()
    pipeline_reservas = get_pipeline_reservas_safe(days=7)
    if pipeline_reservas and pipeline_reservas.get('_errores'):
        logger.warning(f'Pipeline interno con errores parciales: {pipeline_reservas["_errores"]}')
    if pipeline_reservas and pipeline_reservas.get('_falla_total'):
        logger.error(f'Pipeline interno FALLO TOTAL — todos los bloques erroneados')

    brief = call_llm(
        semana_inicio=semana_inicio,
        semana_fin=semana_fin,
        frases_clientes=frases,
        blog_posts_recientes=posts,
        alertas_analisis_ia=alertas,
        ga4_snapshot=ga4_snapshot,
        gsc_snapshot=gsc_snapshot,
        meta_snapshot=meta_snapshot,
        meta_analysis=meta_analysis,
        objetivo_semana=objetivo_semana,
        reviews_resumen=reviews_resumen,
        calendario_chile=calendario_chile,
        pipeline_reservas=pipeline_reservas,
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
        'meta_analysis': meta_analysis,
        'objetivo_semana': objetivo_semana,
        'reviews_resumen': reviews_resumen,
        'pipeline_reservas': pipeline_reservas,
        'metricas_disponibles': bool(ga4_snapshot or gsc_snapshot or meta_snapshot),
    }
