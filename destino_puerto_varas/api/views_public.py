"""Endpoints públicos read-only para catálogo DPV (circuitos, lugares, duraciones)."""

from __future__ import annotations

from rest_framework import generics

from ..models import DurationCase, Place
from ..selectors import get_published_circuit_by_slug, list_places, list_published_circuits
from .serializers import (
    CircuitDetailSerializer,
    CircuitListSerializer,
    DurationCaseSerializer,
    PlaceSerializer,
)


class CircuitListView(generics.ListAPIView):
    """GET /api/destino-puerto-varas/circuits/ — circuitos publicados."""
    serializer_class = CircuitListSerializer

    def get_queryset(self):
        qs = list_published_circuits()
        duration_code = self.request.query_params.get("duration_case")
        interest = self.request.query_params.get("interest")
        featured = self.request.query_params.get("featured")
        if duration_code:
            qs = qs.filter(duration_case__code=duration_code)
        if interest:
            qs = qs.filter(primary_interest=interest)
        if featured is not None:
            qs = qs.filter(featured=featured.lower() in ("1", "true", "yes"))
        return qs


class CircuitDetailView(generics.RetrieveAPIView):
    """GET /api/destino-puerto-varas/circuits/<slug>/ — detalle con días y paradas."""
    serializer_class = CircuitDetailSerializer
    lookup_field = "slug"

    def get_object(self):
        slug = self.kwargs[self.lookup_field]
        circuit = get_published_circuit_by_slug(slug)
        if circuit is None:
            from django.http import Http404
            raise Http404("Circuito no encontrado")
        return circuit


class PlaceListView(generics.ListAPIView):
    """GET /api/destino-puerto-varas/places/ — lugares publicados."""
    serializer_class = PlaceSerializer

    def get_queryset(self):
        qs = list_places()
        place_type = self.request.query_params.get("place_type")
        rain_friendly = self.request.query_params.get("rain_friendly")
        if place_type:
            qs = qs.filter(place_type=place_type)
        if rain_friendly is not None:
            qs = qs.filter(is_rain_friendly=rain_friendly.lower() in ("1", "true", "yes"))
        return qs


class DurationCaseListView(generics.ListAPIView):
    """GET /api/destino-puerto-varas/duration-cases/ — casos de duración activos."""
    serializer_class = DurationCaseSerializer
    queryset = DurationCase.objects.filter(is_active=True).order_by("sort_order", "days")
