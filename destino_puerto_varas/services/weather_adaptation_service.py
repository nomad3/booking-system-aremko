"""Adapta la recomendación al clima (lluvia). Sin API climática — recibe is_rainy del caller."""

from __future__ import annotations

from typing import Optional

from ..models import Circuit


def adapt_recommendation_for_weather(
    circuit: Optional[Circuit],
    is_rainy: bool = False,
) -> dict:
    """Si llueve y el circuito no incluye paradas rain-friendly, sugiere ajuste."""
    if circuit is None:
        return {"adjusted": False, "message_text": "", "reasons": []}

    if not is_rainy:
        return {"adjusted": False, "message_text": "", "reasons": []}

    # Contar paradas rain-friendly en todos los days del circuito
    rain_friendly_count = 0
    total_stops = 0
    try:
        for day in circuit.days.all():
            for stop in day.place_stops.all():
                total_stops += 1
                if getattr(stop.place, "is_rain_friendly", False):
                    rain_friendly_count += 1
    except Exception:
        # Defensivo: si el related_name cambia o falta, retornamos sin ajuste
        return {"adjusted": False, "message_text": "", "reasons": []}

    if total_stops == 0 or rain_friendly_count == 0:
        return {
            "adjusted": True,
            "message_text": (
                "Como está lloviendo, te sugiero ajustar el plan para privilegiar lugares "
                "bajo techo: spa, restaurantes, cafés y museos en Puerto Varas."
            ),
            "reasons": ["Circuito sin paradas rain-friendly", "Día lluvioso"],
        }

    # Hay al menos algunas paradas aptas → no hay que ajustar dramáticamente
    return {
        "adjusted": False,
        "message_text": "",
        "reasons": [f"{rain_friendly_count}/{total_stops} paradas funcionan con lluvia"],
    }
