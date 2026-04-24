"""Máquina de estados conversacional (legacy) + delegación al agente LLM.

Desde DPV-008, `process_incoming_message` delega al agente LLM (agent_service) si
está disponible. La máquina de estados queda como fallback determinístico si el
agente falla o está desactivado.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional

from django.utils import timezone

from ..constants import (
    MAX_PARSE_RETRIES,
    REPLY_TYPE_INFO,
    REPLY_TYPE_QUESTION,
    REPLY_TYPE_RECOMMENDATION,
    REPLY_TYPE_REFERRAL,
    STATE_AREMKO_SUGGESTED,
    STATE_ASK_DURATION,
    STATE_ASK_INTEREST,
    STATE_ASK_PROFILE,
    STATE_FOLLOW_UP,
    STATE_RECOMMEND_CIRCUIT,
    STATE_REFERRED_TO_AREMKO,
    STATE_START,
)
from ..enums import ConversationStatus, DurationType, InterestType, MessageSenderType, ProfileType
from ..models import ConversationMessage, DurationCase, LeadConversation
from .aremko_insertion import (
    get_aremko_recommendation_for_context,
    should_insert_aremko,
)
from .aremko_referral_service import build_aremko_referral_payload
from .channel_router import build_channel_action
from .recommendation_engine import recommend_circuit
from .response_builder import build_response

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Normalización y parsers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """lowercase + strip + remove accents."""
    if not text:
        return ""
    t = text.strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t


# Orden canónico de DurationType para índices 1..8
_DURATION_ORDER = [
    DurationType.HALF_DAY,
    DurationType.FULL_DAY,
    DurationType.TWO_DAYS_ONE_NIGHT,
    DurationType.THREE_DAYS_TWO_NIGHTS,
    DurationType.FOUR_DAYS_THREE_NIGHTS,
    DurationType.FIVE_DAYS_FOUR_NIGHTS,
    DurationType.SIX_DAYS_FIVE_NIGHTS,
    DurationType.SEVEN_DAYS_SIX_NIGHTS,
]

_INTEREST_ORDER = [
    InterestType.NATURE,
    InterestType.GASTRONOMY,
    InterestType.ADVENTURE,
    InterestType.RELAX_ROMANTIC,
    InterestType.MIXED,
]

_PROFILE_ORDER = [
    ProfileType.COUPLE,
    ProfileType.FAMILY,
    ProfileType.FRIENDS,
    ProfileType.SOLO,
]


def parse_duration_message(text: str) -> Optional[str]:
    t = _normalize(text)
    if not t:
        return None

    # Índice numérico 1..8
    idx_match = re.match(r"^\s*([1-8])\s*$", t) or re.match(r"^\s*opcion\s*([1-8])\s*$", t)
    if idx_match:
        return _DURATION_ORDER[int(idx_match.group(1)) - 1]

    # Palabras clave
    if "medio dia" in t or "medio día" in text.lower():
        return DurationType.HALF_DAY
    if "dia completo" in t or "día completo" in text.lower() or "full day" in t:
        return DurationType.FULL_DAY
    if "fin de semana" in t or "2 dia" in t or "dos dia" in t or "1 noche" in t:
        return DurationType.TWO_DAYS_ONE_NIGHT
    if "3 dia" in t or "tres dia" in t or "2 noche" in t or "dos noche" in t:
        return DurationType.THREE_DAYS_TWO_NIGHTS
    if "4 dia" in t or "cuatro dia" in t or "3 noche" in t or "tres noche" in t:
        return DurationType.FOUR_DAYS_THREE_NIGHTS
    if "5 dia" in t or "cinco dia" in t or "4 noche" in t:
        return DurationType.FIVE_DAYS_FOUR_NIGHTS
    if "6 dia" in t or "seis dia" in t or "5 noche" in t:
        return DurationType.SIX_DAYS_FIVE_NIGHTS
    if "semana" in t or "7 dia" in t or "siete dia" in t or "6 noche" in t:
        return DurationType.SEVEN_DAYS_SIX_NIGHTS
    return None


def parse_interest_message(text: str) -> Optional[str]:
    t = _normalize(text)
    if not t:
        return None

    idx_match = re.match(r"^\s*([1-5])\s*$", t)
    if idx_match:
        return _INTEREST_ORDER[int(idx_match.group(1)) - 1]

    if "natura" in t or "paisaj" in t or "volcan" in t or "lago" in t:
        return InterestType.NATURE
    if "gastro" in t or "comida" in t or "restaur" in t or "gourmet" in t:
        return InterestType.GASTRONOMY
    if "aventur" in t or "trekking" in t or "kayak" in t or "rafting" in t or "adrenalin" in t:
        return InterestType.ADVENTURE
    if "relaj" in t or "romanti" in t or "pareja" in t or "spa" in t or "tina" in t or "descans" in t:
        return InterestType.RELAX_ROMANTIC
    if "mixto" in t or "variado" in t or "todo" in t:
        return InterestType.MIXED
    return None


def parse_profile_message(text: str) -> Optional[str]:
    t = _normalize(text)
    if not t:
        return None

    idx_match = re.match(r"^\s*([1-4])\s*$", t)
    if idx_match:
        return _PROFILE_ORDER[int(idx_match.group(1)) - 1]

    if "pareja" in t or "novi" in t or "esposa" in t or "esposo" in t:
        return ProfileType.COUPLE
    if "familia" in t or "hijos" in t or "niños" in t or "ninos" in t:
        return ProfileType.FAMILY
    if "amigos" in t or "grupo" in t:
        return ProfileType.FRIENDS
    if re.search(r"\bsol[oa]\b", t):
        return ProfileType.SOLO
    return None


_AREMKO_KEYWORDS = re.compile(
    r"\b(spa|masaje|tina|tinaja|alojamiento|alojar|reserva|reservar|cabana|cabaña|hospedaje|pernoctar|dormir)\b",
    re.IGNORECASE,
)


def detect_aremko_interest(text: str) -> bool:
    if not text:
        return False
    return bool(_AREMKO_KEYWORDS.search(text))


# ─────────────────────────────────────────────────────────────────────────────
# Inferencia de estado
# ─────────────────────────────────────────────────────────────────────────────

def get_next_state(conversation: LeadConversation) -> str:
    if conversation.referred_to_aremko:
        return STATE_REFERRED_TO_AREMKO
    if conversation.showed_interest_in_aremko:
        return STATE_AREMKO_SUGGESTED
    if conversation.recommended_circuit_id:
        return STATE_FOLLOW_UP
    if (
        conversation.detected_duration_case_id
        and conversation.detected_interest
        and conversation.detected_profile
    ):
        return STATE_RECOMMEND_CIRCUIT
    if conversation.detected_duration_case_id and conversation.detected_interest:
        return STATE_ASK_PROFILE
    if conversation.detected_duration_case_id:
        return STATE_ASK_INTEREST
    if not conversation.detected_duration_case_id:
        if conversation.pk and conversation.messages.exists():
            return STATE_ASK_DURATION
        return STATE_START
    return STATE_START


# ─────────────────────────────────────────────────────────────────────────────
# Helpers privados
# ─────────────────────────────────────────────────────────────────────────────

def _append_assistant_message(conversation: LeadConversation, text: str) -> ConversationMessage:
    msg = ConversationMessage.objects.create(
        conversation=conversation,
        sender_type="ASSISTANT",
        text=text,
    )
    conversation.last_assistant_message_at = timezone.now()
    conversation.save(update_fields=["last_assistant_message_at", "updated_at"])
    return msg


def _record_llm_metadata_if_any(msg: ConversationMessage, metadata: dict) -> None:
    """Persiste metadata LLM (tokens, costo, latencia, error) si corresponde."""
    if not metadata:
        return
    from .llm.cost_tracker import CostTracker
    CostTracker.record_to_message(
        msg,
        model=metadata.get("model", "") or "",
        input_tokens=int(metadata.get("input_tokens", 0) or 0),
        output_tokens=int(metadata.get("output_tokens", 0) or 0),
        latency_ms=int(metadata.get("latency_ms", 0) or 0),
        error=metadata.get("error", "") or "",
    )


def _circuit_first_day_summary(circuit) -> str:
    """Saca el summary del día 1 del circuit, o string vacío."""
    if circuit is None:
        return ""
    first_day = circuit.days.order_by("day_number").first()
    return (first_day.summary or first_day.title) if first_day else ""


def _circuit_top_place_name(circuit) -> str:
    """Nombre del primer place is_main_stop o el primer place en general."""
    if circuit is None:
        return ""
    from ..models import CircuitPlace
    main = (
        CircuitPlace.objects
        .filter(circuit_day__circuit=circuit, is_main_stop=True)
        .select_related("place")
        .order_by("circuit_day__day_number", "visit_order")
        .first()
    )
    if main:
        return main.place.name
    any_cp = (
        CircuitPlace.objects
        .filter(circuit_day__circuit=circuit)
        .select_related("place")
        .order_by("circuit_day__day_number", "visit_order")
        .first()
    )
    return any_cp.place.name if any_cp else ""


def _circuit_places_for_follow_up(circuit) -> list:
    """Lista de dicts {name, place_type, short_description} para el prompt FOLLOW_UP."""
    if circuit is None:
        return []
    from ..models import CircuitPlace
    stops = (
        CircuitPlace.objects
        .filter(circuit_day__circuit=circuit)
        .select_related("place")
        .order_by("circuit_day__day_number", "visit_order")
    )
    seen = set()
    items = []
    for s in stops:
        if s.place_id in seen:
            continue
        seen.add(s.place_id)
        items.append({
            "name": s.place.name,
            "place_type": s.place.get_place_type_display(),
            "short_description": s.place.short_description,
        })
        if len(items) >= 5:
            break
    return items


def _count_parse_retries(conversation: LeadConversation, state: str) -> int:
    """Cuenta mensajes consecutivos del usuario en el mismo estado sin parseo exitoso.
    Simple: cuenta mensajes USER desde el último cambio detectado."""
    if not conversation.pk:
        return 0
    return conversation.messages.filter(sender_type="USER").count() - 1


# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

def handle_start(conversation: LeadConversation) -> dict:
    text = (
        "¡Hola! Soy tu guía de Puerto Varas. Te ayudo a armar un plan a medida.\n\n"
        "¿Cuánto tiempo tienes?\n"
        "1) Medio día\n"
        "2) Día completo\n"
        "3) 2 días / 1 noche\n"
        "4) 3 días / 2 noches\n"
        "5) 4 días / 3 noches\n"
        "(o cuéntame con tus palabras: \"fin de semana\", \"una semana\", etc.)"
    )
    _append_assistant_message(conversation, text)
    action = build_channel_action(conversation)
    return build_response(
        reply_type=REPLY_TYPE_QUESTION,
        reply_text=text,
        conversation=conversation,
        channel_action=action,
    )


def handle_ask_duration(conversation: LeadConversation, message_text: str) -> dict:
    parsed = parse_duration_message(message_text)

    if parsed:
        dc = DurationCase.objects.filter(duration_type=parsed, is_active=True).first()
        if dc:
            conversation.detected_duration_case = dc
            conversation.save(update_fields=["detected_duration_case", "updated_at"])
            return handle_ask_interest(conversation, "")  # avanza al siguiente

    # No parseó — retry o derivar
    retries = _count_parse_retries(conversation, STATE_ASK_DURATION)
    if retries >= MAX_PARSE_RETRIES:
        conversation.showed_interest_in_aremko = True
        conversation.save(update_fields=["showed_interest_in_aremko", "updated_at"])
        return handle_referral(conversation)

    text = (
        "No pude identificar la duración. ¿Cuánto tiempo tienes?\n"
        "1) Medio día  2) Día completo  3) 2 días  4) 3 días  5) 4 días"
    )
    _append_assistant_message(conversation, text)
    return build_response(
        reply_type=REPLY_TYPE_QUESTION,
        reply_text=text,
        conversation=conversation,
        channel_action=build_channel_action(conversation),
    )


def handle_ask_interest(conversation: LeadConversation, message_text: str) -> dict:
    if message_text:
        parsed = parse_interest_message(message_text)
        if parsed:
            conversation.detected_interest = parsed
            conversation.save(update_fields=["detected_interest", "updated_at"])
            return handle_ask_profile(conversation, "")

        retries = _count_parse_retries(conversation, STATE_ASK_INTEREST)
        if retries >= MAX_PARSE_RETRIES:
            conversation.showed_interest_in_aremko = True
            conversation.save(update_fields=["showed_interest_in_aremko", "updated_at"])
            return handle_referral(conversation)

    text = (
        "¿Qué tipo de experiencia te interesa más?\n"
        "1) Naturaleza\n"
        "2) Gastronomía\n"
        "3) Aventura\n"
        "4) Relax / Romántico\n"
        "5) Mixto"
    )
    _append_assistant_message(conversation, text)
    return build_response(
        reply_type=REPLY_TYPE_QUESTION,
        reply_text=text,
        conversation=conversation,
        channel_action=build_channel_action(conversation),
    )


def handle_ask_profile(conversation: LeadConversation, message_text: str) -> dict:
    if message_text:
        parsed = parse_profile_message(message_text)
        if parsed:
            conversation.detected_profile = parsed
            conversation.save(update_fields=["detected_profile", "updated_at"])
            return handle_recommend_circuit(conversation)

        retries = _count_parse_retries(conversation, STATE_ASK_PROFILE)
        if retries >= MAX_PARSE_RETRIES:
            conversation.showed_interest_in_aremko = True
            conversation.save(update_fields=["showed_interest_in_aremko", "updated_at"])
            return handle_referral(conversation)

    text = (
        "¿Con quién viajas?\n"
        "1) Pareja\n"
        "2) Familia\n"
        "3) Amigos\n"
        "4) Solo/a"
    )
    _append_assistant_message(conversation, text)
    return build_response(
        reply_type=REPLY_TYPE_QUESTION,
        reply_text=text,
        conversation=conversation,
        channel_action=build_channel_action(conversation),
    )


def handle_recommend_circuit(conversation: LeadConversation) -> dict:
    result = recommend_circuit(
        duration_case=conversation.detected_duration_case,
        interest=conversation.detected_interest or None,
        profile=conversation.detected_profile or None,
        is_rainy=None,
    )
    circuit = result["circuit"]
    if circuit is not None:
        conversation.recommended_circuit = circuit
        conversation.save(update_fields=["recommended_circuit", "updated_at"])

    conv_depth = conversation.messages.count() if conversation.pk else 0
    aremko_applies = should_insert_aremko(
        duration_case=conversation.detected_duration_case,
        interest=conversation.detected_interest or None,
        profile=conversation.detected_profile or None,
        conversation_depth=conv_depth,
        explicit_interest=conversation.showed_interest_in_aremko,
    )
    aremko_reco = None
    if aremko_applies:
        aremko_reco = get_aremko_recommendation_for_context(
            duration_case=conversation.detected_duration_case,
            interest=conversation.detected_interest or None,
            profile=conversation.detected_profile or None,
        )

    if circuit is not None:
        fallback_text = f"Te recomiendo: {circuit.name}.\n{circuit.short_description}"
        if result["reasons"]:
            fallback_text += "\n\nPor qué: " + "; ".join(result["reasons"]) + "."
    else:
        fallback_text = "No encontré un circuito exacto. Puedo derivarte al equipo de Aremko para asesoría personalizada."

    if aremko_reco is not None:
        fallback_text += f"\n\n💧 {aremko_reco.title}: {aremko_reco.message_text}"

    # LLM: solo si hay un circuit para redactar — si no, mandamos fallback tal cual
    final_text = fallback_text
    llm_metadata: dict = {}
    if circuit is not None:
        from .llm.llm_reply_service import get_llm_reply_service
        llm_ctx = {
            "circuit": {
                "name": circuit.name,
                "duration_label": circuit.duration_case.name,
                "short_description": circuit.short_description,
            },
            "first_day_summary": _circuit_first_day_summary(circuit),
            "top_place_name": _circuit_top_place_name(circuit),
            "aremko_recommendation": (
                {"title": aremko_reco.title, "message_text": aremko_reco.message_text}
                if aremko_reco else None
            ),
        }
        llm_result = get_llm_reply_service().reply_recommend_circuit(llm_ctx, fallback_text)
        final_text = llm_result["text"]
        llm_metadata = llm_result.get("metadata") or {}

    msg = _append_assistant_message(conversation, final_text)
    _record_llm_metadata_if_any(msg, llm_metadata)

    return build_response(
        reply_type=REPLY_TYPE_RECOMMENDATION,
        reply_text=final_text,
        conversation=conversation,
        recommended_circuit=circuit,
        aremko_recommendation=aremko_reco,
        channel_action=build_channel_action(conversation),
    )


def handle_follow_up(conversation: LeadConversation, message_text: str) -> dict:
    if detect_aremko_interest(message_text):
        conversation.showed_interest_in_aremko = True
        conversation.save(update_fields=["showed_interest_in_aremko", "updated_at"])
        return handle_referral(conversation)

    fallback_text = (
        "Puedo darte más detalle del circuito, sugerir restaurantes o actividades. "
        "¿Qué te gustaría profundizar?"
    )

    circuit = conversation.recommended_circuit
    from .llm.llm_reply_service import get_llm_reply_service
    llm_ctx = {
        "recommended_circuit": {"name": circuit.name} if circuit else None,
        "available_places": _circuit_places_for_follow_up(circuit),
    }
    llm_result = get_llm_reply_service().reply_follow_up(llm_ctx, message_text, fallback_text)
    final_text = llm_result["text"]
    llm_metadata = llm_result.get("metadata") or {}

    msg = _append_assistant_message(conversation, final_text)
    _record_llm_metadata_if_any(msg, llm_metadata)

    return build_response(
        reply_type=REPLY_TYPE_INFO,
        reply_text=final_text,
        conversation=conversation,
        recommended_circuit=conversation.recommended_circuit,
        channel_action=build_channel_action(conversation),
    )


def handle_aremko_suggestion(conversation: LeadConversation) -> dict:
    aremko_reco = get_aremko_recommendation_for_context(
        duration_case=conversation.detected_duration_case,
        interest=conversation.detected_interest or None,
        profile=conversation.detected_profile or None,
    )
    text = (
        "Noté que mencionaste spa, tinas o alojamiento. Aremko Spa Boutique en Puerto Varas "
        "es ideal para eso — ¿querés los accesos directos de reserva?"
    )
    if aremko_reco is not None:
        text = f"{aremko_reco.title}: {aremko_reco.message_text}\n\n" + text
    _append_assistant_message(conversation, text)
    return build_response(
        reply_type=REPLY_TYPE_INFO,
        reply_text=text,
        conversation=conversation,
        recommended_circuit=conversation.recommended_circuit,
        aremko_recommendation=aremko_reco,
        channel_action=build_channel_action(conversation),
    )


def handle_referral(conversation: LeadConversation) -> dict:
    payload = build_aremko_referral_payload(conversation)
    if payload["should_refer"]:
        conversation.referred_to_aremko = True
        conversation.status = ConversationStatus.REFERRED_TO_AREMKO
        conversation.save(update_fields=["referred_to_aremko", "status", "updated_at"])

    text = payload["reply_text"] or (
        "Te derivo al equipo de Aremko para que te asistan directamente."
    )
    text_with_urls = text
    if payload.get("reservation_url"):
        text_with_urls += f"\n\nReserva: {payload['reservation_url']}"
    if payload.get("whatsapp_url"):
        text_with_urls += f"\nWhatsApp: {payload['whatsapp_url']}"

    _append_assistant_message(conversation, text_with_urls)
    return build_response(
        reply_type=REPLY_TYPE_REFERRAL,
        reply_text=text_with_urls,
        conversation=conversation,
        channel_action=build_channel_action(conversation),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point para IncomingMessageView
# ─────────────────────────────────────────────────────────────────────────────

def _legacy_process_incoming_message(
    conversation: LeadConversation,
    message_text: str,
) -> dict:
    """Máquina de estados determinística (fallback). No usa LLM conversacional."""
    # Señal global: menciones de Aremko
    if detect_aremko_interest(message_text):
        conversation.showed_interest_in_aremko = True
        conversation.save(update_fields=["showed_interest_in_aremko", "updated_at"])

    state = get_next_state(conversation)

    if state == STATE_REFERRED_TO_AREMKO:
        return handle_referral(conversation)
    if state == STATE_AREMKO_SUGGESTED:
        return handle_referral(conversation)
    if state == STATE_FOLLOW_UP:
        return handle_follow_up(conversation, message_text)
    if state == STATE_RECOMMEND_CIRCUIT:
        return handle_recommend_circuit(conversation)
    if state == STATE_ASK_PROFILE:
        return handle_ask_profile(conversation, message_text)
    if state == STATE_ASK_INTEREST:
        return handle_ask_interest(conversation, message_text)
    if state == STATE_ASK_DURATION:
        return handle_ask_duration(conversation, message_text)
    return handle_start(conversation)


def _persist_agent_message(
    conversation: LeadConversation,
    text: str,
    metadata: dict,
) -> None:
    """Persiste la respuesta del agente LLM con su metadata (tokens, costo, latencia)."""
    msg = ConversationMessage.objects.create(
        conversation=conversation,
        sender_type=MessageSenderType.ASSISTANT,
        text=text,
        llm_model=metadata.get("model", "") or "",
        llm_input_tokens=metadata.get("input_tokens", 0) or 0,
        llm_output_tokens=metadata.get("output_tokens", 0) or 0,
        llm_latency_ms=metadata.get("latency_ms", 0) or 0,
        llm_error=(metadata.get("error") or "")[:200],
    )
    conversation.last_assistant_message_at = timezone.now()
    conversation.save(update_fields=["last_assistant_message_at", "updated_at"])
    return msg


def process_incoming_message(
    conversation: LeadConversation,
    message_text: str,
) -> dict:
    """Entry point del flujo conversacional.

    Desde DPV-008, delega al agente LLM (agent_service.respond). Si el agente
    está desactivado, sin template activo, o falla → cae al state machine legacy.
    """
    # Import tardío para evitar ciclos y permitir que settings estén cargados
    from .agent_service import is_agent_available, respond as agent_respond

    if is_agent_available():
        try:
            result = agent_respond(conversation, message_text)
        except Exception as exc:
            logger.exception("agent_service.respond falló: %s", exc)
            result = None

        if result and result.get("ok") and result.get("text"):
            text = result["text"]
            metadata = result.get("metadata") or {}
            _persist_agent_message(conversation, text, metadata)
            # Refrescar conversation por si una tool (refer_user_to_aremko) la mutó
            conversation.refresh_from_db()
            return build_response(
                reply_type=REPLY_TYPE_INFO,
                reply_text=text,
                conversation=conversation,
                recommended_circuit=conversation.recommended_circuit,
                channel_action=build_channel_action(conversation),
            )

        # Agente disponible pero falló → loguear y caer al legacy
        err = (result or {}).get("error", "unknown")
        logger.warning(
            "Agente LLM falló (conv=%s, error=%s); cayendo al state machine",
            conversation.id, err,
        )

    return _legacy_process_incoming_message(conversation, message_text)
