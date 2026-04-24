"""DPV-007 · Procesamiento de mensajes entrantes por Telegram Bot API.

Entry point: handle_incoming_update(update).

Adapta el Update de Telegram a la capa conversacional existente reutilizando
selectors.get_or_create_conversation y conversation_flow_service.process_incoming_message.

Adaptaciones vs. brief:
- external_id (no external_user_id)
- contact_phone / contact_name (no phone_number / full_name)
- ConversationMessage.text (no message_text)
- process_incoming_message (no process_user_message)
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from django.conf import settings
from django.utils import timezone

from ..enums import ChannelType, MessageSenderType
from ..models import ConversationMessage, LeadConversation
from ..selectors import get_or_create_conversation
from ..services.conversation_flow_service import process_incoming_message

logger = logging.getLogger(__name__)

# Prefijo para que los external_id de Telegram no choquen con los de WhatsApp
EXTERNAL_USER_ID_PREFIX = "telegram:"


def _chat_id_is_allowed(chat_id: str) -> bool:
    """Respeta el kill-switch global DPV_BOT_ENABLED + whitelist por chat_id."""
    if not getattr(settings, "DPV_BOT_ENABLED", False):
        return False
    whitelist = getattr(settings, "DPV_BOT_ENABLED_TELEGRAM_CHAT_IDS", []) or []
    if not whitelist:
        return True  # Vacío = modo abierto
    return chat_id in whitelist


def _sync_contact_fields(conv: LeadConversation, from_info: dict) -> None:
    """Completa contact_name si viene en el from de Telegram y aún está vacío."""
    first = (from_info or {}).get("first_name", "") or ""
    last = (from_info or {}).get("last_name", "") or ""
    username = (from_info or {}).get("username", "") or ""
    display_name = f"{first} {last}".strip()
    if not display_name and username:
        display_name = f"@{username}"
    display_name = display_name[:200]
    if display_name and conv.contact_name != display_name:
        conv.contact_name = display_name
        conv.save(update_fields=["contact_name", "updated_at"])


def _already_processed(dedup_id: str) -> bool:
    if not dedup_id:
        return False
    return ConversationMessage.objects.filter(
        external_message_id=dedup_id,
        sender_type=MessageSenderType.USER,
    ).exists()


def _persist_assistant_message(conv: LeadConversation, text: str) -> None:
    ConversationMessage.objects.create(
        conversation=conv,
        sender_type=MessageSenderType.ASSISTANT,
        text=text,
    )
    conv.last_assistant_message_at = timezone.now()
    conv.save(update_fields=["last_assistant_message_at", "updated_at"])


def _dispatch_send_telegram(chat_id: str, text: str) -> bool:
    """POST a api.telegram.org/botTOKEN/sendMessage. True si la API responde ok=true."""
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    base = getattr(settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org").rstrip("/")
    timeout = int(getattr(settings, "TELEGRAM_SEND_TIMEOUT_SECONDS", 15))
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN vacío; mensaje no despachado a Telegram")
        return False
    url = f"{base}/bot{token}/sendMessage"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json={"chat_id": chat_id, "text": text})
        if resp.status_code >= 400:
            logger.warning(
                "Telegram sendMessage %s: %s", resp.status_code, resp.text[:200]
            )
            return False
        data = {}
        try:
            data = resp.json()
        except Exception:
            logger.warning("Telegram sendMessage: respuesta no-JSON")
            return False
        if not data.get("ok"):
            logger.warning("Telegram sendMessage not ok: %s", data)
            return False
        return True
    except Exception as exc:
        logger.warning("Telegram sendMessage exception: %s", exc)
        return False


def handle_incoming_update(update: dict) -> dict:
    """Procesa un Update de Telegram Bot API.

    Esperado (simplificado):
      {
        "update_id": 123,
        "message": {
          "message_id": 42,
          "from": {"id": 12345, "first_name": "Jorge", "is_bot": false},
          "chat": {"id": 12345, "type": "private"},
          "date": 1714000000,
          "text": "hola"
        }
      }
    """
    update = update or {}
    update_id = str(update.get("update_id", ""))
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"status": "ignored", "reason": "no_message_in_update"}

    chat = message.get("chat") or {}
    chat_type = chat.get("type", "")
    if chat_type != "private":
        return {"status": "ignored", "reason": f"chat_type_not_supported: {chat_type}"}

    chat_id = str(chat.get("id", ""))
    if not chat_id:
        return {"status": "error", "reason": "missing_chat_id"}

    if not _chat_id_is_allowed(chat_id):
        return {
            "status": "ignored",
            "reason": "chat_id_not_in_whitelist_or_bot_disabled",
        }

    from_info = message.get("from") or {}
    if from_info.get("is_bot"):
        return {"status": "ignored", "reason": "from_bot"}

    text = (message.get("text") or "").strip()
    message_id_tg = str(message.get("message_id", ""))

    # Telegram garantiza update_id único por bot → lo usamos como clave de dedup.
    dedup_id = f"tg:{update_id}" if update_id else f"tg_msg:{chat_id}:{message_id_tg}"

    if _already_processed(dedup_id):
        logger.info("Duplicate Telegram dedup_id=%s, skipping", dedup_id)
        return {"status": "ignored", "reason": "duplicate"}

    external_user_id = f"{EXTERNAL_USER_ID_PREFIX}{chat_id}"
    conv, _created = get_or_create_conversation(ChannelType.TELEGRAM, external_user_id)
    _sync_contact_fields(conv, from_info)

    if not text:
        reply = (
            "Por ahora solo puedo leer mensajes de texto. ¿Puedes contarme qué estás "
            "buscando en Puerto Varas?"
        )
        _persist_assistant_message(conv, reply)
        sent = _dispatch_send_telegram(chat_id, reply)
        return {
            "status": "handled",
            "reason": "non_text_message",
            "conversation_id": conv.id,
            "reply_text": reply,
            "reply_sent": sent,
        }

    # Persistir mensaje entrante
    ConversationMessage.objects.create(
        conversation=conv,
        sender_type=MessageSenderType.USER,
        text=text,
        external_message_id=dedup_id,
    )
    conv.last_user_message_at = timezone.now()
    conv.save(update_fields=["last_user_message_at", "updated_at"])

    # Ejecutar flow conversacional (mismo que WhatsApp)
    try:
        flow_result = process_incoming_message(conv, text)
    except Exception as exc:
        logger.exception("conversation_flow_service falló (telegram): %s", exc)
        fallback = (
            "Perdón, estoy con un problema técnico. Escríbenos a wa.me/56958655810 y "
            "te ayudamos directo."
        )
        _persist_assistant_message(conv, fallback)
        sent = _dispatch_send_telegram(chat_id, fallback)
        return {
            "status": "error",
            "reason": "flow_exception",
            "conversation_id": conv.id,
            "reply_text": fallback,
            "reply_sent": sent,
        }

    reply_text: Optional[str] = ""
    try:
        reply_text = (flow_result or {}).get("reply", {}).get("text", "")
    except AttributeError:
        reply_text = ""

    if not reply_text:
        reply_text = "Disculpa, no te entendí. ¿Me lo puedes contar con otras palabras?"
        _persist_assistant_message(conv, reply_text)

    sent = _dispatch_send_telegram(chat_id, reply_text)
    return {
        "status": "handled",
        "conversation_id": conv.id,
        "reply_text": reply_text,
        "reply_sent": sent,
    }
