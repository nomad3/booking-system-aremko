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
            for stop in day.place_stops.all().order_by("visit_order"):
                stops.append({
                    "global_index": global_index,
                    "day": day,
                    "stop": stop,
                    "place": stop.place,
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
