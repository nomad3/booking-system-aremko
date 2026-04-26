"""Vistas HTML públicas para destinopuertovaras.cl.

Hoy se montan en la misma instancia Django bajo /dpv/ para iterar.
Más adelante (Opción B) se servirán desde un Render service separado
diferenciado por SITE_MODE/host.
"""
from __future__ import annotations

from django.http import Http404
from django.shortcuts import render
from django.views.generic import View

from .models import Circuit, CircuitDay, CircuitPlace, Place


class CircuitListPublicView(View):
    """Listado público de circuitos publicados."""

    template_name = "destino_puerto_varas/public/circuit_list.html"

    def get(self, request):
        circuits = (
            Circuit.objects.filter(published=True)
            .select_related("duration_case")
            .order_by("sort_order", "number")
        )
        return render(request, self.template_name, {"circuits": circuits})


class CircuitDetailPublicView(View):
    """Detalle público de un circuito (itinerario estilo Bled)."""

    template_name = "destino_puerto_varas/public/circuit_detail.html"

    def get(self, request, slug: str):
        circuit = (
            Circuit.objects.filter(published=True, slug=slug)
            .select_related("duration_case")
            .prefetch_related("days__place_stops__place__photos")
            .first()
        )
        if circuit is None:
            raise Http404("Circuito no encontrado")

        # Aplanar paradas en orden global, conservando referencia al día
        stops: list[dict] = []
        global_index = 1
        for day in circuit.days.all().order_by("day_number", "sort_order"):
            day_extra_title = _day_extra_title(day)
            for stop in day.place_stops.all().order_by("visit_order"):
                stops.append({
                    "global_index": global_index,
                    "day": day,
                    "day_extra_title": day_extra_title,
                    "stop": stop,
                    "place": stop.place,
                    "place_icon": _place_icon(stop.place.place_type),
                    "primary_photo": _primary_photo(stop.place),
                })
                global_index += 1

        context = {
            "circuit": circuit,
            "stops": stops,
            "total_stops": len(stops),
        }
        return render(request, self.template_name, context)


def _primary_photo(place: Place):
    """Devuelve la foto principal del lugar o la primera disponible."""
    photos = list(place.photos.all())
    if not photos:
        return None
    primary = next((p for p in photos if p.is_primary), None)
    return primary or photos[0]


# Emoji por tipo de lugar para el placeholder de foto
PLACE_TYPE_ICONS = {
    "ATTRACTION": "🏞️",
    "VIEWPOINT": "🔭",
    "PARK": "🌲",
    "RESTAURANT": "🍴",
    "CAFE": "☕",
    "SHOP": "🛍️",
    "LODGING": "🛏️",
    "SPA": "💆",
    "TOUR_OPERATOR": "🎒",
    "BUSINESS": "🏢",
    "ACTIVITY": "⛰️",
    "MUSEUM": "🏛️",
    "THEATER": "🎭",
    "CHURCH": "⛪",
    "CULTURAL_CENTER": "🎨",
    "OTHER": "📍",
}


def _place_icon(place_type: str) -> str:
    return PLACE_TYPE_ICONS.get(place_type, "📍")


def _day_extra_title(day) -> str:
    """Devuelve el título del día solo si aporta info más allá del 'Día N'.

    Evita duplicar 'DÍA 1 · DÍA 1' cuando el title viene como 'Día 1' literal.
    """
    title = (day.title or "").strip()
    if not title:
        return ""
    normalized = title.lower().replace("dia", "día")
    if normalized == f"día {day.day_number}":
        return ""
    return title
