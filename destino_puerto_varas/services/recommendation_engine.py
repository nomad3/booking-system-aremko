"""Motor de recomendación determinístico (sin IA).

Orden de especificidad (mayor → menor):
  1. duration + interest + profile + is_rainy    → HIGH
  2. duration + interest + profile               → MEDIUM
  3. duration + interest                         → MEDIUM
  4. duration + profile                          → MEDIUM
  5. solo duration (fallback a default)          → LOW
"""

from __future__ import annotations

from typing import Optional

from django.db.models import Q

from ..constants import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from ..enums import InterestType, ProfileType
from ..models import Circuit, DurationCase, RecommendationRule


def get_default_circuit_for_duration(duration_case: DurationCase) -> Optional[Circuit]:
    """Circuit default para un DurationCase: featured primero, luego sort_order ASC, updated_at DESC.

    Excluye circuitos sin itinerario armado (los "Próximamente").
    """
    from django.db.models import Count

    return (
        Circuit.objects.filter(published=True, duration_case=duration_case)
        .annotate(_days_count=Count("days"))
        .filter(_days_count__gt=0)
        .order_by("-featured", "sort_order", "-updated_at")
        .first()
    )


def _rule_specificity(rule: RecommendationRule) -> int:
    """Cuenta cuántos campos criterio están seteados (más = más específica)."""
    score = 1  # duration_case siempre está seteado (FK CASCADE not null)
    if rule.interest:
        score += 1
    if rule.profile:
        score += 1
    if rule.is_rainy is not None:
        score += 1
    return score


def get_matching_rules(
    duration_case: DurationCase,
    interest: Optional[str] = None,
    profile: Optional[str] = None,
    is_rainy: Optional[bool] = None,
) -> list[RecommendationRule]:
    """Reglas donde todos los campos no-null coinciden con los criterios.
    Campos null/blank en la regla = wildcard."""
    qs = RecommendationRule.objects.filter(is_active=True, duration_case=duration_case)

    # interest: matchea si la regla tiene "" (wildcard) o el valor exacto
    if interest:
        qs = qs.filter(Q(interest="") | Q(interest=interest))
    else:
        qs = qs.filter(interest="")

    if profile:
        qs = qs.filter(Q(profile="") | Q(profile=profile))
    else:
        qs = qs.filter(profile="")

    # is_rainy tri-state: null en la regla = wildcard
    if is_rainy is not None:
        qs = qs.filter(Q(is_rainy__isnull=True) | Q(is_rainy=is_rainy))
    else:
        qs = qs.filter(is_rainy__isnull=True)

    return list(qs.select_related("recommended_circuit"))


def select_best_rule(rules: list[RecommendationRule]) -> Optional[RecommendationRule]:
    """Elige la regla más específica. Desempate: priority DESC."""
    if not rules:
        return None
    return max(rules, key=lambda r: (_rule_specificity(r), r.priority))


def _confidence_from_specificity(specificity: int) -> str:
    if specificity >= 4:
        return CONFIDENCE_HIGH
    if specificity >= 2:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def _build_reasons(
    duration_case: DurationCase,
    interest: Optional[str],
    profile: Optional[str],
    is_rainy: Optional[bool],
    rule: Optional[RecommendationRule],
) -> list[str]:
    reasons: list[str] = []
    if duration_case is not None:
        reasons.append(f"Duración: {duration_case.name}")
    if interest:
        label = dict(InterestType.choices).get(interest, interest)
        reasons.append(f"Interés: {label}")
    if profile:
        label = dict(ProfileType.choices).get(profile, profile)
        reasons.append(f"Perfil: {label}")
    if is_rainy is True:
        reasons.append("Clima: lluvioso")
    elif is_rainy is False:
        reasons.append("Clima: despejado")
    if rule is None:
        reasons.append("Sin regla específica (circuit por defecto)")
    return reasons


def recommend_circuit(
    duration_case: Optional[DurationCase],
    interest: Optional[str] = None,
    profile: Optional[str] = None,
    is_rainy: Optional[bool] = None,
) -> dict:
    """Entry point. Retorna dict con circuit, confidence, reasons, rule_id."""
    if duration_case is None:
        return {
            "circuit": None,
            "confidence": CONFIDENCE_LOW,
            "reasons": ["Falta duración"],
            "rule_id": None,
        }

    rules = get_matching_rules(duration_case, interest, profile, is_rainy)
    best = select_best_rule(rules)

    if best is not None:
        return {
            "circuit": best.recommended_circuit,
            "confidence": _confidence_from_specificity(_rule_specificity(best)),
            "reasons": _build_reasons(duration_case, interest, profile, is_rainy, best),
            "rule_id": best.id,
        }

    fallback = get_default_circuit_for_duration(duration_case)
    return {
        "circuit": fallback,
        "confidence": CONFIDENCE_LOW,
        "reasons": _build_reasons(duration_case, interest, profile, is_rainy, None),
        "rule_id": None,
    }
