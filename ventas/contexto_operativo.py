"""Generador de la sección automática del Contexto Operativo.

Introspecta el código y la BD para producir un markdown con:
- Templates SMS / Email activos
- Tareas programadas (management commands disparados por cron-job.org)
- Promociones / paquetes vigentes
- Campañas activas
- Convenios (si hay)
- Hardcoded business rules conocidas

Diseño: omitir secciones vacías (no imprimir "## X\n(ninguno)"). Salidas
limpias para inyectar al system prompt de análisis IA.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import List

from django.utils import timezone

logger = logging.getLogger(__name__)


# Schedules conocidos en cron-job.org (hardcoded porque cron-job.org es externo
# y no tenemos forma de leer programación desde acá). Actualizar manualmente si
# se agregan/quitan jobs.
CRON_JOBS_CONOCIDOS = [
    {
        'comando': 'generate_weekly_marketing_brief',
        'schedule': 'Lunes 10:00 hora Chile',
        'descripcion': 'Genera brief semanal de marketing con análisis IA (GA4 + Meta + Reviews + Pipeline)',
    },
    {
        'comando': 'snapshot_weekly_traffic',
        'schedule': 'Lunes 09:00 hora Chile',
        'descripcion': 'Persiste snapshot semanal GA4 + Search Console para series históricas',
    },
    {
        'comando': 'analyze_surveys_weekly',
        'schedule': 'Lunes 09:00 hora Chile',
        'descripcion': 'Análisis IA semanal de encuestas de satisfacción',
    },
    {
        'comando': 'send_communication_triggers',
        'schedule': 'Diario (varios horarios según trigger)',
        'descripcion': (
            'Disparador central: recordatorios 24h, post-visita NPS (D+1), reactivación 90d, '
            'cumpleaños, newsletters segmentados'
        ),
    },
    {
        'comando': 'cleanup_pending_reservations',
        'schedule': 'Cada 30 min (sugerido, verificar configuración)',
        'descripcion': 'Expira PendingReservation sin pago confirmado',
    },
    {
        'comando': 'report_pending_followups',
        'schedule': 'Diario (sugerido)',
        'descripcion': 'Reporte VoC con follow-ups pendientes + sugerencia WhatsApp por IA',
    },
]


# Reglas de negocio hardcoded en código que no están en BD pero el LLM debería saber.
REGLAS_HARDCODED = [
    {
        'nombre': 'Anti-spam por cliente',
        'descripcion': (
            'SMS: máximo 2/día y 8/mes por cliente. Email: 1/semana y 4/mes. '
            'Configurable vía env vars SMS_DAILY_LIMIT_PER_CLIENT, EMAIL_WEEKLY_LIMIT_PER_CLIENT, etc.'
        ),
    },
    {
        'nombre': 'Horario preferido del cliente',
        'descripcion': (
            'Las comunicaciones automáticas respetan los campos '
            'horario_preferido_inicio / horario_preferido_fin del Cliente.'
        ),
    },
    {
        'nombre': 'Cabañas con check-in 16:00 fijo',
        'descripcion': (
            'En el carrito web, cualquier hora seleccionada para cabaña se normaliza a 16:00 '
            '(servidor-side override en ventas/views/checkout_views.py).'
        ),
    },
    {
        'nombre': 'Ambientaciones requieren tina',
        'descripcion': (
            'Las decoraciones/ambientaciones solo se pueden agregar al carrito si ya hay '
            'una tina reservada. Heredan fecha/hora de la última tina del carrito.'
        ),
    },
    {
        'nombre': 'Desayuno con cabaña: auto-mapeo',
        'descripcion': (
            'Al agregar "Desayuno" al carrito, el sistema reemplaza por el desayuno '
            'específico de la cabaña reservada (Torre/Laurel/Arrayan/Tepa/Acantilado). '
            'Distribución cíclica si hay múltiples cabañas.'
        ),
    },
    {
        'nombre': 'Tinas y cabañas con precio plano',
        'descripcion': (
            'Tinas (Calbuco, Osorno, Tronador, Hornopirén, Llaima, Puntiagudo, Puyehue, Villarrica) '
            'y cabañas cobran SIEMPRE precio_base × capacidad_máxima, ignorando la cantidad '
            'enviada desde el cliente (override server-side AR-014).'
        ),
    },
]


def _seccion(titulo: str, items: List[str]) -> str:
    """Formatea una sección. Devuelve cadena vacía si no hay items (para omitir)."""
    if not items:
        return ''
    body = '\n'.join(items)
    return f'## {titulo}\n{body}\n'


def _sms_templates_section() -> str:
    """Templates SMS activos por tipo."""
    try:
        from .models import SMSTemplate
        templates = SMSTemplate.objects.filter(is_active=True).order_by('message_type', 'name')
        items = []
        for t in templates:
            tipo_humano = t.get_message_type_display()
            items.append(f'- **{t.name}** ({tipo_humano}): "{t.content[:120].strip()}..."' if len(t.content) > 120
                         else f'- **{t.name}** ({tipo_humano}): "{t.content.strip()}"')
        return _seccion('Plantillas de SMS activas', items)
    except Exception as exc:
        logger.warning(f'contexto_operativo: SMS templates error: {exc}')
        return ''


def _email_templates_section() -> str:
    """Templates Email activos."""
    try:
        from .models import EmailTemplate
        templates = EmailTemplate.objects.filter(is_active=True).order_by('campaign_type', 'name')
        items = []
        for t in templates:
            items.append(f'- **{t.name}** ({t.get_campaign_type_display()}) — asunto: "{t.subject[:80]}"')
        return _seccion('Plantillas de Email activas', items)
    except Exception as exc:
        logger.warning(f'contexto_operativo: Email templates error: {exc}')
        return ''


def _packs_section() -> str:
    """Packs de descuento vigentes."""
    try:
        from .models import PackDescuento
        hoy = timezone.now().date()
        packs = PackDescuento.objects.filter(activo=True).order_by('-prioridad', 'nombre')
        items = []
        for p in packs:
            # Vigente si no tiene fecha_fin o fecha_fin >= hoy y fecha_inicio <= hoy
            if p.fecha_inicio and p.fecha_inicio > hoy:
                continue
            if p.fecha_fin and p.fecha_fin < hoy:
                continue
            vigencia = f'desde {p.fecha_inicio}'
            if p.fecha_fin:
                vigencia += f' hasta {p.fecha_fin}'
            else:
                vigencia += ' (sin fecha de fin)'
            descuento_str = f'${int(p.descuento):,}'.replace(',', '.')
            items.append(
                f'- **{p.nombre}**: descuento de {descuento_str}. {p.descripcion[:200].strip()} '
                f'(vigencia: {vigencia}, prioridad {p.prioridad})'
            )
        return _seccion('Packs de Descuento Vigentes', items)
    except Exception as exc:
        logger.warning(f'contexto_operativo: Packs error: {exc}')
        return ''


def _campaigns_section() -> str:
    """Campañas activas (Campaign con estado activo en últimos 90 días)."""
    try:
        from .models import Campaign
        hoy = timezone.now().date()
        # Verificar nombres de campos disponibles en Campaign.
        campaigns = Campaign.objects.all().order_by('-id')[:20]
        items = []
        for c in campaigns:
            estado = getattr(c, 'estado', None) or getattr(c, 'status', None) or '?'
            nombre = getattr(c, 'nombre', None) or getattr(c, 'name', None) or f'Campaign #{c.id}'
            # Filtrar manualmente las "activas" — el campo puede tener varios nombres
            if str(estado).lower() not in ('activa', 'active', 'enviando', 'running', 'programada'):
                continue
            descripcion = (getattr(c, 'descripcion', '') or getattr(c, 'description', ''))[:150]
            items.append(f'- **{nombre}** (estado: {estado}): {descripcion}')
        # Cap a 10 items para no inflar
        items = items[:10]
        return _seccion('Campañas Activas', items)
    except Exception as exc:
        logger.warning(f'contexto_operativo: Campaigns error: {exc}')
        return ''


def _cron_jobs_section() -> str:
    """Tareas programadas conocidas (cron-job.org externo)."""
    items = [
        f'- **{j["comando"]}** ({j["schedule"]}): {j["descripcion"]}'
        for j in CRON_JOBS_CONOCIDOS
    ]
    return _seccion('Tareas Programadas (cron-job.org)', items)


def _reglas_hardcoded_section() -> str:
    """Reglas de negocio hardcoded en código."""
    items = [f'- **{r["nombre"]}**: {r["descripcion"]}' for r in REGLAS_HARDCODED]
    return _seccion('Reglas de Negocio Aplicadas en el Sistema', items)


def _giftcards_section() -> str:
    """Resumen de gift cards activas/disponibles."""
    try:
        from .models import GiftCard
        hoy = timezone.now().date()
        activas = GiftCard.objects.filter(
            fecha_vencimiento__gte=hoy,
            monto_disponible__gt=0,
        ).count()
        if activas == 0:
            return ''
        return _seccion('Gift Cards', [
            f'- **{activas} gift cards activas** (con saldo disponible y no vencidas)',
            '- Las gift cards se compran online, vienen con código único y se aplican como '
            'método de pago al checkout. PDF se genera y envía por email al destinatario.',
        ])
    except Exception as exc:
        logger.warning(f'contexto_operativo: GiftCards error: {exc}')
        return ''


def _comunicaciones_section() -> str:
    """Triggers de comunicación automáticos (mailers + SMS)."""
    items = [
        '- **Confirmación de reserva**: inmediata al crear reserva o confirmar pago Flow.cl',
        '- **Recordatorio 24h antes**: cron diario (a través de send_communication_triggers)',
        '- **Encuesta post-visita NPS**: D+1 después del servicio',
        '- **Reactivación**: clientes inactivos hace 90 días',
        '- **Cumpleaños**: una vez al año por cliente',
        '- **Newsletter**: segmentado por persona/frecuencia/gasto',
        '- **Confirmación Meta CAPI**: server-side al confirmar pago (Pixel + CAPI dedupe via event_id)',
    ]
    return _seccion('Triggers de Comunicación Automáticos', items)


def generar_seccion_automatica() -> str:
    """Punto de entrada: arma el markdown completo de la sección automática."""
    secciones = [
        _comunicaciones_section(),
        _sms_templates_section(),
        _email_templates_section(),
        _packs_section(),
        _giftcards_section(),
        _campaigns_section(),
        _cron_jobs_section(),
        _reglas_hardcoded_section(),
    ]
    # Filtrar secciones vacías y concatenar.
    contenido = '\n'.join(s for s in secciones if s).strip()
    if not contenido:
        return ''

    header = (
        f'# Contexto Operativo Aremko Spa Boutique\n'
        f'_(generado automáticamente desde el código y la BD — {timezone.now().strftime("%Y-%m-%d %H:%M")} hora servidor)_\n\n'
        f'Este bloque describe procesos, reglas, automatizaciones y promociones que YA están '
        f'activos en Aremko. Úsalo para evitar recomendar acciones que ya están implementadas y '
        f'para sugerir mejoras incrementales sobre lo existente.\n'
    )
    return header + '\n' + contenido + '\n'


def regenerar_y_guardar() -> str:
    """Regenera la sección automática y la guarda en el singleton ContextoOperativo.

    Devuelve el markdown generado (str). Si falla, levanta excepción.
    """
    from .models import ContextoOperativo
    obj = ContextoOperativo.get_solo()
    contenido = generar_seccion_automatica()
    obj.seccion_automatica_cache = contenido
    obj.seccion_automatica_actualizada_en = timezone.now()
    obj.save(update_fields=['seccion_automatica_cache', 'seccion_automatica_actualizada_en'])
    logger.info(f'ContextoOperativo regenerado: {len(contenido)} chars')
    return contenido
