"""
Google Search Console API client (Tarea 2.3 plan maestro).

Trae queries, páginas y métricas de búsqueda orgánica:
- Top queries de los últimos 7 días vs los 7 anteriores
- Top landing pages desde Google
- Clicks, impresiones, CTR, posición promedio

Reusa el mismo service account que GA4 (debe agregarse como usuario de GSC
con permisos al menos de Lectura sobre la propiedad).

Settings:
- GSC_SITE_URL: 'sc-domain:aremko.cl' si es Domain property,
                'https://aremko.cl/' si es URL prefix property.
"""
import logging
from datetime import date, timedelta
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def _service():
    from googleapiclient.discovery import build

    from .ga4_reporter import _get_credentials

    creds = _get_credentials()
    return build('searchconsole', 'v1', credentials=creds, cache_discovery=False)


def _site_url() -> str:
    url = getattr(settings, 'GSC_SITE_URL', '') or ''
    if not url:
        raise ValueError('GSC_SITE_URL no configurado')
    return url


def _date_range(days: int = 7, offset: int = 0) -> dict:
    """Rango de N días terminando hace `offset` días.

    Por default: últimos 7 días terminando ayer.
    Para los 7 anteriores: days=7, offset=7.

    Nota: GSC tiene 2-3 días de latencia, así que ayer puede no tener datos.
    Usamos siempre offset >= 1 para evitar el día de hoy.
    """
    today = date.today()
    end = today - timedelta(days=1 + offset)
    start = end - timedelta(days=days - 1)
    return {'start': start.isoformat(), 'end': end.isoformat()}


def _query(dimensions: list, start_date: str, end_date: str,
           row_limit: int = 100, search_type: str = 'web') -> list:
    """Wrapper para searchanalytics.query."""
    service = _service()
    body = {
        'startDate': start_date,
        'endDate': end_date,
        'dimensions': dimensions,
        'rowLimit': row_limit,
        'type': search_type,
    }
    try:
        resp = service.searchanalytics().query(siteUrl=_site_url(), body=body).execute()
    except Exception as exc:
        logger.error(f'GSC query falló: {exc}')
        raise
    return resp.get('rows', [])


def _format_rows(rows: list, dimensions: list) -> list:
    out = []
    for r in rows:
        item = {}
        for i, dim in enumerate(dimensions):
            item[dim] = r.get('keys', [None] * len(dimensions))[i]
        item['clicks'] = r.get('clicks', 0)
        item['impressions'] = r.get('impressions', 0)
        item['ctr'] = round(r.get('ctr', 0.0) * 100, 2)  # como porcentaje
        item['position'] = round(r.get('position', 0.0), 2)
        out.append(item)
    return out


def get_top_queries_last_7d(limit: int = 25) -> dict:
    """Top queries por clicks: últimos 7d vs 7d anteriores."""
    curr = _date_range(days=7, offset=2)  # 7d terminando antes de ayer (latencia GSC)
    prev = _date_range(days=7, offset=9)
    return {
        'last_7d': _format_rows(_query(['query'], curr['start'], curr['end'], row_limit=limit), ['query']),
        'prev_7d': _format_rows(_query(['query'], prev['start'], prev['end'], row_limit=limit), ['query']),
        'date_range': {'last_7d': curr, 'prev_7d': prev},
    }


def get_top_pages_last_7d(limit: int = 25) -> list:
    """Top landing pages desde Google (últimos 7d)."""
    r = _date_range(days=7, offset=2)
    return _format_rows(_query(['page'], r['start'], r['end'], row_limit=limit), ['page'])


def get_overview_last_7d_vs_prev() -> dict:
    """Totales agregados: clicks, impresiones, CTR, posición."""
    curr = _date_range(days=7, offset=2)
    prev = _date_range(days=7, offset=9)

    def _totals(rows):
        if not rows:
            return {'clicks': 0, 'impressions': 0, 'ctr': 0, 'position': 0}
        total_clicks = sum(r.get('clicks', 0) for r in rows)
        total_imp = sum(r.get('impressions', 0) for r in rows)
        ctr = (total_clicks / total_imp * 100) if total_imp else 0
        # position promedio ponderada por impresiones
        if total_imp:
            pos = sum(r.get('position', 0) * r.get('impressions', 0) for r in rows) / total_imp
        else:
            pos = 0
        return {
            'clicks': total_clicks,
            'impressions': total_imp,
            'ctr': round(ctr, 2),
            'position': round(pos, 2),
        }

    rows_curr = _query(['date'], curr['start'], curr['end'], row_limit=100)
    rows_prev = _query(['date'], prev['start'], prev['end'], row_limit=100)

    return {
        'last_7d': _totals(rows_curr),
        'prev_7d': _totals(rows_prev),
        'date_range': {'last_7d': curr, 'prev_7d': prev},
    }


def get_full_snapshot() -> dict:
    """Snapshot GSC para brief/análisis IA. Tolerante a fallas parciales."""
    snapshot = {
        'overview': {},
        'top_queries': {},
        'top_pages': [],
        'errors': [],
    }
    sections = [
        ('overview', get_overview_last_7d_vs_prev),
        ('top_queries', get_top_queries_last_7d),
        ('top_pages', get_top_pages_last_7d),
    ]
    for name, fn in sections:
        try:
            snapshot[name] = fn()
        except Exception as exc:
            logger.warning(f'GSC {name} falló: {exc}', exc_info=True)
            snapshot['errors'].append(f'{name}: {str(exc)[:200]}')
    return snapshot
