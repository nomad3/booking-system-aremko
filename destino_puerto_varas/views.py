"""Vistas HTML públicas para destinopuertovaras.cl.

Hoy se montan en la misma instancia Django bajo /dpv/ para iterar.
Más adelante (Opción B) se servirán desde un Render service separado
diferenciado por SITE_MODE/host.
"""
from __future__ import annotations

from django.http import Http404
from django.shortcuts import render
from django.views.generic import View

from django.db.models import Count, Q

from .models import Circuit, CircuitDay, CircuitPlace, Place


# Mapeo de slugs de categoría → flag del modelo Circuit (filtro UI/agente).
# Multi-valor: el turista puede combinar varias y se aplica OR (la unión).
CATEGORY_FILTERS = {
    "nature": "is_nature",
    "culture": "is_culture",
    "gastronomy": "is_gastronomy",
    "adventure": "is_adventure",
    "family": "is_family_friendly",
}

CATEGORY_LABELS = [
    ("nature", "Naturaleza escénica", "🏞️"),
    ("culture", "Cultura y patrimonio", "🏛️"),
    ("gastronomy", "Gastronomía", "🍴"),
    ("adventure", "Aventura", "🎒"),
    ("family", "Viaje familiar", "👨‍👩‍👧"),
]


class CircuitListPublicView(View):
    """Listado público de circuitos publicados."""

    template_name = "destino_puerto_varas/public/circuit_list.html"

    def get(self, request):
        # Solo mostrar circuitos con itinerario armado (paradas/días).
        # Los circuitos sin paradas se mantienen en BD pero ocultos al turista;
        # aparecerán automáticamente al armarles paradas en el admin.
        circuits = (
            Circuit.objects.filter(published=True)
            .select_related("duration_case")
            .prefetch_related("days__place_stops__place__photos", "days__place_stops__place__parent_place")
            .annotate(days_count=Count("days"))
            .filter(days_count__gt=0)
            .order_by("sort_order", "number")
        )

        # Categorías seleccionadas por el turista (OR semantics).
        # Acepta repetidos: ?cat=nature&cat=culture
        selected = [c for c in request.GET.getlist("cat") if c in CATEGORY_FILTERS]
        if selected:
            q = Q()
            for cat in selected:
                q |= Q(**{CATEGORY_FILTERS[cat]: True})
            circuits = circuits.filter(q).distinct()

        # Resolver hero_url por circuito: hero_image propio → foto del primer
        # place del Día 1 → None (cae al gradiente actual del template).
        circuit_list = list(circuits)
        for c in circuit_list:
            c.hero_url = _resolve_circuit_hero_url(c)

        context = {
            "circuits": circuit_list,
            "categories": CATEGORY_LABELS,
            "selected_categories": set(selected),
        }
        return render(request, self.template_name, context)


class CircuitDetailPublicView(View):
    """Detalle público de un circuito (itinerario estilo Bled)."""

    template_name = "destino_puerto_varas/public/circuit_detail.html"

    def get(self, request, slug: str):
        circuit = (
            Circuit.objects.filter(published=True, slug=slug)
            .select_related("duration_case")
            .prefetch_related("days__place_stops__place__photos", "days__place_stops__place__parent_place")
            .first()
        )
        if circuit is None:
            raise Http404("Circuito no encontrado")
        # Circuitos "Próximamente" no tienen días aún — no exponer detalle vacío.
        if not circuit.days.exists():
            raise Http404("Circuito en preparación")

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


def _resolve_circuit_hero_url(circuit) -> str:
    """URL para la imagen hero del circuito en el listado.

    Prioridad: hero_image propio del circuito → foto principal del primer
    place del Día 1 → string vacío (template cae al gradiente).
    """
    if getattr(circuit, "hero_image", None):
        try:
            return circuit.hero_image.url
        except (ValueError, AttributeError):
            pass
    for day in circuit.days.all().order_by("day_number", "sort_order"):
        for stop in day.place_stops.all().order_by("visit_order"):
            photo = _primary_photo(stop.place)
            if photo and photo.image:
                try:
                    return photo.image.url
                except (ValueError, AttributeError):
                    continue
            if photo and photo.source_url:
                return photo.source_url
        break  # solo Día 1
    return ""


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
