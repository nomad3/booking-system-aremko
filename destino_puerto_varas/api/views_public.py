"""Endpoints públicos read-only para catálogo DPV (circuitos, lugares, duraciones)."""

from __future__ import annotations

from django.db.models import Count
from django.http import Http404
from rest_framework import generics

from ..models import Circuit, DurationCase, Place
from .serializers import (
    CircuitDetailSerializer,
    CircuitListSerializer,
    DurationCaseSerializer,
    PlaceSerializer,
)


def _truthy(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() in ("1", "true", "yes")


class CircuitListView(generics.ListAPIView):
    """GET /api/destino-puerto-varas/circuits/ — circuitos publicados."""
    serializer_class = CircuitListSerializer

    def get_queryset(self):
        # Solo circuitos con itinerario armado — los "Próximamente" se ocultan.
        qs = (
            Circuit.objects.filter(published=True)
            .annotate(_days_count=Count("days"))
            .filter(_days_count__gt=0)
            .order_by("sort_order", "number")
        )
        params = self.request.query_params
        duration_code = params.get("duration_case")
        interest = params.get("interest")
        featured = _truthy(params.get("featured"))
        if duration_code:
            qs = qs.filter(duration_case__code=duration_code)
        if interest:
            qs = qs.filter(primary_interest=interest)
        if featured is not None:
            qs = qs.filter(featured=featured)
        return qs


class CircuitDetailView(generics.RetrieveAPIView):
    """GET /api/destino-puerto-varas/circuits/<slug>/ — detalle con días y paradas."""
    serializer_class = CircuitDetailSerializer
    lookup_field = "slug"

    def get_object(self):
        slug = self.kwargs[self.lookup_field]
        circuit = (
            Circuit.objects.filter(published=True, slug=slug)
            .prefetch_related("days__place_stops__place")
            .first()
        )
        if circuit is None:
            raise Http404("Circuito no encontrado")
        return circuit


class PlaceListView(generics.ListAPIView):
    """GET /api/destino-puerto-varas/places/ — lugares publicados."""
    serializer_class = PlaceSerializer

    def get_queryset(self):
        qs = Place.objects.filter(published=True).order_by("name")
        params = self.request.query_params
        place_type = params.get("place_type")
        rain_friendly = _truthy(params.get("rain_friendly"))
        if place_type:
            qs = qs.filter(place_type=place_type)
        if rain_friendly is not None:
            qs = qs.filter(is_rain_friendly=rain_friendly)
        return qs


class DurationCaseListView(generics.ListAPIView):
    """GET /api/destino-puerto-varas/duration-cases/ — casos de duración activos."""
    serializer_class = DurationCaseSerializer
    queryset = DurationCase.objects.filter(is_active=True).order_by("sort_order", "days")
