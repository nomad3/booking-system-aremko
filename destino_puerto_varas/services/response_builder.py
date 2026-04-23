"""Helper para la estructura JSON consistente de respuestas conversacionales."""

from __future__ import annotations

from typing import Optional

from ..models import AremkoRecommendation, Circuit, LeadConversation


def _serialize_circuit_compact(circuit: Optional[Circuit]) -> Optional[dict]:
    if circuit is None:
        return None
    return {
        "id": circuit.id,
        "slug": circuit.slug,
        "number": circuit.number,
        "name": circuit.name,
        "short_description": circuit.short_description,
        "duration_case_id": circuit.duration_case_id,
        "featured": circuit.featured,
        "updated_at": circuit.updated_at.isoformat() if circuit.updated_at else None,
    }


def _serialize_aremko(reco: Optional[AremkoRecommendation]) -> Optional[dict]:
    if reco is None:
        return None
    return {
        "id": reco.id,
        "context_key": reco.context_key,
        "title": reco.title,
        "message_text": reco.message_text,
        "recommended_service_type": reco.recommended_service_type,
    }


def _serialize_conversation_state(conversation: Optional[LeadConversation]) -> Optional[dict]:
    if conversation is None:
        return None
    duration_code = None
    if conversation.detected_duration_case_id:
        duration_code = conversation.detected_duration_case.code
    return {
        "id": conversation.id,
        "duration_case": duration_code,
        "interest": conversation.detected_interest or None,
        "profile": conversation.detected_profile or None,
        "status": conversation.status,
        "showed_interest_in_aremko": conversation.showed_interest_in_aremko,
        "referred_to_aremko": conversation.referred_to_aremko,
    }


def build_response(
    reply_type: str,
    reply_text: str,
    conversation: Optional[LeadConversation] = None,
    recommended_circuit: Optional[Circuit] = None,
    aremko_recommendation: Optional[AremkoRecommendation] = None,
    channel_action: Optional[dict] = None,
) -> dict:
    """Estructura JSON unificada para todas las respuestas conversacionales."""
    return {
        "reply_type": reply_type,
        "reply": {"text": reply_text},
        "conversation_state": _serialize_conversation_state(conversation),
        "recommended_circuit": _serialize_circuit_compact(recommended_circuit),
        "aremko_recommendation": _serialize_aremko(aremko_recommendation),
        "channel_action": channel_action or {
            "stay_in_instagram": False,
            "suggest_whatsapp": False,
            "suggest_aremko": False,
        },
    }
