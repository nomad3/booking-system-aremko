"""DPV-006 · Procesa mensajes entrantes desde el servicio neonize.

Flujo:
 1. Valida payload (tipo, from_me).
 2. Gate por DPV_BOT_ENABLED + whitelist DPV_BOT_ENABLED_JIDS.
 3. Dedup por external_message_id.
 4. Obtiene/crea LeadConversation por (WHATSAPP, jid).
 5. Persiste mensaje USER, corre process_incoming_message y despacha reply via /send.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from django.conf import settings
from django.utils import timezone

from ..enums import ChannelType, MessageSenderType
from ..models import ConversationMessage
from ..selectors import get_or_create_conversation
from ..services.conversation_flow_service import process_incoming_message

logger = logging.getLogger(__name__)


def _bot_is_enabled_for(jid: str) -> bool:
    """Bot activo solo si flag global ON y jid en whitelist (si hay whitelist)."""
    if not getattr(settings, "DPV_BOT_ENABLED", False):
        return False
    whitelist = getattr(settings, "DPV_BOT_ENABLED_JIDS", []) or []
    if whitelist and jid not in whitelist:
        return False
    return True


def _dispatch_send(jid: str, text: str) -> bool:
    """POST al neonize /send. Devuelve True si 2xx."""
    base_url = getattr(settings, "NEONIZE_SERVICE_URL", "")
    token = getattr(settings, "NEONIZE_SERVICE_TOKEN", "")
    timeout = int(getattr(settings, "NEONIZE_SERVICE_TIMEOUT_SECONDS", 15))
    if not base_url:
        logger.warning("NEONIZE_SERVICE_URL no configurado; reply no despachada")
        return False
    url = base_url.rstrip("/") + "/send"
    headers = {"X-Auth-Token": token} if token else {}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json={"jid": jid, "text": text}, headers=headers)
        if resp.status_code >= 300:
            logger.warning("neonize /send no-OK status=%s body=%s", resp.status_code, resp.text[:300])
            return False
        return True
    except Exception as exc:
        logger.exception("Fallo dispatch a neonize /send: %s", exc)
        return False


def handle_incoming_message(payload: dict) -> dict:
    """Procesa un evento 'message' entrante proveniente de neonize_service.

    payload esperado:
      {
        "event_type": "message",
        "from_me": bool,
        "jid": "<sender_jid>",
        "message_id": "<wa_external_id>",
        "text": "<contenido>",
        "timestamp": <int epoch, opcional>,
      }
    """
    event_type = (payload or {}).get("event_type")
    if event_type != "message":
        return {"status": "ignored", "reason": f"event_type={event_type!r}"}

    if payload.get("from_me"):
        return {"status": "ignored", "reason": "from_me"}

    jid: str = (payload.get("jid") or "").strip()
    text: str = (payload.get("text") or "").strip()
    external_message_id: str = (payload.get("message_id") or "").strip()

    if not jid or not text:
        return {"status": "ignored", "reason": "missing_jid_or_text"}

    if not _bot_is_enabled_for(jid):
        return {"status": "ignored", "reason": "bot_disabled_for_jid"}

    # Dedup: si ya procesamos ese message_id de WhatsApp, salir.
    if external_message_id and ConversationMessage.objects.filter(
        external_message_id=external_message_id,
        sender_type=MessageSenderType.USER,
    ).exists():
        return {"status": "duplicate", "external_message_id": external_message_id}

    conversation, _created = get_or_create_conversation(ChannelType.WHATSAPP, jid)

    # Sincroniza contact_phone con el jid (normalizado a número sin sufijo WA si aplica)
    contact_phone = jid.split("@")[0] if "@" in jid else jid
    if contact_phone and conversation.contact_phone != contact_phone:
        conversation.contact_phone = contact_phone
        conversation.save(update_fields=["contact_phone", "updated_at"])

    # Persistir mensaje USER
    ConversationMessage.objects.create(
        conversation=conversation,
        sender_type=MessageSenderType.USER,
        text=text,
        external_message_id=external_message_id,
    )
    conversation.last_user_message_at = timezone.now()
    conversation.save(update_fields=["last_user_message_at", "updated_at"])

    # Correr flow
    flow_result = process_incoming_message(conversation, text)
    reply_text: Optional[str] = None
    try:
        reply_text = (flow_result.get("reply") or {}).get("text")
    except AttributeError:
        reply_text = None

    reply_sent = False
    if reply_text:
        reply_sent = _dispatch_send(jid, reply_text)

    return {
        "status": "processed",
        "conversation_id": conversation.id,
        "reply_text": reply_text or "",
        "reply_sent": reply_sent,
    }
