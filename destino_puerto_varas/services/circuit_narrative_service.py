"""Genera narrativas editoriales para Circuits a partir de los Places ordenados.

A diferencia del enriquecimiento de Place (que usa Perplexity para buscar info en la
web), este servicio usa OpenRouter (Claude/Haiku) porque toda la data ya está en DB
— solo hay que sintetizar.

Flujo:
    1. generate_circuit_narrative(circuit) → reúne contexto de places + days, llama
       LLM, crea CircuitNarrativeDraft.
    2. apply_narrative_draft(draft) → vuelca al Circuit (long_description + summaries
       de cada día).

Detección de staleness: el draft guarda el `places_signature` del momento. Si las
paradas cambiaron después, el admin puede mostrar warning "narrativa stale".
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.utils import timezone

from ..models import Circuit, CircuitDay, CircuitNarrativeDraft
from .llm.openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres un copywriter editorial de turismo especializado en Puerto Varas \
y la región de Los Lagos (Chile). Tu trabajo es transformar la lista de paradas de un \
circuito turístico en una narrativa atractiva, coherente y útil para el viajero.

Reglas de tono:
- Cercano, evocador, sensorial — pero sin caer en clichés gastados.
- Español de Chile, sin modismos de otros países.
- Hechos verificables: solo afirma lo que aparece en los datos del lugar (no inventes \
  altura, año, infraestructura).
- Nunca menciones que el texto fue generado por IA.
- Conecta las paradas con transiciones suaves ("desde aquí, ...", "tras unos minutos en \
  auto, ...", "al caer la tarde, ...").

Formato de respuesta — DEVUELVE SOLO JSON, sin texto antes/después, sin bloque ```. \
Estructura exacta:

{
  "circuit_long_description": "<texto editorial 400-700 palabras describiendo el circuito completo, día por día, lugar por lugar>",
  "day_summaries": {
    "1": "<resumen del día 1, 80-150 palabras>",
    "2": "<resumen del día 2, 80-150 palabras>"
  }
}

- circuit_long_description debe abrir con un hook (qué hace especial este circuito), \
  recorrer cada parada en orden con ~50-80 palabras por parada, y cerrar con una nota \
  evocadora.
- day_summaries: una clave por cada día del circuito (claves como string, "1", "2", ...). \
  Si el circuito es de 1 día (medio día), solo "1".
- El JSON debe ser válido (comillas dobles, sin trailing commas).
"""


def generate_circuit_narrative(
    circuit: Circuit,
    *,
    save: bool = True,
    model: str | None = None,
) -> CircuitNarrativeDraft | None:
    """Genera un CircuitNarrativeDraft para `circuit` usando OpenRouter.

    Si `save=False`, retorna el draft sin persistir.
    Retorna None si OpenRouter no está configurado.
    """
    provider = OpenRouterProvider()
    if not provider.api_key:
        logger.warning("generate_circuit_narrative: OPENROUTER_API_KEY no configurada")
        return None

    user_prompt = _build_circuit_context(circuit)
    signature = circuit.compute_places_signature()

    result = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=2500,
        temperature=0.6,  # algo más alto: queremos prosa, no datos crudos
    )

    if not result.ok:
        draft = CircuitNarrativeDraft(
            circuit=circuit,
            status=CircuitNarrativeDraft.STATUS_REJECTED,
            places_signature=signature,
            proposed_data={},
            llm_model=result.model,
            llm_input_tokens=result.input_tokens,
            llm_output_tokens=result.output_tokens,
            llm_latency_ms=result.latency_ms,
            review_notes=f"[auto] LLM falló: {result.error}",
        )
        if save:
            draft.save()
        return draft

    parsed, parse_error = _parse_json(result.text)
    proposed = _normalize(parsed) if parsed else {"raw_text": result.text}

    draft = CircuitNarrativeDraft(
        circuit=circuit,
        status=CircuitNarrativeDraft.STATUS_DRAFT,
        places_signature=signature,
        proposed_data=proposed,
        llm_model=result.model,
        llm_input_tokens=result.input_tokens,
        llm_output_tokens=result.output_tokens,
        llm_latency_ms=result.latency_ms,
        review_notes=("[auto] Error parseando JSON: " + parse_error) if parse_error else "",
    )
    if save:
        draft.save()
    return draft


def apply_narrative_draft(
    draft: CircuitNarrativeDraft,
    *,
    reviewer: str = "",
) -> bool:
    """Aplica un draft aprobado al Circuit + CircuitDay summaries."""
    if draft.status != CircuitNarrativeDraft.STATUS_APPROVED:
        logger.warning(
            "apply_narrative_draft: draft #%s no está aprobado (status=%s)",
            draft.id,
            draft.status,
        )
        return False

    circuit = draft.circuit
    proposed = draft.proposed_data or {}

    long_desc = (proposed.get("circuit_long_description") or "").strip()
    if long_desc:
        circuit.long_description = long_desc

    circuit.places_signature = draft.places_signature or circuit.compute_places_signature()
    circuit.last_narrative_at = timezone.now()
    circuit.save()

    # Día por día
    day_summaries = proposed.get("day_summaries") or {}
    for key, summary in day_summaries.items():
        try:
            day_num = int(key)
        except (TypeError, ValueError):
            continue
        try:
            day = CircuitDay.objects.get(circuit=circuit, day_number=day_num)
        except CircuitDay.DoesNotExist:
            continue
        if summary and isinstance(summary, str):
            day.summary = summary.strip()
            day.save()

    draft.status = CircuitNarrativeDraft.STATUS_APPLIED
    draft.applied_at = timezone.now()
    if reviewer and not draft.reviewed_by:
        draft.reviewed_by = reviewer
    if not draft.reviewed_at:
        draft.reviewed_at = timezone.now()
    draft.save()
    return True


# ─── Helpers privados ───


def _build_circuit_context(circuit: Circuit) -> str:
    """Arma el bloque de datos del circuito para enviar al LLM."""
    lines: list[str] = []
    lines.append(f"Circuito: {circuit.name} (#{circuit.number})")
    lines.append(f"Slug: {circuit.slug}")
    if circuit.short_description:
        lines.append(f"Descripción breve: {circuit.short_description}")
    if circuit.duration_case_id:
        dc = circuit.duration_case
        lines.append(f"Duración: {dc.days} día(s) / {dc.nights} noche(s) — {dc.name}")
    lines.append(f"Interés principal: {circuit.get_primary_interest_display()}")
    if circuit.recommended_profile:
        lines.append(f"Perfil recomendado: {circuit.get_recommended_profile_display()}")

    flags = []
    if circuit.is_romantic: flags.append("romántico")
    if circuit.is_family_friendly: flags.append("apto familias")
    if circuit.is_adventure: flags.append("aventura")
    if circuit.is_rain_friendly: flags.append("apto lluvia")
    if circuit.is_premium: flags.append("premium")
    if flags:
        lines.append(f"Etiquetas: {', '.join(flags)}")

    lines.append("")
    lines.append("=== PARADAS POR DÍA ===")

    days = circuit.days.order_by("day_number", "sort_order").prefetch_related(
        "place_stops__place__photos"
    )
    if not days.exists():
        lines.append("(este circuito no tiene días definidos todavía)")
        return "\n".join(lines)

    for day in days:
        lines.append("")
        lines.append(f"--- Día {day.day_number}: {day.title} ({day.get_block_type_display()}) ---")
        if day.summary:
            lines.append(f"Resumen actual: {day.summary}")

        stops = day.place_stops.order_by("visit_order")
        if not stops.exists():
            lines.append("(sin paradas)")
            continue

        for stop in stops:
            place = stop.place
            marker = " [PARADA PRINCIPAL]" if stop.is_main_stop else ""
            lines.append(f"\n  Parada {stop.visit_order}: {place.name}{marker}")
            if place.location_label:
                lines.append(f"    Ubicación: {place.location_label}")
            if place.short_description:
                lines.append(f"    Descripción breve: {place.short_description}")
            if place.elevation_m:
                lines.append(f"    Altitud: {place.elevation_m} m")
            if place.year_established:
                lines.append(f"    Año: {place.year_established}")
            if place.distance_from_pv_km:
                lines.append(f"    Distancia desde Pto Varas: {place.distance_from_pv_km} km")
            if place.drive_time_from_pv_min:
                lines.append(f"    Tiempo en auto desde Pto Varas: {place.drive_time_from_pv_min} min")
            infra = []
            if place.has_parking: infra.append("estacionamiento")
            if place.has_restrooms: infra.append("baños")
            if place.has_conaf_office: infra.append("oficina CONAF")
            if place.has_food_service: infra.append("servicio de comida")
            if infra:
                lines.append(f"    Infraestructura: {', '.join(infra)}")
            if place.entry_fee_clp is not None:
                fee = "gratis" if place.entry_fee_clp == 0 else f"${place.entry_fee_clp:,} CLP"
                lines.append(f"    Entrada: {fee}")
            if place.best_season:
                lines.append(f"    Mejor temporada: {place.best_season}")
            if place.long_description:
                # Limitar para no inflar el prompt
                desc = place.long_description.strip()
                if len(desc) > 400:
                    desc = desc[:400] + "..."
                lines.append(f"    Descripción: {desc}")
            if place.extra_data:
                # Pasar primeras claves del extra_data sintéticamente
                keys = list(place.extra_data.keys())[:5]
                if keys:
                    lines.append(f"    Datos extra disponibles: {', '.join(keys)}")
            if place.did_you_know:
                lines.append(f"    Dato curioso: {place.did_you_know[:200]}")

    lines.append("")
    lines.append("=== INSTRUCCIÓN ===")
    lines.append(
        "Genera la narrativa editorial siguiendo el formato JSON especificado en el system prompt."
    )
    return "\n".join(lines)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _parse_json(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parsea el primer objeto JSON en `text` (tolera trailing content vía raw_decode)."""
    if not text:
        return None, "respuesta vacía"
    candidate = text.strip()
    fence_match = _JSON_FENCE_RE.search(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()
    if not candidate.startswith("{"):
        first = candidate.find("{")
        if first == -1:
            return None, "no se encontró objeto JSON"
        candidate = candidate[first:]
    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(candidate)
        if not isinstance(obj, dict):
            return None, f"objeto JSON no es dict (got {type(obj).__name__})"
        return obj, ""
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}"


def _normalize(parsed: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "circuit_long_description": str(parsed.get("circuit_long_description") or "").strip(),
        "day_summaries": {},
    }
    raw_summaries = parsed.get("day_summaries") or {}
    if isinstance(raw_summaries, dict):
        for k, v in raw_summaries.items():
            out["day_summaries"][str(k)] = str(v or "").strip()
    return out
