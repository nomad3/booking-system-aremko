"""Construye el payload de derivación a Aremko (URLs + texto de cierre)."""

from __future__ import annotations

from django.conf import settings

from ..models import LeadConversation


def should_refer_to_aremko(conversation: LeadConversation) -> bool:
    """True si la conversación debe derivarse. Señal principal: showed_interest_in_aremko."""
    if conversation is None:
        return False
    if conversation.referred_to_aremko:
        return False  # ya fue derivada, no re-derivar
    return bool(conversation.showed_interest_in_aremko)


def build_aremko_referral_payload(conversation: LeadConversation) -> dict:
    """Payload de derivación con texto + URLs.
    Si no corresponde derivar, should_refer=False y campos vacíos."""
    if not should_refer_to_aremko(conversation):
        return {
            "should_refer": False,
            "reply_text": "",
            "reservation_url": "",
            "whatsapp_url": "",
        }

    reply_text = (
        "Perfecto, para reservar spa, tinas calientes o cabañas en Aremko te dejo "
        "los accesos directos. Te atiende el equipo de Aremko directamente."
    )
    return {
        "should_refer": True,
        "reply_text": reply_text,
        "reservation_url": getattr(settings, "AREMKO_RESERVATION_URL", ""),
        "whatsapp_url": getattr(settings, "AREMKO_WHATSAPP_URL", ""),
    }
