"""Agente conversacional LLM con tool-calling para Destino Puerto Varas.

Entry point: respond(conversation, user_message) -> dict

Reemplaza la máquina de estados regex-based por un LLM que conversa naturalmente
y tiene acceso a tools para consultar el catálogo de circuitos y derivar a Aremko.

El system prompt se carga desde el modelo AgentPromptTemplate (editable en admin).
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from ..enums import ConversationStatus, InterestType, MessageSenderType, ProfileType
from ..models import (
    AgentPromptTemplate,
    Circuit,
    CircuitDay,
    ConversationMessage,
    LeadConversation,
)
from .llm.openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)


AGENT_SLUG = "dpv-main-guide"


# ─────────────────────────────────────────────────────────────────────────────
# Tools: definición JSON-Schema que ve el LLM
# ─────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_circuits",
            "description": (
                "Lista circuitos turísticos publicados en Puerto Varas. "
                "Usa filtros opcionales para afinar. Retorna hasta 8 circuitos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "interest": {
                        "type": "string",
                        "enum": [c.value for c in InterestType],
                        "description": "Interés principal: NATURE, GASTRONOMY, ADVENTURE, RELAX_ROMANTIC, MIXED.",
                    },
                    "profile": {
                        "type": "string",
                        "enum": [c.value for c in ProfileType],
                        "description": "Perfil del viajero: COUPLE, FAMILY, FRIENDS, SOLO.",
                    },
                    "duration_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 7,
                        "description": "Días de duración. Usa 1 para medio día o día completo.",
                    },
                    "is_rainy": {
                        "type": "boolean",
                        "description": "Si es true, prioriza circuitos aptos para lluvia.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_circuit_detail",
            "description": (
                "Obtiene el detalle completo de un circuito: descripción larga, días, "
                "lugares principales por día. Usa el slug que viene de list_circuits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Slug del circuito (ej: 'circuito-volcanico-1-dia').",
                    },
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refer_user_to_aremko",
            "description": (
                "USAR SOLO cuando el usuario pide explícitamente reservar en Aremko "
                "(cabaña, tinas, spa, masaje). Marca la conversación como derivada y "
                "retorna las URLs de reserva y WhatsApp. NO usar ante saludos o "
                "preguntas genéricas sobre el destino."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Breve justificación de por qué se deriva (para auditoría).",
                    },
                },
                "required": ["reason"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────────────────────────────────────

def _tool_list_circuits(arguments: dict) -> dict:
    qs = Circuit.objects.filter(published=True)
    interest = arguments.get("interest")
    profile = arguments.get("profile")
    duration_days = arguments.get("duration_days")
    is_rainy = arguments.get("is_rainy")

    if interest:
        qs = qs.filter(primary_interest=interest)
    if profile:
        qs = qs.filter(recommended_profile=profile)
    if duration_days is not None:
        qs = qs.filter(duration_case__days=duration_days)
    if is_rainy:
        qs = qs.filter(is_rain_friendly=True)

    circuits = qs.select_related("duration_case").order_by("sort_order", "number")[:8]
    results = []
    for c in circuits:
        duration_label = c.duration_case.name if c.duration_case_id else ""
        results.append({
            "number": c.number,
            "name": c.name,
            "slug": c.slug,
            "duration_label": duration_label,
            "primary_interest": c.primary_interest,
            "recommended_profile": c.recommended_profile or "",
            "short_description": c.short_description,
            "is_romantic": c.is_romantic,
            "is_family_friendly": c.is_family_friendly,
            "is_adventure": c.is_adventure,
            "is_rain_friendly": c.is_rain_friendly,
            "is_premium": c.is_premium,
        })

    return {"count": len(results), "circuits": results}


def _tool_get_circuit_detail(arguments: dict) -> dict:
    slug = arguments.get("slug", "")
    if not slug:
        return {"error": "missing_slug"}

    circuit = Circuit.objects.filter(published=True, slug=slug).select_related("duration_case").first()
    if not circuit:
        return {"error": "circuit_not_found", "slug": slug}

    days_data = []
    for day in CircuitDay.objects.filter(circuit=circuit).order_by("day_number", "sort_order"):
        places = []
        for stop in day.place_stops.select_related("place").order_by("visit_order")[:5]:
            places.append({
                "name": stop.place.name,
                "type": stop.place.place_type,
                "short_description": stop.place.short_description,
                "is_main_stop": stop.is_main_stop,
            })
        days_data.append({
            "day_number": day.day_number,
            "title": day.title,
            "block_type": day.block_type,
            "summary": day.summary or "",
            "places": places,
        })

    return {
        "number": circuit.number,
        "name": circuit.name,
        "slug": circuit.slug,
        "duration_label": circuit.duration_case.name if circuit.duration_case_id else "",
        "primary_interest": circuit.primary_interest,
        "recommended_profile": circuit.recommended_profile or "",
        "short_description": circuit.short_description,
        "long_description": circuit.long_description or "",
        "is_romantic": circuit.is_romantic,
        "is_family_friendly": circuit.is_family_friendly,
        "is_adventure": circuit.is_adventure,
        "is_rain_friendly": circuit.is_rain_friendly,
        "is_premium": circuit.is_premium,
        "days": days_data,
    }


def _tool_refer_user_to_aremko(conversation: LeadConversation, arguments: dict) -> dict:
    reason = (arguments.get("reason") or "")[:500]
    reservation_url = getattr(settings, "AREMKO_RESERVATION_URL", "") or "https://www.aremko.cl/"
    whatsapp_url = getattr(settings, "AREMKO_WHATSAPP_URL", "") or "https://wa.me/56958655810"

    if not conversation.referred_to_aremko:
        conversation.referred_to_aremko = True
        conversation.showed_interest_in_aremko = True
        conversation.status = ConversationStatus.REFERRED_TO_AREMKO
        note = f"[agente LLM] derivado a Aremko: {reason}"
        conversation.notes = (conversation.notes + "\n" + note).strip() if conversation.notes else note
        conversation.save(update_fields=[
            "referred_to_aremko",
            "showed_interest_in_aremko",
            "status",
            "notes",
            "updated_at",
        ])

    return {
        "referred": True,
        "reservation_url": reservation_url,
        "whatsapp_url": whatsapp_url,
        "instructions": (
            "Confirma al usuario que lo derivas al equipo Aremko e incluye ambas URLs "
            "en tu respuesta (reserva web y WhatsApp) en líneas separadas."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Historia de conversación → mensajes LLM
# ─────────────────────────────────────────────────────────────────────────────

_ROLE_MAP = {
    MessageSenderType.USER: "user",
    MessageSenderType.ASSISTANT: "assistant",
    MessageSenderType.AGENT: "assistant",
    MessageSenderType.SYSTEM: "system",
}


def _build_history_messages(
    conversation: LeadConversation,
    current_user_message: str,
    window: int,
) -> list[dict]:
    """Últimos `window` mensajes previos + el mensaje actual del usuario.

    Los mensajes previos del usuario actual no se incluyen como duplicados porque
    el caller ya persistió `current_user_message` antes de llamar al agente.
    Por eso filtramos por id estricto: traemos los últimos `window` y el actual
    como último user turn (aunque esté en la query, lo agregamos explícitamente).
    """
    qs = (
        ConversationMessage.objects.filter(conversation=conversation)
        .exclude(sender_type=MessageSenderType.SYSTEM)
        .order_by("-created_at")[:window]
    )
    history = list(reversed(list(qs)))

    messages = []
    for m in history:
        role = _ROLE_MAP.get(m.sender_type, "user")
        text = (m.text or "").strip()
        if not text:
            continue
        messages.append({"role": role, "content": text})

    # Asegurar que el último mensaje del usuario visible es el actual.
    # Si el último de la historia ya es el current_user_message con mismo texto,
    # no dupliquemos. Si no, lo agregamos.
    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != current_user_message:
        messages.append({"role": "user", "content": current_user_message})

    return messages


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def _get_active_template() -> Optional[AgentPromptTemplate]:
    try:
        return AgentPromptTemplate.objects.get(slug=AGENT_SLUG, is_active=True)
    except AgentPromptTemplate.DoesNotExist:
        logger.warning("AgentPromptTemplate slug=%s no existe o no está activo", AGENT_SLUG)
        return None


def is_agent_available() -> bool:
    """Chequea condiciones mínimas para usar el agente LLM."""
    if not getattr(settings, "DPV_LLM_ENABLED", False):
        return False
    if not getattr(settings, "OPENROUTER_API_KEY", ""):
        return False
    return _get_active_template() is not None


def respond(conversation: LeadConversation, user_message: str) -> dict:
    """Genera respuesta del agente conversacional.

    Retorna dict con forma:
      {"ok": True, "text": str, "tool_calls": [...], "metadata": {...}}
      {"ok": False, "text": "", "error": str}

    El caller (process_incoming_message) se encarga de persistir el mensaje del
    asistente y despacharlo al canal.
    """
    template = _get_active_template()
    if template is None:
        return {"ok": False, "text": "", "error": "no_active_prompt_template"}

    system_prompt = template.system_prompt
    model_name = template.model_name
    temperature = float(template.temperature)
    max_tokens = template.max_output_tokens
    history_window = template.history_window

    history = _build_history_messages(conversation, user_message, history_window)
    messages = [{"role": "system", "content": system_prompt}, *history]

    def tool_executor(name: str, arguments: dict) -> dict:
        if name == "list_circuits":
            return _tool_list_circuits(arguments)
        if name == "get_circuit_detail":
            return _tool_get_circuit_detail(arguments)
        if name == "refer_user_to_aremko":
            return _tool_refer_user_to_aremko(conversation, arguments)
        return {"error": f"unknown_tool: {name}"}

    provider = OpenRouterProvider()
    result = provider.generate_with_tools(
        messages=messages,
        tools=TOOL_DEFINITIONS,
        tool_executor=tool_executor,
        model=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        max_iterations=3,
    )

    if not result.ok or not result.text:
        return {
            "ok": False,
            "text": "",
            "error": result.error or "empty_response",
            "tool_calls": result.tool_calls_executed,
            "metadata": {
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": result.latency_ms,
            },
        }

    return {
        "ok": True,
        "text": result.text,
        "tool_calls": result.tool_calls_executed,
        "metadata": {
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
            "error": "",
        },
    }
