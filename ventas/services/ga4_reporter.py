"""
GA4 Reporting API client (Tarea 2.3 plan maestro).

Consulta Google Analytics Data API v1 para traer métricas de los últimos 7 días
y los 7 anteriores, para alimentar el brief semanal de marketing y el análisis
IA de encuestas (cruzar NPS con conversiones reales).

Autenticación: service account JSON.
- GOOGLE_SERVICE_ACCOUNT_JSON (string completo del JSON, recomendado en Render)
- GOOGLE_SERVICE_ACCOUNT_FILE (path al archivo, alternativa local)

Property: GA4_PROPERTY_ID en settings (numérico, no Measurement ID).

Eventos custom que ya emite el sitio (Tarea 2.2):
- whatsapp_click, phone_click, cta_blog_click
- reservation_started, reservation_completed (también marcado como conversión)
"""
import json
import logging
from datetime import date, timedelta
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_credentials():
    """Construye las credenciales del service account desde settings."""
    from google.oauth2 import service_account

    raw_json = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_JSON', '') or ''
    file_path = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', '') or ''

    scopes = [
        'https://www.googleapis.com/auth/analytics.readonly',
        'https://www.googleapis.com/auth/webmasters.readonly',
    ]

    if raw_json.strip():
        info = json.loads(raw_json)
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)
    if file_path:
        return service_account.Credentials.from_service_account_file(file_path, scopes=scopes)
    raise ValueError('No hay credenciales: define GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_SERVICE_ACCOUNT_FILE')


def _client():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    creds = _get_credentials()
    return BetaAnalyticsDataClient(credentials=creds)


def _property_path() -> str:
    pid = getattr(settings, 'GA4_PROPERTY_ID', '') or ''
    if not pid:
        raise ValueError('GA4_PROPERTY_ID no configurado')
    return f'properties/{pid}'


def _run_report(metrics: list, dimensions: Optional[list], date_ranges: list,
                dimension_filter=None, order_bys=None, limit: int = 100) -> dict:
    """Wrapper genérico sobre runReport. Devuelve dict con rows."""
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, OrderBy, RunReportRequest,
    )

    client = _client()
    request = RunReportRequest(
        property=_property_path(),
        dimensions=[Dimension(name=d) for d in (dimensions or [])],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=dr['start'], end_date=dr['end'], name=dr.get('name', ''))
                     for dr in date_ranges],
        limit=limit,
    )
    if dimension_filter is not None:
        request.dimension_filter = dimension_filter
    if order_bys:
        request.order_bys = order_bys

    response = client.run_report(request)

    metric_headers = [h.name for h in response.metric_headers]
    dim_headers = [h.name for h in response.dimension_headers]

    rows = []
    for row in response.rows:
        item = {}
        for i, dh in enumerate(dim_headers):
            item[dh] = row.dimension_values[i].value
        for i, mh in enumerate(metric_headers):
            v = row.metric_values[i].value
            try:
                item[mh] = float(v) if '.' in v else int(v)
            except (ValueError, TypeError):
                item[mh] = v
        rows.append(item)

    totals = []
    for total in response.totals:
        item = {}
        for i, mh in enumerate(metric_headers):
            v = total.metric_values[i].value
            try:
                item[mh] = float(v) if '.' in v else int(v)
            except (ValueError, TypeError):
                item[mh] = v
        totals.append(item)

    return {
        'rows': rows,
        'totals': totals,
        'row_count': response.row_count,
    }


def _date_ranges_last_7_and_prev() -> list:
    """Últimos 7 días vs los 7 anteriores."""
    today = date.today()
    end_curr = today - timedelta(days=1)        # ayer
    start_curr = today - timedelta(days=7)      # hace 7 días
    end_prev = start_curr - timedelta(days=1)
    start_prev = start_curr - timedelta(days=7)
    return [
        {'name': 'last_7d', 'start': start_curr.isoformat(), 'end': end_curr.isoformat()},
        {'name': 'prev_7d', 'start': start_prev.isoformat(), 'end': end_prev.isoformat()},
    ]


def get_overview_last_7d_vs_prev() -> dict:
    """Métricas globales: sesiones, usuarios, engagement, conversiones."""
    metrics = [
        'sessions',
        'totalUsers',
        'newUsers',
        'engagedSessions',
        'averageSessionDuration',
        'screenPageViews',
        'conversions',
    ]
    ranges = _date_ranges_last_7_and_prev()
    out = {'last_7d': {}, 'prev_7d': {}}
    for r in ranges:
        res = _run_report(metrics=metrics, dimensions=None, date_ranges=[r])
        if res['totals']:
            out[r['name']] = res['totals'][0]
        elif res['rows']:
            out[r['name']] = res['rows'][0]
    return out


def get_traffic_sources_last_7d(limit: int = 10) -> list:
    """Top fuentes de tráfico por sesiones (últimos 7 días)."""
    from google.analytics.data_v1beta.types import OrderBy

    ranges = _date_ranges_last_7_and_prev()[:1]  # solo last_7d
    res = _run_report(
        metrics=['sessions', 'engagedSessions', 'conversions'],
        dimensions=['sessionDefaultChannelGroup', 'sessionSource'],
        date_ranges=ranges,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name='sessions'), desc=True)],
        limit=limit,
    )
    return res['rows']


def get_top_pages_last_7d(limit: int = 15) -> list:
    """Top páginas por sesiones."""
    from google.analytics.data_v1beta.types import OrderBy

    ranges = _date_ranges_last_7_and_prev()[:1]
    res = _run_report(
        metrics=['sessions', 'screenPageViews', 'engagementRate'],
        dimensions=['pagePath'],
        date_ranges=ranges,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name='sessions'), desc=True)],
        limit=limit,
    )
    return res['rows']


def get_custom_events_last_7d() -> dict:
    """Conteo de eventos custom de Aremko (Tarea 2.2)."""
    from google.analytics.data_v1beta.types import (
        Filter, FilterExpression, FilterExpressionList, OrderBy,
    )

    event_names = [
        'whatsapp_click',
        'phone_click',
        'cta_blog_click',
        'reservation_started',
        'reservation_completed',
        # Programa Refugio (paquete 3D/2N $270K, landing aremko.cl/refugio).
        # Disparados desde refugio_landing.html via gtag(). El brief semanal
        # los usa para medir conversión del soft-launch sin depender solo
        # del Pixel Meta.
        'refugio_view',
        'refugio_form_submit',
        'refugio_garantia_click',
    ]

    filt = FilterExpression(
        filter=Filter(
            field_name='eventName',
            in_list_filter=Filter.InListFilter(values=event_names),
        )
    )

    out = {}
    for r in _date_ranges_last_7_and_prev():
        res = _run_report(
            metrics=['eventCount'],
            dimensions=['eventName'],
            date_ranges=[r],
            dimension_filter=filt,
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name='eventCount'), desc=True)],
        )
        bucket = {ev: 0 for ev in event_names}
        for row in res['rows']:
            bucket[row.get('eventName', '')] = row.get('eventCount', 0)
        out[r['name']] = bucket
    return out


def get_conversions_by_source_medium(days: int = 28, limit: int = 100) -> dict:
    """Conversiones por evento × source × medium (atribución multi-canal).

    Espejo del reporte que muestra el agente aremko-cli en dashboard web:
    para cada evento custom (whatsapp_click, refugio_form_submit,
    reservation_completed, etc.), trae cuántas conversions/users vinieron
    de cada source/medium combinado.

    Returns:
        dict con keys:
          'total_conversions': int (suma de conversions de TODOS los eventos)
          'total_users': int (usuarios únicos que convirtieron)
          'by_event': dict {eventName: {conversions, eventCount, totalUsers}}
          'by_source': lista de dicts con eventName, source, medium,
                       conversions, totalUsers (top N por conversions)
          'period_days': N
    """
    from google.analytics.data_v1beta.types import OrderBy

    start = (date.today() - timedelta(days=days)).isoformat()
    end = (date.today() - timedelta(days=1)).isoformat()
    ranges = [{'name': f'last_{days}d', 'start': start, 'end': end}]

    # --- A) Agregado por evento ---
    res_evt = _run_report(
        metrics=['conversions', 'eventCount', 'totalUsers'],
        dimensions=['eventName'],
        date_ranges=ranges,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name='conversions'), desc=True)],
        limit=50,
    )

    by_event = {}
    total_conversions = 0
    total_users = 0
    for row in res_evt['rows']:
        evt = row.get('eventName', '')
        convs = row.get('conversions', 0)
        # Solo nos interesan eventos que son conversion (conversions > 0)
        if convs > 0:
            by_event[evt] = {
                'conversions': convs,
                'event_count': row.get('eventCount', 0),
                'users': row.get('totalUsers', 0),
            }
            total_conversions += convs
    # totalUsers del overall (para deduplicar usuarios que convirtieron en varios eventos)
    if res_evt.get('totals'):
        total_users = res_evt['totals'][0].get('totalUsers', 0)

    # --- B) Breakdown por evento × source × medium ---
    res_attr = _run_report(
        metrics=['conversions', 'totalUsers'],
        dimensions=['eventName', 'sessionSource', 'sessionMedium'],
        date_ranges=ranges,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name='conversions'), desc=True)],
        limit=limit,
    )
    by_source = []
    for row in res_attr['rows']:
        if row.get('conversions', 0) > 0:  # filtrar filas vacías
            by_source.append({
                'event': row.get('eventName', ''),
                'source': row.get('sessionSource', '(not set)'),
                'medium': row.get('sessionMedium', '(not set)'),
                'conversions': row.get('conversions', 0),
                'users': row.get('totalUsers', 0),
            })

    return {
        'period_days': days,
        'total_conversions': total_conversions,
        'total_users': total_users,
        'by_event': by_event,
        'by_source_medium': by_source,
    }


def get_top_traffic_sources_with_conversion(days: int = 28, limit: int = 15) -> list:
    """Top fuentes de tráfico CON conversion rate (útil para evaluar qué canales convierten mejor).

    Distinto a get_traffic_sources_last_7d() que solo trae sesiones. Acá calculamos
    conversion_rate (conversions / sessions) — la métrica clave para priorizar inversión.
    """
    from google.analytics.data_v1beta.types import OrderBy

    start = (date.today() - timedelta(days=days)).isoformat()
    end = (date.today() - timedelta(days=1)).isoformat()
    ranges = [{'name': f'last_{days}d', 'start': start, 'end': end}]

    res = _run_report(
        metrics=['sessions', 'totalUsers', 'engagedSessions', 'conversions',
                 'bounceRate', 'averageSessionDuration'],
        dimensions=['sessionDefaultChannelGroup', 'sessionSource', 'sessionMedium'],
        date_ranges=ranges,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name='sessions'), desc=True)],
        limit=limit,
    )

    out = []
    for row in res['rows']:
        sessions = row.get('sessions', 0) or 0
        convs = row.get('conversions', 0) or 0
        out.append({
            'channel_group': row.get('sessionDefaultChannelGroup', '(not set)'),
            'source': row.get('sessionSource', '(not set)'),
            'medium': row.get('sessionMedium', '(not set)'),
            'sessions': sessions,
            'users': row.get('totalUsers', 0),
            'engaged_sessions': row.get('engagedSessions', 0),
            'conversions': convs,
            'conversion_rate_pct': round((convs / sessions) * 100, 2) if sessions else 0.0,
            'bounce_rate_pct': round((row.get('bounceRate', 0) or 0) * 100, 1),
            'avg_session_duration_sec': round(row.get('averageSessionDuration', 0) or 0, 1),
        })
    return out


def get_devices_last_7d() -> list:
    """Distribución por device category."""
    ranges = _date_ranges_last_7_and_prev()[:1]
    res = _run_report(
        metrics=['sessions', 'engagementRate', 'conversions'],
        dimensions=['deviceCategory'],
        date_ranges=ranges,
    )
    return res['rows']


def get_full_snapshot() -> dict:
    """Snapshot completo para alimentar el brief / análisis IA.

    Devuelve dict con: overview, traffic_sources, top_pages, custom_events, devices.
    Si alguna sección falla, se loguea y se devuelve {} para esa sección
    (no romper todo el brief si una métrica falla).
    """
    snapshot = {
        'date_range': _date_ranges_last_7_and_prev(),
        'overview': {},
        'traffic_sources': [],
        'top_pages': [],
        'custom_events': {},
        'devices': [],
        'conversions_attribution': {},  # nuevo (atribución por source/medium, 28d)
        'top_sources_with_cvr': [],     # nuevo (top fuentes con conversion rate, 28d)
        'errors': [],
    }

    sections = [
        ('overview', get_overview_last_7d_vs_prev),
        ('traffic_sources', get_traffic_sources_last_7d),
        ('top_pages', get_top_pages_last_7d),
        ('custom_events', get_custom_events_last_7d),
        ('devices', get_devices_last_7d),
        # Nuevos (2026-05-30): atribución multi-canal con conversion rate
        # Espejo del reporte que el agente aremko-cli muestra en su dashboard
        ('conversions_attribution', get_conversions_by_source_medium),
        ('top_sources_with_cvr', get_top_traffic_sources_with_conversion),
    ]

    for name, fn in sections:
        try:
            snapshot[name] = fn()
        except Exception as exc:
            logger.warning(f'GA4 {name} falló: {exc}', exc_info=True)
            snapshot['errors'].append(f'{name}: {str(exc)[:200]}')

    return snapshot
