"""Consultas ORM reutilizables para DPV. Las views y servicios usan estas funciones
en lugar de hacer Model.objects.filter(...) directamente."""

from __future__ import annotations

from typing import Optional, Tuple

from django.db.models import Q

from .models import Circuit, DurationCase, LeadConversation, Place


def list_published_circuits(
    duration_case: Optional[DurationCase] = None,
    interest: Optional[str] = None,
    profile: Optional[str] = None,
    featured: Optional[bool] = None,
) -> list[Circuit]:
    """Circuits publicados filtrados por criterios opcionales."""
    qs = Circuit.objects.filter(published=True)
    if duration_case is not None:
        qs = qs.filter(duration_case=duration_case)
    if interest:
        qs = qs.filter(primary_interest=interest)
    if profile:
        qs = qs.filter(recommended_profile=profile)
    if featured is not None:
        qs = qs.filter(featured=featured)
    return list(qs.order_by("sort_order", "number"))


def get_published_circuit_by_slug(slug: str) -> Optional[Circuit]:
    return Circuit.objects.filter(published=True, slug=slug).first()


def list_places(
    place_type: Optional[str] = None,
    is_rain_friendly: Optional[bool] = None,
    is_romantic: Optional[bool] = None,
    is_family_friendly: Optional[bool] = None,
) -> list[Place]:
    """Places publicados filtrados por tipo y flags opcionales."""
    qs = Place.objects.filter(published=True)
    if place_type:
        qs = qs.filter(place_type=place_type)
    if is_rain_friendly is not None:
        qs = qs.filter(is_rain_friendly=is_rain_friendly)
    if is_romantic is not None:
        qs = qs.filter(is_romantic=is_romantic)
    if is_family_friendly is not None:
        qs = qs.filter(is_family_friendly=is_family_friendly)
    return list(qs.order_by("name"))


def get_or_create_conversation(
    channel: str,
    external_user_id: str,
) -> Tuple[LeadConversation, bool]:
    """Obtiene o crea una conversación por (channel, external_id).
    external_user_id del brief → external_id del modelo."""
    conversation, created = LeadConversation.objects.get_or_create(
        channel=channel,
        external_id=external_user_id,
    )
    return conversation, created
