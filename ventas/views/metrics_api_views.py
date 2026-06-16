"""Métricas / Tablero de Evolución (H-021) — endpoints de agregación read-only.

Series semanales (ISO week) sobre data que YA existe, consumidas por aremko-cli para
la página "Métricas / Evolución". Auth: header X-API-Key (LUNA_API_KEY), igual que
`/api/whatsapp/*`. Param `weeks` (default 12, máx 52). Montos en CLP enteros.

Rutas:
  GET /api/metrics/campanas?weeks=12  → funnel + ROI de la Bandeja de envíos (ContactoWhatsApp)
  GET /api/metrics/agente?weeks=12     → curva del agente IA (AgenteFeedback)
  GET /api/metrics/canales?weeks=12    → volumen WhatsApp vs Instagram + 1ª respuesta + backlog
  GET /api/metrics/masajes?weeks=12    → cobertura de seguimientos de masaje
"""

from datetime import datetime, timedelta

from django.http import JsonResponse
from django.utils import timezone

from .whatsapp_api_views import _check_luna_key

# Estimación de minutos de redacción que ahorra cada borrador aceptado (sin editar).
MIN_POR_REDACCION = 2


# ---------------------------------------------------------------------------
# Helpers de tiempo / agregación
# ---------------------------------------------------------------------------

def _weeks_param(request, default=12, cap=52):
    try:
        w = int(request.GET.get('weeks', default))
    except (ValueError, TypeError):
        w = default
    return max(1, min(w, cap))


def _label(d):
    """date -> 'YYYY-Www' (ISO week)."""
    iso = d.isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


def _label_dt(dt):
    """datetime aware -> etiqueta de semana ISO en hora local."""
    return _label(timezone.localtime(dt).date())


def _semanas(weeks):
    """Lista ordenada [(label, lunes_date)] de las últimas `weeks` semanas ISO (incluida la actual)."""
    hoy = timezone.localdate()
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    return [( _label(lunes_actual - timedelta(weeks=i)), lunes_actual - timedelta(weeks=i))
            for i in range(weeks - 1, -1, -1)]


def _mediana(valores):
    vals = sorted(valores)
    n = len(vals)
    if n == 0:
        return None
    mid = n // 2
    return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2


# ---------------------------------------------------------------------------
# 1) Campañas — funnel + ROI (ContactoWhatsApp)
# ---------------------------------------------------------------------------

def metrics_campanas(request):
    err = _check_luna_key(request)
    if err:
        return err
    weeks = _weeks_param(request)
    semanas = _semanas(weeks)
    desde = semanas[0][1]
    labels = [l for l, _ in semanas]
    serie = {l: {'semana': l, 'enviados': 0, 'costo': None, 'respondieron': 0,
                 'reservaron': 0, 'ingreso': 0} for l in labels}

    from ..models import ContactoWhatsApp
    from whatsapp_agent.models import WhatsAppAgentConfig
    tarifa = int(WhatsAppAgentConfig.get_solo().tarifa_plantilla_clp or 0)

    # Actividad por fecha_envio: los enviados son lo que cuesta y lo que genera ingreso.
    enviados_qs = (ContactoWhatsApp.objects
                   .filter(estado='enviado', fecha_envio__isnull=False, fecha_envio__date__gte=desde)
                   .select_related('reserva_atribuida'))
    for c in enviados_qs:
        b = serie.get(_label_dt(c.fecha_envio))
        if not b:
            continue
        b['enviados'] += 1
        if c.respondio:
            b['respondieron'] += 1
        if c.reserva_atribuida_id:
            b['reservaron'] += 1
            b['ingreso'] += int(getattr(c.reserva_atribuida, 'total', 0) or 0)
    for l in labels:
        serie[l]['costo'] = (serie[l]['enviados'] * tarifa) if tarifa else None

    enviados = sum(serie[l]['enviados'] for l in labels)
    respondieron = sum(serie[l]['respondieron'] for l in labels)
    reservaron = sum(serie[l]['reservaron'] for l in labels)
    ingreso = sum(serie[l]['ingreso'] for l in labels)
    # Top del funnel por cohorte propuesta en el período (fecha_sugerido).
    generados = ContactoWhatsApp.objects.filter(fecha_sugerido__gte=desde).count()
    aprobados = ContactoWhatsApp.objects.filter(
        fecha_sugerido__gte=desde, estado__in=['aprobado', 'enviado']).count()

    costo = enviados * tarifa if tarifa else None
    roi_neto = (ingreso - costo) if costo is not None else None
    roas = round(ingreso / costo, 1) if costo else None

    return JsonResponse({
        'weeks': weeks,
        'tarifa_plantilla_clp': tarifa or None,
        'resumen': {
            'generados': generados, 'aprobados': aprobados, 'enviados': enviados,
            'respondieron': respondieron, 'reservaron': reservaron,
            'ingreso_atribuido': ingreso, 'costo_estimado': costo,
            'roi_neto': roi_neto, 'roas': roas,
        },
        'series': [serie[l] for l in labels],
    })


# ---------------------------------------------------------------------------
# 2) Agente IA — curva de calidad (AgenteFeedback / SugerenciaAgenteWhatsApp)
# ---------------------------------------------------------------------------

def metrics_agente(request):
    err = _check_luna_key(request)
    if err:
        return err
    weeks = _weeks_param(request)
    semanas = _semanas(weeks)
    desde = semanas[0][1]
    labels = [l for l, _ in semanas]
    serie = {l: {'semana': l, 'total': 0, 'sin_editar': 0, 'pct_sin_editar': 0,
                 'escalados': 0, 'pct_escalado': 0} for l in labels}

    from whatsapp_agent.models import (
        AgenteFeedback, SugerenciaAgenteWhatsApp, SugerenciaAprendizaje)

    # % sin editar (de los borradores con texto que Deborah usó).
    for f in AgenteFeedback.objects.filter(created_at__date__gte=desde):
        b = serie.get(_label_dt(f.created_at))
        if not b or not (f.borrador or '').strip():
            continue
        b['total'] += 1
        if not f.editado:
            b['sin_editar'] += 1

    # Escalados sobre el total de sugerencias generadas esa semana.
    sug_total = {l: 0 for l in labels}
    for s in SugerenciaAgenteWhatsApp.objects.filter(created_at__date__gte=desde).only('created_at', 'escalar'):
        l = _label_dt(s.created_at)
        if l not in serie:
            continue
        sug_total[l] += 1
        if s.escalar:
            serie[l]['escalados'] += 1

    for l in labels:
        b = serie[l]
        b['pct_sin_editar'] = round(100 * b['sin_editar'] / b['total']) if b['total'] else 0
        b['pct_escalado'] = round(100 * b['escalados'] / sug_total[l]) if sug_total[l] else 0

    total = sum(serie[l]['total'] for l in labels)
    sin_editar = sum(serie[l]['sin_editar'] for l in labels)
    pct_sin_editar = round(100 * sin_editar / total) if total else 0
    delta = None
    if len(labels) >= 9:
        delta = serie[labels[-1]]['pct_sin_editar'] - serie[labels[-9]]['pct_sin_editar']
    aprendizajes = SugerenciaAprendizaje.objects.filter(
        estado='aprobada', resuelto_at__date__gte=desde).count()

    return JsonResponse({
        'weeks': weeks,
        'resumen': {
            'pct_sin_editar': pct_sin_editar,
            'delta_pts_8sem': delta,
            'aprendizajes_aprobados': aprendizajes,
            'tiempo_ahorrado_min_estim': sin_editar * MIN_POR_REDACCION,
        },
        'series': [serie[l] for l in labels],
    })


# ---------------------------------------------------------------------------
# 3) Canales — volumen + 1ª respuesta + backlog (WhatsApp + Instagram)
# ---------------------------------------------------------------------------

def _acumular_primera_respuesta(rows, key, deltas_por_semana):
    """Por conversación, delta (min) del primer entrante sin responder hasta la 1ª salida."""
    convs = {}
    for r in rows:
        convs.setdefault(r[key], []).append((r['timestamp'], r['direction']))
    for msgs in convs.values():
        msgs.sort(key=lambda x: x[0])
        primer_in = None
        for ts, direction in msgs:
            if direction == 'in':
                if primer_in is None:
                    primer_in = ts
            elif primer_in is not None:
                dmin = (ts - primer_in).total_seconds() / 60.0
                if dmin >= 0:
                    ds = deltas_por_semana.get(_label_dt(primer_in))
                    if ds is not None:
                        ds.append(dmin)
                primer_in = None


def metrics_canales(request):
    err = _check_luna_key(request)
    if err:
        return err
    weeks = _weeks_param(request)
    semanas = _semanas(weeks)
    desde = semanas[0][1]
    labels = [l for l, _ in semanas]
    serie = {l: {'semana': l, 'whatsapp': 0, 'instagram': 0,
                 'primera_respuesta_mediana_min': None} for l in labels}

    from ..models import WhatsAppMessage
    from inbox_omnicanal.models import ChannelMessage

    # Volumen = entrantes por canal por semana.
    for ts in (WhatsAppMessage.objects.filter(direction='in', timestamp__date__gte=desde)
               .values_list('timestamp', flat=True)):
        b = serie.get(_label_dt(ts))
        if b:
            b['whatsapp'] += 1
    for ts in (ChannelMessage.objects.filter(canal='instagram', direction='in', timestamp__date__gte=desde)
               .values_list('timestamp', flat=True)):
        b = serie.get(_label_dt(ts))
        if b:
            b['instagram'] += 1

    # Primera respuesta (mediana por semana + global).
    deltas = {l: [] for l in labels}
    _acumular_primera_respuesta(
        WhatsAppMessage.objects.filter(timestamp__date__gte=desde).values('phone', 'direction', 'timestamp'),
        'phone', deltas)
    _acumular_primera_respuesta(
        ChannelMessage.objects.filter(canal='instagram', timestamp__date__gte=desde)
        .values('external_id', 'direction', 'timestamp'),
        'external_id', deltas)
    todos = []
    for l in labels:
        m = _mediana(deltas[l])
        serie[l]['primera_respuesta_mediana_min'] = round(m) if m is not None else None
        todos += deltas[l]
    mediana_global = _mediana(todos)

    backlog_wa = (WhatsAppMessage.objects.filter(direction='in', requiere_atencion=True)
                  .values('phone').distinct().count())
    backlog_ig = (ChannelMessage.objects.filter(canal='instagram', direction='in', requiere_atencion=True)
                  .values('external_id').distinct().count())

    return JsonResponse({
        'weeks': weeks,
        'resumen': {
            'backlog_actual': backlog_wa + backlog_ig,
            'primera_respuesta_mediana_min': round(mediana_global) if mediana_global is not None else None,
        },
        'series': [serie[l] for l in labels],
    })


# ---------------------------------------------------------------------------
# 4) Masajes — cobertura de seguimientos (SeguimientoBienestarMasaje)
# ---------------------------------------------------------------------------

def metrics_masajes(request):
    err = _check_luna_key(request)
    if err:
        return err
    weeks = _weeks_param(request)
    semanas = _semanas(weeks)
    desde = semanas[0][1]
    labels = [l for l, _ in semanas]
    serie = {l: {'semana': l, 'programados': 0, 'enviados': 0, 'cobertura_pct': 0} for l in labels}

    from ..models import SeguimientoBienestarMasaje
    for s in (SeguimientoBienestarMasaje.objects.filter(fecha_programada__date__gte=desde)
              .values('estado', 'fecha_programada')):
        b = serie.get(_label_dt(s['fecha_programada']))
        if not b:
            continue
        b['programados'] += 1
        if s['estado'] == 'enviado':
            b['enviados'] += 1
    for l in labels:
        b = serie[l]
        b['cobertura_pct'] = round(100 * b['enviados'] / b['programados']) if b['programados'] else 0

    enviados = sum(serie[l]['enviados'] for l in labels)
    programados = sum(serie[l]['programados'] for l in labels)
    cobertura = round(100 * enviados / programados) if programados else 0

    return JsonResponse({
        'weeks': weeks,
        'resumen': {
            'cobertura_pct': cobertura,           # % de seguimientos programados que se enviaron
            'tasa_respuesta_pct': None,           # no disponible (ver nota)
        },
        'nota': ('cobertura_pct = enviados/programados (entrega de los seguimientos agendados). '
                 'tasa_respuesta_pct NO disponible: SeguimientoBienestarMasaje no registra la '
                 'respuesta del cliente (solo el envío) → requiere un campo nuevo (Fase 2).'),
        'series': [serie[l] for l in labels],
    })
