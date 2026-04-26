"""DPV CMS-IA · Form 2 (Fase A): composición de Circuit con IA.

A diferencia de circuit_narrative_service (que solo redacta narrativa para un
Circuit ya armado), este servicio arma el circuito completo desde una idea
libre del usuario.

Flujo:
    1. compose_circuit_from_idea(idea, ...) → lee catálogo de Places publicados,
       llama al LLM con la idea + catálogo + reglas, retorna CircuitCompositionDraft.
    2. apply_composition(draft) → crea Circuit + CircuitDay + CircuitPlace en DB.

Reglas duras:
    - Solo se proponen Places con published=True. La IA NO inventa lugares.
    - Si la IA detecta que el catálogo no alcanza, lo reporta en
      proposed_data.gaps_detected (no bloquea, solo informa).
    - Los anchor_places del usuario deben aparecer obligatoriamente en la propuesta.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from ..enums import BlockType, InterestType, ProfileType
from ..models import (
    Circuit,
    CircuitCompositionDraft,
    CircuitDay,
    CircuitPlace,
    DurationCase,
    Place,
)
from .llm.openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres un editor de circuitos turísticos para Puerto Varas y la \
región de Los Lagos (Chile). Tu trabajo es transformar la idea libre del usuario \
en un circuito coherente seleccionando paradas DEL CATÁLOGO QUE TE DOY.

Reglas no negociables:
1. Solo puedes usar Places del catálogo. NO inventes lugares.
2. Cada parada debe ser referenciada por su `place_id` exacto del catálogo.
3. Respeta la duración pedida: si son 2 días/1 noche, devuelve exactamente 2 días.
4. Si el usuario dio anchor_place_ids, esos lugares DEBEN aparecer en el circuito.
5. Si el catálogo no tiene lo que el usuario pide (p.ej. "ruta de cervecerías" pero no \
   hay Places de tipo CAFE/RESTAURANT), reporta el gap en `gaps_detected` pero igual \
   propone el mejor circuito posible con lo que hay.
6. No mezcles paradas geográficamente incompatibles (no pongas Frutillar y Petrohué en \
   la misma mañana sin transición).
7. Marca como `is_main_stop: true` la parada más representativa de cada día (1 sola).
8. Decide los flags booleanos según las paradas elegidas, no según la idea original.

Estructura de salida (JSON estricto, sin texto antes ni después):

{
  "name": "Nombre evocador del circuito (max 200 chars)",
  "slug": "slug-en-minusculas-con-guiones",
  "short_description": "1-2 oraciones gancho (max 240 chars)",
  "long_description": "Narrativa editorial 3-5 párrafos — tono cercano, evocador, \
  español de Chile. Solo afirma datos del catálogo.",
  "primary_interest": "NATURE | GASTRONOMY | ADVENTURE | RELAX_ROMANTIC | MIXED",
  "recommended_profile": "COUPLE | FAMILY | FRIENDS | SOLO",
  "is_romantic": false,
  "is_family_friendly": false,
  "is_adventure": false,
  "is_rain_friendly": false,
  "is_premium": false,
  "is_nature": false,
  "is_culture": false,
  "is_gastronomy": false,
  "days": [
    {
      "day_number": 1,
      "title": "Mañana de mirador y saltos",
      "block_type": "ARRIVAL | HALF_DAY | FULL_DAY | DEPARTURE | AREMKO_MOMENT",
      "summary": "Resumen del día (2-4 oraciones)",
      "stops": [
        {"place_id": 12, "visit_order": 1, "is_main_stop": false},
        {"place_id":  7, "visit_order": 2, "is_main_stop": true}
      ]
    }
  ],
  "gaps_detected": [
    "Texto libre describiendo qué tipo de Place falta en el catálogo y por qué \
    convendría agregarlo (ej: 'Falta un café con vista entre Frutillar y Pto Varas')."
  ],
  "rationale": "Por qué elegiste estas paradas y este orden (2-4 oraciones)."
}

Reglas de tono:
- Cercano, evocador, sensorial — sin clichés.
- Español de Chile, sin modismos foráneos.
- No prometas servicios que no estén en el catálogo (no digas 'almuerzo incluido' \
  si no hay un RESTAURANT en la parada).
"""


def is_composer_available() -> bool:
    """True si OpenRouter está configurado para componer circuitos."""
    provider = OpenRouterProvider()
    return bool(provider.api_key)


def compose_circuit_from_idea(
    *,
    user_idea: str,
    duration_case: DurationCase | None = None,
    primary_interest: str = "",
    recommended_profile: str = "",
    anchor_place_ids: list[int] | None = None,
    save: bool = True,
    model: str | None = None,
) -> CircuitCompositionDraft | None:
    """Compone un borrador de Circuit usando el catálogo de Places publicados.

    Retorna CircuitCompositionDraft o None si OpenRouter no está disponible.
    """
    provider = OpenRouterProvider()
    if not provider.api_key:
        logger.warning("compose_circuit_from_idea: OPENROUTER_API_KEY no configurada")
        return None

    anchor_place_ids = list(anchor_place_ids or [])

    catalog = _build_catalog(primary_interest=primary_interest)
    user_prompt = _build_user_prompt(
        user_idea=user_idea,
        duration_case=duration_case,
        primary_interest=primary_interest,
        recommended_profile=recommended_profile,
        anchor_place_ids=anchor_place_ids,
        catalog=catalog,
    )

    result = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=3500,
        temperature=0.5,
    )

    base_kwargs = {
        "user_idea": user_idea,
        "duration_case": duration_case,
        "primary_interest": primary_interest or "",
        "recommended_profile": recommended_profile or "",
        "anchor_place_ids": anchor_place_ids,
        "llm_model": result.model,
        "llm_input_tokens": result.input_tokens,
        "llm_output_tokens": result.output_tokens,
        "llm_latency_ms": result.latency_ms,
    }

    if not result.ok:
        draft = CircuitCompositionDraft(
            status=CircuitCompositionDraft.STATUS_REJECTED,
            proposed_data={},
            review_notes=f"[auto] LLM falló: {result.error}",
            **base_kwargs,
        )
        if save:
            draft.save()
        return draft

    parsed, parse_error = _parse_json(result.text)
    if not parsed:
        draft = CircuitCompositionDraft(
            status=CircuitCompositionDraft.STATUS_REJECTED,
            proposed_data={"raw_text": result.text},
            review_notes=f"[auto] No pude parsear JSON: {parse_error}",
            **base_kwargs,
        )
        if save:
            draft.save()
        return draft

    proposed = _normalize(parsed)
    proposed = _validate_against_catalog(proposed, anchor_place_ids=anchor_place_ids)

    draft = CircuitCompositionDraft(
        status=CircuitCompositionDraft.STATUS_DRAFT,
        proposed_data=proposed,
        review_notes="",
        **base_kwargs,
    )
    if save:
        draft.save()
    return draft


@transaction.atomic
def apply_composition(
    draft: CircuitCompositionDraft,
    *,
    reviewer: str = "",
    publish: bool = False,
) -> Circuit | None:
    """Crea el Circuit + CircuitDay + CircuitPlace desde proposed_data.

    Retorna el Circuit creado, o None si el draft no aplica.
    """
    if draft.status not in (
        CircuitCompositionDraft.STATUS_DRAFT,
        CircuitCompositionDraft.STATUS_APPROVED,
    ):
        logger.warning(
            "apply_composition: draft #%s no aplicable (status=%s)",
            draft.id,
            draft.status,
        )
        return None

    proposed = draft.proposed_data or {}
    if not proposed.get("days"):
        logger.warning("apply_composition: draft #%s sin días", draft.id)
        return None

    # Resolver duration_case (puede venir del form o del proposed_data)
    duration_case = draft.duration_case
    if not duration_case:
        code = proposed.get("duration_case_code") or ""
        if code:
            duration_case = DurationCase.objects.filter(code=code).first()
    if not duration_case:
        # Fallback: cualquier DurationCase activo
        duration_case = DurationCase.objects.filter(is_active=True).order_by("days").first()
    if not duration_case:
        logger.error("apply_composition: no hay DurationCase válido")
        return None

    # Calcular slug y number únicos
    name = (proposed.get("name") or "Circuito sin nombre").strip()[:200]
    base_slug = (proposed.get("slug") or slugify(name) or "circuito").strip()[:200]
    slug = base_slug
    n = 2
    while Circuit.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1
    next_number = (Circuit.objects.order_by("-number").values_list("number", flat=True).first() or 0) + 1

    circuit = Circuit.objects.create(
        number=next_number,
        name=name,
        slug=slug,
        short_description=(proposed.get("short_description") or "")[:255],
        long_description=proposed.get("long_description") or "",
        duration_case=duration_case,
        primary_interest=_safe_choice(
            proposed.get("primary_interest"),
            InterestType.values,
            InterestType.MIXED,
        ),
        recommended_profile=_safe_choice(
            proposed.get("recommended_profile"),
            ProfileType.values,
            "",
        ),
        is_romantic=bool(proposed.get("is_romantic")),
        is_family_friendly=bool(proposed.get("is_family_friendly")),
        is_adventure=bool(proposed.get("is_adventure")),
        is_rain_friendly=bool(proposed.get("is_rain_friendly")),
        is_premium=bool(proposed.get("is_premium")),
        is_nature=bool(proposed.get("is_nature")),
        is_culture=bool(proposed.get("is_culture")),
        is_gastronomy=bool(proposed.get("is_gastronomy")),
        published=publish,
    )

    for day_idx, day_data in enumerate(proposed.get("days") or [], start=1):
        day_number = int(day_data.get("day_number") or day_idx)
        day = CircuitDay.objects.create(
            circuit=circuit,
            day_number=day_number,
            title=(day_data.get("title") or f"Día {day_number}")[:200],
            block_type=_safe_choice(
                day_data.get("block_type"),
                BlockType.values,
                BlockType.FULL_DAY,
            ),
            summary=day_data.get("summary") or "",
            sort_order=day_idx,
        )
        for stop_idx, stop in enumerate(day_data.get("stops") or [], start=1):
            place_id = stop.get("place_id")
            if not place_id:
                continue
            try:
                place = Place.objects.get(pk=place_id, published=True)
            except Place.DoesNotExist:
                logger.warning(
                    "apply_composition: place_id=%s no existe o no está publicado, omitido",
                    place_id,
                )
                continue
            CircuitPlace.objects.create(
                circuit_day=day,
                place=place,
                visit_order=int(stop.get("visit_order") or stop_idx),
                is_main_stop=bool(stop.get("is_main_stop")),
            )

    # Marcar el signature de paradas (para que la narrativa se considere vigente)
    circuit.places_signature = circuit.compute_places_signature()
    circuit.last_narrative_at = timezone.now() if proposed.get("long_description") else None
    circuit.save(update_fields=["places_signature", "last_narrative_at", "updated_at"])

    # Cerrar el draft
    draft.status = CircuitCompositionDraft.STATUS_APPLIED
    draft.created_circuit = circuit
    draft.applied_at = timezone.now()
    if reviewer and not draft.reviewed_by:
        draft.reviewed_by = reviewer
    if not draft.reviewed_at:
        draft.reviewed_at = timezone.now()
    draft.save()

    return circuit


# ─── Helpers privados ───


def _build_catalog(*, primary_interest: str = "") -> list[dict[str, Any]]:
    """Reúne los Places publicados con campos compactos para enviar al LLM."""
    qs = Place.objects.filter(published=True).order_by("name")
    catalog = []
    for p in qs:
        catalog.append({
            "place_id": p.id,
            "name": p.name,
            "type": p.place_type,
            "partnership": p.partnership_level,
            "location": p.location_label or "",
            "short": (p.short_description or "")[:180],
            "distance_pv_km": float(p.distance_from_pv_km) if p.distance_from_pv_km else None,
            "drive_time_pv_min": p.drive_time_from_pv_min or None,
            "is_rain_friendly": p.is_rain_friendly,
            "is_romantic": p.is_romantic,
            "is_family_friendly": p.is_family_friendly,
            "is_adventure_related": p.is_adventure_related,
            "has_food_service": p.has_food_service,
            "has_parking": p.has_parking,
            "entry_fee_clp": p.entry_fee_clp,
        })
    return catalog


def _build_user_prompt(
    *,
    user_idea: str,
    duration_case: DurationCase | None,
    primary_interest: str,
    recommended_profile: str,
    anchor_place_ids: list[int],
    catalog: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("=== IDEA DEL USUARIO ===")
    lines.append(user_idea.strip() or "(sin descripción)")
    lines.append("")

    lines.append("=== PARÁMETROS ===")
    if duration_case:
        lines.append(
            f"Duración pedida: {duration_case.days} día(s) / "
            f"{duration_case.nights} noche(s) — {duration_case.name} "
            f"(code={duration_case.code})"
        )
    else:
        lines.append("Duración pedida: NO ESPECIFICADA — usa tu criterio (1 día por defecto).")
    if primary_interest:
        lines.append(f"Interés primario pedido: {primary_interest}")
    if recommended_profile:
        lines.append(f"Perfil recomendado pedido: {recommended_profile}")
    if anchor_place_ids:
        anchors = Place.objects.filter(id__in=anchor_place_ids, published=True)
        if anchors.exists():
            lines.append(
                "Anchor Places (DEBEN aparecer en el circuito): "
                + ", ".join(f"#{p.id} {p.name}" for p in anchors)
            )
    lines.append("")

    lines.append("=== CATÁLOGO DE PLACES PUBLICADOS ===")
    if not catalog:
        lines.append("(catálogo vacío — no hay Places publicados)")
    else:
        lines.append(f"Total: {len(catalog)} lugar(es). Solo puedes usar estos place_id.")
        lines.append(json.dumps(catalog, ensure_ascii=False, indent=2))
    lines.append("")

    lines.append("=== INSTRUCCIÓN ===")
    lines.append(
        "Devuelve el circuito en el formato JSON especificado en el system prompt. "
        "No incluyas texto antes ni después del JSON."
    )
    return "\n".join(lines)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _parse_json(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text:
        return None, "respuesta vacía"
    candidate = text.strip()
    fence = _JSON_FENCE_RE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()
    if not candidate.startswith("{"):
        first = candidate.find("{")
        if first == -1:
            return None, "no se encontró objeto JSON"
        candidate = candidate[first:]
    try:
        obj, _end = json.JSONDecoder().raw_decode(candidate)
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}"
    if not isinstance(obj, dict):
        return None, f"objeto JSON no es dict (got {type(obj).__name__})"
    return obj, ""


def _normalize(parsed: dict[str, Any]) -> dict[str, Any]:
    """Coacciona tipos sin mutar el original."""
    out: dict[str, Any] = {
        "name": str(parsed.get("name") or "").strip()[:200],
        "slug": slugify(str(parsed.get("slug") or parsed.get("name") or ""))[:200],
        "short_description": str(parsed.get("short_description") or "").strip()[:255],
        "long_description": str(parsed.get("long_description") or "").strip(),
        "primary_interest": str(parsed.get("primary_interest") or "").strip(),
        "recommended_profile": str(parsed.get("recommended_profile") or "").strip(),
        "is_romantic": bool(parsed.get("is_romantic")),
        "is_family_friendly": bool(parsed.get("is_family_friendly")),
        "is_adventure": bool(parsed.get("is_adventure")),
        "is_rain_friendly": bool(parsed.get("is_rain_friendly")),
        "is_premium": bool(parsed.get("is_premium")),
        "is_nature": bool(parsed.get("is_nature")),
        "is_culture": bool(parsed.get("is_culture")),
        "is_gastronomy": bool(parsed.get("is_gastronomy")),
        "days": [],
        "gaps_detected": [],
        "rationale": str(parsed.get("rationale") or "").strip(),
    }

    raw_days = parsed.get("days") or []
    if isinstance(raw_days, list):
        for day in raw_days:
            if not isinstance(day, dict):
                continue
            stops_out = []
            for stop in (day.get("stops") or []):
                if not isinstance(stop, dict):
                    continue
                try:
                    pid = int(stop.get("place_id"))
                except (TypeError, ValueError):
                    continue
                stops_out.append({
                    "place_id": pid,
                    "visit_order": int(stop.get("visit_order") or len(stops_out) + 1),
                    "is_main_stop": bool(stop.get("is_main_stop")),
                })
            out["days"].append({
                "day_number": int(day.get("day_number") or len(out["days"]) + 1),
                "title": str(day.get("title") or "").strip()[:200],
                "block_type": str(day.get("block_type") or "").strip(),
                "summary": str(day.get("summary") or "").strip(),
                "stops": stops_out,
            })

    gaps = parsed.get("gaps_detected") or []
    if isinstance(gaps, list):
        out["gaps_detected"] = [str(g).strip() for g in gaps if str(g).strip()]

    return out


def _validate_against_catalog(
    proposed: dict[str, Any],
    *,
    anchor_place_ids: list[int],
) -> dict[str, Any]:
    """Revisa que todos los place_id existan y estén publicados.

    - place_ids inválidos → se eliminan de stops y se anota en validation_warnings.
    - anchor_place_ids ausentes → se anotan en validation_warnings.
    """
    warnings: list[str] = []
    used_ids: set[int] = set()

    valid_ids = set(
        Place.objects.filter(published=True).values_list("id", flat=True)
    )

    for day in proposed.get("days") or []:
        cleaned_stops = []
        for stop in day.get("stops") or []:
            pid = stop.get("place_id")
            if pid in valid_ids:
                cleaned_stops.append(stop)
                used_ids.add(pid)
            else:
                warnings.append(
                    f"place_id={pid} no existe o no está publicado — parada omitida."
                )
        day["stops"] = cleaned_stops

    missing_anchors = set(anchor_place_ids) - used_ids
    if missing_anchors:
        warnings.append(
            "La IA no incluyó estos anchor places: "
            + ", ".join(str(x) for x in sorted(missing_anchors))
        )

    # Auto-inferencia de categorías multi-valor a partir del place_type real de
    # las paradas. La IA puede proponer flags, pero el catálogo manda: si una
    # parada es THEATER/MUSEUM, el circuito ES de cultura aunque el LLM no lo marque.
    if used_ids:
        types_in_circuit = set(
            Place.objects.filter(id__in=used_ids).values_list("place_type", flat=True)
        )
        proposed["is_culture"] = bool(
            proposed.get("is_culture") or types_in_circuit & {"THEATER", "MUSEUM", "CHURCH", "CULTURAL_CENTER"}
        )
        proposed["is_gastronomy"] = bool(
            proposed.get("is_gastronomy") or types_in_circuit & {"RESTAURANT", "CAFE"}
        )
        proposed["is_nature"] = bool(
            proposed.get("is_nature") or types_in_circuit & {"PARK", "VIEWPOINT", "ATTRACTION"}
        )

    proposed["validation_warnings"] = warnings
    return proposed


def _safe_choice(value: Any, valid_values: list[str], default: str) -> str:
    """Si value es un choice válido, lo retorna; si no, retorna default."""
    if value and str(value) in valid_values:
        return str(value)
    return default


# ─── Modo Manual: aplicar branding + paradas elegidas por el usuario ───


@transaction.atomic
def apply_manual_composition(
    draft: CircuitCompositionDraft,
    *,
    chosen_name_index: int,
    reviewer: str = "",
    publish: bool = False,
) -> Circuit | None:
    """Aplica un draft generado por propose_circuit_branding (modo manual).

    `draft.anchor_place_ids` contiene la lista ordenada de Places elegidos.
    `draft.proposed_data["name_options"]` tiene las 3 alternativas.
    `chosen_name_index` (0,1,2) es la elegida por el usuario.

    Auto-distribuye las paradas en N días donde N = duration_case.days.
    """
    if draft.status not in (
        CircuitCompositionDraft.STATUS_DRAFT,
        CircuitCompositionDraft.STATUS_APPROVED,
    ):
        logger.warning(
            "apply_manual_composition: draft #%s no aplicable (status=%s)",
            draft.id,
            draft.status,
        )
        return None

    proposed = draft.proposed_data or {}
    options = proposed.get("name_options") or []
    if not options:
        logger.warning("apply_manual_composition: draft #%s sin name_options", draft.id)
        return None
    try:
        chosen = options[int(chosen_name_index)]
    except (IndexError, TypeError, ValueError):
        logger.warning(
            "apply_manual_composition: índice %s inválido (options=%d)",
            chosen_name_index,
            len(options),
        )
        return None

    place_ids = draft.anchor_place_ids or []
    if not place_ids:
        logger.warning("apply_manual_composition: draft #%s sin paradas", draft.id)
        return None

    duration_case = draft.duration_case
    if not duration_case:
        logger.error("apply_manual_composition: draft #%s sin duration_case", draft.id)
        return None

    # Resolver Places preservando el orden y filtrando por publicado
    places_by_id = {p.id: p for p in Place.objects.filter(id__in=place_ids, published=True)}
    places_in_order = [places_by_id[pid] for pid in place_ids if pid in places_by_id]
    if not places_in_order:
        logger.warning("apply_manual_composition: ninguna parada está publicada")
        return None

    # Auto-distribuir paradas en N días
    n_days = max(1, duration_case.days)
    distribution = _distribute_stops_across_days(places_in_order, n_days)

    # Slug + number únicos
    name = chosen.get("name", "Circuito sin nombre")[:200]
    base_slug = slugify(chosen.get("slug") or name)[:200] or "circuito"
    slug = base_slug
    n = 2
    while Circuit.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1
    next_number = (Circuit.objects.order_by("-number").values_list("number", flat=True).first() or 0) + 1

    circuit = Circuit.objects.create(
        number=next_number,
        name=name,
        slug=slug,
        short_description=(chosen.get("short_description") or "")[:255],
        long_description=(proposed.get("long_description") or "").strip(),
        duration_case=duration_case,
        primary_interest=_safe_choice(
            draft.primary_interest,
            InterestType.values,
            InterestType.MIXED,
        ),
        recommended_profile=_safe_choice(
            draft.recommended_profile,
            ProfileType.values,
            "",
        ),
        is_romantic=bool(proposed.get("is_romantic")),
        is_family_friendly=bool(proposed.get("is_family_friendly")),
        is_adventure=bool(proposed.get("is_adventure")),
        is_rain_friendly=bool(proposed.get("is_rain_friendly")),
        is_premium=bool(proposed.get("is_premium")),
        is_nature=bool(proposed.get("is_nature")),
        is_culture=bool(proposed.get("is_culture")),
        is_gastronomy=bool(proposed.get("is_gastronomy")),
        published=publish,
    )

    day_summaries = proposed.get("day_summaries") or {}
    for day_idx, places_for_day in enumerate(distribution, start=1):
        block = BlockType.FULL_DAY
        if n_days == 1:
            block = BlockType.HALF_DAY if duration_case.nights == 0 and len(places_for_day) <= 2 else BlockType.FULL_DAY
        day = CircuitDay.objects.create(
            circuit=circuit,
            day_number=day_idx,
            title=f"Día {day_idx}",
            block_type=block,
            summary=str(day_summaries.get(str(day_idx)) or "").strip(),
            sort_order=day_idx,
        )
        for stop_idx, place in enumerate(places_for_day, start=1):
            CircuitPlace.objects.create(
                circuit_day=day,
                place=place,
                visit_order=stop_idx,
                is_main_stop=(stop_idx == 1 and len(places_for_day) > 1),
            )

    circuit.places_signature = circuit.compute_places_signature()
    if (proposed.get("long_description") or "").strip():
        circuit.last_narrative_at = timezone.now()
    circuit.save(update_fields=["places_signature", "last_narrative_at", "updated_at"])

    draft.status = CircuitCompositionDraft.STATUS_APPLIED
    draft.created_circuit = circuit
    draft.applied_at = timezone.now()
    if reviewer and not draft.reviewed_by:
        draft.reviewed_by = reviewer
    if not draft.reviewed_at:
        draft.reviewed_at = timezone.now()
    draft.proposed_data = {**proposed, "chosen_name_index": int(chosen_name_index)}
    draft.save()
    return circuit


def _distribute_stops_across_days(places: list, n_days: int) -> list[list]:
    """Reparte `places` en `n_days` listas conservando el orden.

    Ej: 7 places en 3 días → [3, 2, 2].
    """
    if n_days <= 1:
        return [list(places)]
    total = len(places)
    base = total // n_days
    extra = total % n_days
    out: list[list] = []
    cursor = 0
    for i in range(n_days):
        size = base + (1 if i < extra else 0)
        out.append(list(places[cursor : cursor + size]))
        cursor += size
    return out
