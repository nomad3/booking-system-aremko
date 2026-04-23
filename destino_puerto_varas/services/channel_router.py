"""Decide el comportamiento por canal (Instagram vs WhatsApp vs Web)."""

from __future__ import annotations

from ..enums import ChannelType
from ..models import LeadConversation
from .aremko_referral_service import should_refer_to_aremko


# Palabras clave que indican que el usuario quiere algo detallado (no cabe en IG)
_DETAIL_KEYWORDS = ("plan completo", "itinerario", "recomendación detallada", "recomendacion detallada")


def should_move_from_instagram_to_whatsapp(
    conversation: LeadConversation,
    latest_message_text: str = "",
) -> bool:
    """True si en Instagram ya se justifica mover la conversación a WhatsApp."""
    if conversation.channel != ChannelType.INSTAGRAM:
        return False

    # Cualquiera de estas condiciones dispara el move
    message_count = conversation.messages.count() if conversation.pk else 0
    if message_count >= 2:
        return True
    if conversation.detected_duration_case_id:
        return True

    text_lower = (latest_message_text or "").lower()
    if any(kw in text_lower for kw in _DETAIL_KEYWORDS):
        return True

    return False


def build_channel_action(
    conversation: LeadConversation,
    latest_message_text: str = "",
) -> dict:
    """Precedencia: suggest_aremko > suggest_whatsapp > stay_in_instagram.
    Mutuamente excluyentes; máximo una en True."""
    action = {
        "stay_in_instagram": False,
        "suggest_whatsapp": False,
        "suggest_aremko": False,
    }

    if should_refer_to_aremko(conversation):
        action["suggest_aremko"] = True
        return action

    if conversation.channel == ChannelType.INSTAGRAM:
        if should_move_from_instagram_to_whatsapp(conversation, latest_message_text):
            action["suggest_whatsapp"] = True
        else:
            action["stay_in_instagram"] = True
        return action

    # WhatsApp o Web sin derivación → todas False
    return action
