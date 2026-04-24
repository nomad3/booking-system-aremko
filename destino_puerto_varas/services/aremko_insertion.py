"""Decide cuándo insertar Aremko como recomendación contextual en la conversación."""

from __future__ import annotations

from typing import Optional

from ..enums import DurationType, InterestType, ProfileType
from ..models import AremkoRecommendation, DurationCase

# DurationTypes que representan estadías de 2+ días/noches
_LODGING_DURATIONS = {
    DurationType.TWO_DAYS_ONE_NIGHT,
    DurationType.THREE_DAYS_TWO_NIGHTS,
    DurationType.FOUR_DAYS_THREE_NIGHTS,
}


def should_insert_aremko(
    duration_case: Optional[DurationCase] = None,
    interest: Optional[str] = None,
    profile: Optional[str] = None,
    is_rainy: Optional[bool] = None,
    conversation_depth: int = 0,
    explicit_interest: bool = False,
) -> bool:
    """True si Aremko aporta valor contextual (no publicidad agresiva)."""
    if explicit_interest:
        return True
    if interest == InterestType.RELAX_ROMANTIC:
        return True
    if (
        profile == ProfileType.COUPLE
        and duration_case is not None
        and getattr(duration_case, "duration_type", None) in _LODGING_DURATIONS
    ):
        return True
    if is_rainy is True:
        return True
    if conversation_depth >= 2:
        return True
    return False


def get_aremko_recommendation_for_context(
    context_key: Optional[str] = None,
    duration_case: Optional[DurationCase] = None,
    interest: Optional[str] = None,
    profile: Optional[str] = None,
    is_rainy: Optional[bool] = None,
) -> Optional[AremkoRecommendation]:
    """Busca la AremkoRecommendation apropiada. Lookup en cascada:
    1. context_key explícito
    2. Heurística por contexto (relax_pareja, lluvia, ...)
    3. Fallback a la más prioritaria activa."""
    qs = AremkoRecommendation.objects.filter(is_active=True)

    if context_key:
        match = qs.filter(context_key=context_key).first()
        if match:
            return match

    # Heurística
    heuristic_key: Optional[str] = None
    if interest == InterestType.RELAX_ROMANTIC and profile == ProfileType.COUPLE:
        heuristic_key = "relax_pareja"
    elif is_rainy is True:
        heuristic_key = "lluvia"
    elif interest == InterestType.RELAX_ROMANTIC:
        heuristic_key = "relax"

    if heuristic_key:
        match = qs.filter(context_key=heuristic_key).first()
        if match:
            return match

    return qs.order_by("-priority", "-id").first()
