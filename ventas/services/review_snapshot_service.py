"""
Helper para leer snapshots de reviews externas (Google + TripAdvisor).

Tarea 2.8 plan maestro. Consumido por survey_ai_analyzer.py para cruzar
NPS interno con la evolución de reviews públicas.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_latest_snapshot():
    """Devuelve el ReviewSnapshot más reciente (o None si no hay)."""
    try:
        from ventas.models import ReviewSnapshot
        return ReviewSnapshot.objects.order_by('-fecha').first()
    except Exception as exc:
        logger.warning(f'No se pudo cargar último snapshot de reviews: {exc}')
        return None


def get_snapshot_summary() -> Optional[dict]:
    """Resumen estructurado del snapshot más reciente + delta vs anterior.

    Formato pensado para inyectar al prompt del LLM:
    {
      'fecha_snapshot': '2026-05-05',
      'google': {'rating': 4.7, 'total': 312, 'rating_delta': 0.05, 'total_delta': 8, 'url': '...'},
      'tripadvisor': {'rating': 4.5, 'total': 184, 'rating_delta': -0.1, 'total_delta': 3, 'url': '...'},
      'fecha_anterior': '2026-04-28',
      'notas': 'Review nueva detractora en Google sobre temperatura tina'
    }

    Devuelve None si no hay snapshot registrado todavía.
    """
    snap = get_latest_snapshot()
    if not snap:
        return None

    deltas = snap.deltas() or {}

    def _section(rating, total, rating_delta_key, total_delta_key, url):
        if rating is None and total is None:
            return None
        return {
            'rating': float(rating) if rating is not None else None,
            'total': int(total) if total is not None else None,
            'rating_delta': deltas.get(rating_delta_key),
            'total_delta': deltas.get(total_delta_key),
            'url': url or None,
        }

    summary = {
        'fecha_snapshot': snap.fecha.isoformat(),
        'fecha_anterior': deltas.get('fecha_anterior').isoformat() if deltas.get('fecha_anterior') else None,
        'google': _section(
            snap.google_rating, snap.google_total,
            'google_rating_delta', 'google_total_delta',
            snap.google_url,
        ),
        'tripadvisor': _section(
            snap.tripadvisor_rating, snap.tripadvisor_total,
            'tripadvisor_rating_delta', 'tripadvisor_total_delta',
            snap.tripadvisor_url,
        ),
        'notas': snap.notas or None,
    }
    return summary


def needs_snapshot_for_this_week() -> bool:
    """Devuelve True si la semana actual aún no tiene snapshot.

    Útil para alertar a Jorge si olvidó actualizar antes del análisis del lunes.
    """
    from datetime import timedelta
    from django.utils import timezone
    from ventas.models import ReviewSnapshot

    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    return not ReviewSnapshot.objects.filter(fecha__gte=monday).exists()


def get_reviews_recientes(days: int = 14, limit: int = 30) -> list:
    """Lista de Review individuales (texto completo) de los últimos N días.

    Pensado para inyectar al prompt del análisis IA semanal: el LLM lee
    el texto real de cada review nueva y lo cruza con NPS interno.
    """
    from datetime import timedelta
    from django.utils import timezone
    try:
        from ventas.models import Review
    except ImportError:
        return []

    cutoff = timezone.localdate() - timedelta(days=days)
    qs = Review.objects.filter(fecha_review__gte=cutoff).order_by('-fecha_review')[:limit]

    out = []
    for r in qs:
        out.append({
            'fuente': r.fuente,
            'fecha': r.fecha_review.isoformat() if r.fecha_review else None,
            'autor': r.autor or None,
            'rating': r.rating,
            'idioma': r.idioma,
            'texto': (r.texto or '').strip()[:600],
            'sentimiento': r.sentimiento or r.auto_sentimiento(),
            'respuesta_publicada': bool(r.respuesta_publicada),
        })
    return out
