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
from django.db.models import Q

from ..models import (
    AgentPromptTemplate,
    Circuit,
    CircuitDay,
    ConversationMessage,
    LeadConversation,
    Place,
)
from .llm.openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)


AGENT_SLUG = "dpv-main-guide"

# Base URL del sitio público DPV (hoy montado en aremko.cl/dpv;
# cuando migre a destinopuertovaras.cl basta con cambiar el setting).
DPV_PUBLIC_BASE_URL = getattr(
    settings, "DPV_PUBLIC_BASE_URL", "https://www.aremko.cl/dpv"
).rstrip("/")


def _circuit_public_url(slug: str) -> str:
    return f"{DPV_PUBLIC_BASE_URL}/circuitos/{slug}/"


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
                "Usa filtros opcionales para afinar. Si retorna 0 con filtros estrictos, "
                "automáticamente vuelve a buscar relajando filtros y marca "
                "'broadened=true'. Retorna hasta 8 circuitos."
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
                        "minimum": 0,
                        "maximum": 7,
                        "description": "Días. Usa 0 para medio día, 1 para día completo, 2-3 para multi-día.",
                    },
                    "is_rainy": {
                        "type": "boolean",
                        "description": "Si es true, prioriza circuitos aptos para lluvia.",
                    },
                    "is_romantic": {
                        "type": "boolean",
                        "description": "True si el viajero busca algo romántico (pareja).",
                    },
                    "is_family_friendly": {
                        "type": "boolean",
                        "description": "True si viaja con niños.",
                    },
                    "is_adventure": {
                        "type": "boolean",
                        "description": "True si busca aventura/actividad física.",
                    },
                    "categories": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["nature", "culture", "gastronomy", "adventure", "family"],
                        },
                        "description": (
                            "Categorías que le interesan al turista (multi-valor, OR). "
                            "Ej: ['culture','gastronomy'] devuelve circuitos de cultura O "
                            "gastronomía O ambos. Equivalencias: nature=is_nature, "
                            "culture=is_culture, gastronomy=is_gastronomy, "
                            "adventure=is_adventure, family=is_family_friendly."
                        ),
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
                "Detalle completo de un circuito: narrativa editorial, días con resumen, "
                "y CADA lugar de visita con datos enriquecidos (altura, año, infraestructura, "
                "entrada, tarifas detalladas, distancia/tiempo desde Pto Varas, fotos). "
                "Si el usuario pregunta por precios/tarifas, prioriza el campo `entry_fee_text` "
                "(detalle real con diferenciales adulto/niño/extranjero, por consumo, etc.) "
                "sobre `entry_fee_clp` (valor único representativo). Usa el slug de list_circuits. "
                "El response incluye `public_url` con el itinerario visual del circuito en el sitio "
                "Destino Puerto Varas (acuarelas, mapa de paradas, datos prácticos completos): "
                "compartilo SIEMPRE al usuario cuando muestres un circuito en detalle."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Slug del circuito (ej: 'aventura-lago-llanquihue-3d2n').",
                    },
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_place_detail",
            "description": (
                "Información detallada de UN lugar específico: descripción, altura, año, "
                "infraestructura (parking/baños/CONAF), entrada, tarifas detalladas, "
                "distancia/tiempo desde Puerto Varas, datos curiosos, fotos. Usar cuando "
                "el usuario pregunta por un atractivo puntual ('cuánto mide el Volcán "
                "Osorno', 'cómo llego a Petrohué', 'cuánto cuesta entrar a...', 'tiene "
                "baños el parque...'). Si pregunta por precios, prioriza `entry_fee_text` "
                "(detalle real con diferenciales) sobre `entry_fee_clp` (valor único). "
                "Acepta slug exacto O un nombre para búsqueda parcial."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Slug exacto del lugar (preferido si lo conoces).",
                    },
                    "name_query": {
                        "type": "string",
                        "description": "Búsqueda por nombre parcial (case-insensitive). Ej: 'osorno', 'petrohué'.",
                    },
                },
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

def _circuit_brief(c: Circuit) -> dict:
    """Representación corta de un circuito para list_circuits."""
    return {
        "number": c.number,
        "name": c.name,
        "slug": c.slug,
        "public_url": _circuit_public_url(c.slug),
        "duration_label": c.duration_case.name if c.duration_case_id else "",
        "duration_days": c.duration_case.days if c.duration_case_id else None,
        "duration_nights": c.duration_case.nights if c.duration_case_id else None,
        "primary_interest": c.primary_interest,
        "recommended_profile": c.recommended_profile or "",
        "short_description": c.short_description,
        "is_romantic": c.is_romantic,
        "is_family_friendly": c.is_family_friendly,
        "is_adventure": c.is_adventure,
        "is_rain_friendly": c.is_rain_friendly,
        "is_premium": c.is_premium,
        "is_nature": c.is_nature,
        "is_culture": c.is_culture,
        "is_gastronomy": c.is_gastronomy,
    }


def _place_summary(place: Place, *, include_long_desc: bool = False) -> dict:
    """Datos enriquecidos de un Place para enviar al LLM como contexto."""
    primary_photo = place.photos.filter(is_primary=True).first() or place.photos.order_by("order").first()
    photo_url = ""
    photo_credit = ""
    if primary_photo:
        if primary_photo.image:
            photo_url = primary_photo.image.url
        elif primary_photo.source_url:
            photo_url = primary_photo.source_url
        photo_credit = primary_photo.credit

    summary = {
        "name": place.name,
        "slug": place.slug,
        "place_type": place.place_type,
        "location_label": place.location_label,
        "short_description": place.short_description,
        "elevation_m": place.elevation_m,
        "year_established": place.year_established,
        "has_parking": place.has_parking,
        "has_restrooms": place.has_restrooms,
        "has_conaf_office": place.has_conaf_office,
        "has_food_service": place.has_food_service,
        "entry_fee_clp": place.entry_fee_clp,
        "entry_fee_text": place.entry_fee_text,
        "best_season": place.best_season,
        "accessibility_notes": place.accessibility_notes,
        "distance_from_pv_km": float(place.distance_from_pv_km) if place.distance_from_pv_km is not None else None,
        "drive_time_from_pv_min": place.drive_time_from_pv_min,
        "requires_reservation": place.requires_reservation,
        "recommended_visit_duration": place.recommended_visit_duration,
        "payment_methods": place.payment_methods,
        "pet_friendly": place.pet_friendly,
        "has_tourist_info": place.has_tourist_info,
        "nearby_food_options": place.nearby_food_options,
        "parking_details": place.parking_details,
        "primary_photo_url": photo_url,
        "primary_photo_credit": photo_credit,
        "photos_count": place.photos.count(),
    }
    if include_long_desc:
        summary["long_description"] = place.long_description or ""
        summary["did_you_know"] = place.did_you_know or ""
        summary["practical_tips"] = place.practical_tips or ""
        summary["safety_notes"] = place.safety_notes or ""
        # extra_data puede ser grande — limitamos a primeras 8 claves
        extra = place.extra_data or {}
        if extra:
            summary["extra_data"] = dict(list(extra.items())[:8])
    return summary


def _tool_list_circuits(arguments: dict) -> dict:
    """Lista circuitos con filtros + broadening automático si 0 resultados.

    Excluye circuitos sin itinerario armado (sin días) — el agente no debe
    recomendarle al turista circuitos que aparecen como "Próximamente".
    """
    from django.db.models import Count

    base_qs = (
        Circuit.objects.filter(published=True)
        .annotate(_days_count=Count("days"))
        .filter(_days_count__gt=0)
    )

    interest = arguments.get("interest")
    profile = arguments.get("profile")
    duration_days = arguments.get("duration_days")
    is_rainy = arguments.get("is_rainy")
    is_romantic = arguments.get("is_romantic")
    is_family_friendly = arguments.get("is_family_friendly")
    is_adventure = arguments.get("is_adventure")
    raw_categories = arguments.get("categories") or []
    category_map = {
        "nature": "is_nature",
        "culture": "is_culture",
        "gastronomy": "is_gastronomy",
        "adventure": "is_adventure",
        "family": "is_family_friendly",
    }
    categories = [c for c in raw_categories if c in category_map]

    def _apply(qs, *, with_profile=True, with_duration=True, with_flags=True, with_categories=True):
        if interest:
            qs = qs.filter(primary_interest=interest)
        if with_profile and profile:
            qs = qs.filter(recommended_profile=profile)
        if with_duration and duration_days is not None:
            qs = qs.filter(duration_case__days=duration_days)
        if is_rainy:
            qs = qs.filter(is_rain_friendly=True)
        if with_flags:
            if is_romantic:
                qs = qs.filter(is_romantic=True)
            if is_family_friendly:
                qs = qs.filter(is_family_friendly=True)
            if is_adventure:
                qs = qs.filter(is_adventure=True)
        if with_categories and categories:
            from django.db.models import Q
            cat_q = Q()
            for cat in categories:
                cat_q |= Q(**{category_map[cat]: True})
            qs = qs.filter(cat_q).distinct()
        return qs

    # Estrategia: probar de más estricto a más permisivo.
    # Las categorías (multi-valor con OR interno) son lo más cercano a la intención
    # del turista, así que se relajan AL FINAL: primero soltamos profile/duration/flags.
    attempts = [
        ("strict", lambda: _apply(base_qs)),
        ("no_profile", lambda: _apply(base_qs, with_profile=False)),
        ("no_profile_no_flags", lambda: _apply(base_qs, with_profile=False, with_flags=False)),
        ("only_categories", lambda: _apply(
            base_qs, with_profile=False, with_duration=False, with_flags=False,
        )),
        ("all_published", lambda: base_qs),
    ]

    chosen_label = "strict"
    chosen_qs = None
    for label, builder in attempts:
        qs = builder().select_related("duration_case").order_by("sort_order", "number")
        if qs.exists():
            chosen_qs = qs
            chosen_label = label
            break

    circuits = list((chosen_qs or base_qs.none())[:8])
    results = [_circuit_brief(c) for c in circuits]

    response = {
        "count": len(results),
        "circuits": results,
        "broadened": chosen_label != "strict",
        "broadening_strategy": chosen_label,
    }
    if chosen_label != "strict":
        response["note"] = (
            "Los filtros estrictos no encontraron circuitos. Se relajaron filtros para "
            "ofrecer alternativas. Mencionalo al usuario si es relevante."
        )
    return response


def _tool_get_circuit_detail(arguments: dict) -> dict:
    slug = arguments.get("slug", "")
    if not slug:
        return {"error": "missing_slug"}

    circuit = (
        Circuit.objects.filter(published=True, slug=slug)
        .select_related("duration_case")
        .first()
    )
    if not circuit:
        return {"error": "circuit_not_found", "slug": slug}

    days_data = []
    for day in (
        CircuitDay.objects.filter(circuit=circuit)
        .order_by("day_number", "sort_order")
        .prefetch_related("place_stops__place__photos")
    ):
        places = []
        for stop in day.place_stops.order_by("visit_order")[:6]:
            place_info = _place_summary(stop.place)
            place_info["is_main_stop"] = stop.is_main_stop
            place_info["visit_order"] = stop.visit_order
            places.append(place_info)
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
        "public_url": _circuit_public_url(circuit.slug),
        "duration_label": circuit.duration_case.name if circuit.duration_case_id else "",
        "duration_days": circuit.duration_case.days if circuit.duration_case_id else None,
        "duration_nights": circuit.duration_case.nights if circuit.duration_case_id else None,
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


def _tool_get_place_detail(arguments: dict) -> dict:
    """Busca un Place por slug exacto o por nombre parcial. Retorna datos completos."""
    slug = (arguments.get("slug") or "").strip()
    name_query = (arguments.get("name_query") or "").strip()

    place = None
    if slug:
        place = (
            Place.objects.filter(published=True, slug=slug)
            .prefetch_related("photos")
            .first()
        )
    if not place and name_query:
        # Búsqueda parcial case-insensitive en nombre o slug
        place = (
            Place.objects.filter(published=True)
            .filter(Q(name__icontains=name_query) | Q(slug__icontains=name_query))
            .prefetch_related("photos")
            .order_by("name")
            .first()
        )

    if not place:
        return {
            "error": "place_not_found",
            "slug": slug,
            "name_query": name_query,
        }

    data = _place_summary(place, include_long_desc=True)
    # Lista de fotos (no solo la primaria)
    photos = []
    for photo in place.photos.order_by("order", "id")[:6]:
        url = ""
        if photo.image:
            url = photo.image.url
        elif photo.source_url:
            url = photo.source_url
        if url:
            photos.append({
                "url": url,
                "caption": photo.caption,
                "credit": photo.credit,
                "is_primary": photo.is_primary,
            })
    data["photos"] = photos
    return data


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
        if name == "get_place_detail":
            return _tool_get_place_detail(arguments)
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
