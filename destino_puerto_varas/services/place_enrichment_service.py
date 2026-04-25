"""Servicio de enriquecimiento de Place vía Perplexity.

Flujo:
    1. enrich_place(place) → query Perplexity con prompt estructurado
    2. Parsea respuesta JSON
    3. Crea PlaceEnrichmentDraft con status='draft' (pendiente revisión humana)
    4. Admin revisa, edita, aprueba → apply_draft(draft) la vuelca al Place

NO modifica el Place directamente — siempre pasa por el draft. Razón: requisito
explícito de revisión humana antes de publicar.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.utils import timezone

from ..models import Place, PlaceEnrichmentDraft, PlacePhoto
from .perplexity_client import is_perplexity_configured, query_perplexity

logger = logging.getLogger(__name__)


# Campos estructurados que la IA debe intentar llenar.
STRUCTURED_FIELDS = [
    "elevation_m",
    "year_established",
    "has_parking",
    "has_restrooms",
    "has_conaf_office",
    "has_food_service",
    "entry_fee_clp",
    "best_season",
    "accessibility_notes",
    "distance_from_pv_km",
    "drive_time_from_pv_min",
]

INT_FIELDS = {
    "elevation_m",
    "year_established",
    "entry_fee_clp",
    "drive_time_from_pv_min",
}
BOOL_FIELDS = {
    "has_parking",
    "has_restrooms",
    "has_conaf_office",
    "has_food_service",
}
FLOAT_FIELDS = {"distance_from_pv_km"}
STR_FIELDS = {"best_season", "accessibility_notes"}


SYSTEM_PROMPT = """Eres un asistente experto en turismo en la región de Los Lagos, Chile, \
especialmente Puerto Varas y alrededores (Frutillar, Ensenada, Petrohué, Cochamó, Puelo, \
Osorno, Calbuco, Llanquihue, etc.).

Tu tarea: dado el nombre de un lugar/atracción turística, recopilar información útil para \
turistas y devolverla en JSON estricto. Solo usa información que puedas verificar en \
fuentes web (Wikipedia, sitios oficiales como CONAF, sernatur.cl, etc.). Si un dato no \
está disponible o no aplica, devuelve null (no inventes).

Formato de respuesta — DEVUELVE SOLO JSON, sin texto antes ni después, sin bloque \
markdown ```. Estructura exacta:

{
  "fields": {
    "elevation_m": <int|null>,
    "year_established": <int|null>,
    "has_parking": <true|false>,
    "has_restrooms": <true|false>,
    "has_conaf_office": <true|false>,
    "has_food_service": <true|false>,
    "entry_fee_clp": <int|null>,
    "best_season": "<string en español>",
    "accessibility_notes": "<string en español>",
    "distance_from_pv_km": <float|null>,
    "drive_time_from_pv_min": <int|null>
  },
  "long_description": "<texto editorial 250-400 palabras en español, tono inspiracional pero informativo, para mostrar al turista>",
  "extra_data": {
    "<clave temática en snake_case>": <valor o lista de strings>,
    "...": "..."
  },
  "photos": [
    {"url": "<URL directa a la imagen>", "caption": "<descripción breve>", "credit": "<atribución, ej: 'Wikimedia Commons, CC-BY-SA 4.0'>"}
  ]
}

Notas importantes:
- entry_fee_clp: usa 0 si la entrada es gratis, null si desconocido o no aplica.
- distance_from_pv_km y drive_time_from_pv_min: distancia/tiempo desde el centro de Puerto Varas.
- extra_data debe contener temas relevantes que enriquezcan la experiencia del turista. Ejemplos de claves: "fauna", "flora", "actividades_disponibles", "historia", "datos_curiosos", "como_llegar", "infraestructura_adicional". Lista mínimo 3 categorías.
- photos: provee 3-5 URLs directas a imágenes (jpg/png) preferiblemente de Wikimedia Commons o sitios con licencia abierta. Incluye atribución completa en credit.
- El JSON debe ser válido (comillas dobles, sin trailing commas).
"""


def is_enrichment_available() -> bool:
    return is_perplexity_configured()


def enrich_place(place: Place, *, save: bool = True) -> PlaceEnrichmentDraft | None:
    """Genera un PlaceEnrichmentDraft para `place` consultando Perplexity.

    Si `save=False`, retorna el draft sin persistir (útil para tests).
    Retorna None si Perplexity no está configurado o la llamada falló.
    """
    if not is_perplexity_configured():
        logger.warning("enrich_place llamado pero PERPLEXITY_API_KEY no está configurada")
        return None

    user_prompt = _build_user_prompt(place)

    pp_result = query_perplexity(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        temperature=0.2,
        max_tokens=2500,
    )

    if not pp_result.ok:
        logger.warning(
            "Perplexity falló para place_id=%s: %s",
            place.id,
            pp_result.error,
        )
        # Aún así creamos un draft con el error para auditoría
        draft = PlaceEnrichmentDraft(
            place=place,
            status=PlaceEnrichmentDraft.STATUS_REJECTED,
            proposed_data={},
            raw_search_response={"error": pp_result.error, **pp_result.to_dict()},
            search_provider="perplexity",
            llm_model=pp_result.model,
            llm_input_tokens=pp_result.input_tokens,
            llm_output_tokens=pp_result.output_tokens,
            llm_latency_ms=pp_result.latency_ms,
            review_notes=f"[auto] Perplexity falló: {pp_result.error}",
        )
        if save:
            draft.save()
        return draft

    parsed, parse_error = _parse_perplexity_json(pp_result.text)
    proposed = _normalize_proposed_data(parsed) if parsed else {}

    draft = PlaceEnrichmentDraft(
        place=place,
        status=PlaceEnrichmentDraft.STATUS_DRAFT,
        proposed_data=proposed,
        raw_search_response={
            "text": pp_result.text,
            "citations": pp_result.citations,
            "parse_error": parse_error,
        },
        search_provider="perplexity",
        llm_model=pp_result.model,
        llm_input_tokens=pp_result.input_tokens,
        llm_output_tokens=pp_result.output_tokens,
        llm_latency_ms=pp_result.latency_ms,
        review_notes=("[auto] Error parseando JSON: " + parse_error) if parse_error else "",
    )
    if save:
        draft.save()
    return draft


def apply_draft(draft: PlaceEnrichmentDraft, *, reviewer: str = "") -> bool:
    """Aplica un draft aprobado al Place real. Retorna True si tuvo éxito.

    - Solo aplica si status == APPROVED.
    - Setea last_enriched_at en el Place.
    - Crea PlacePhoto para cada foto propuesta (si no existe ya por source_url).
    - Marca el draft como APPLIED.
    """
    if draft.status != PlaceEnrichmentDraft.STATUS_APPROVED:
        logger.warning(
            "apply_draft: draft #%s no está aprobado (status=%s)",
            draft.id,
            draft.status,
        )
        return False

    place = draft.place
    proposed = draft.proposed_data or {}

    # ─── Campos estructurados ───
    fields = proposed.get("fields") or {}
    for key, value in fields.items():
        if key in STRUCTURED_FIELDS and value is not None:
            setattr(place, key, value)

    # ─── long_description (sólo si está vacío o el usuario lo permitió) ───
    long_desc = proposed.get("long_description")
    if long_desc:
        place.long_description = long_desc

    # ─── extra_data: merge no destructivo ───
    extra = proposed.get("extra_data") or {}
    if extra:
        merged = dict(place.extra_data or {})
        merged.update(extra)
        place.extra_data = merged

    place.last_enriched_at = timezone.now()
    place.save()

    # ─── Photos ───
    for idx, photo in enumerate(proposed.get("photos") or []):
        url = (photo.get("url") or "").strip()
        if not url:
            continue
        # Evita duplicar la misma URL
        if PlacePhoto.objects.filter(place=place, source_url=url).exists():
            continue
        PlacePhoto.objects.create(
            place=place,
            source_url=url,
            caption=(photo.get("caption") or "")[:255],
            credit=(photo.get("credit") or "")[:200],
            is_primary=(idx == 0 and not place.photos.filter(is_primary=True).exists()),
            order=idx,
        )

    draft.status = PlaceEnrichmentDraft.STATUS_APPLIED
    draft.applied_at = timezone.now()
    if reviewer and not draft.reviewed_by:
        draft.reviewed_by = reviewer
    if not draft.reviewed_at:
        draft.reviewed_at = timezone.now()
    draft.save()
    return True


# ─── Helpers privados ───


def _build_user_prompt(place: Place) -> str:
    parts = [f"Lugar: {place.name}"]
    if place.location_label:
        parts.append(f"Ubicación: {place.location_label}")
    if place.place_type:
        parts.append(f"Tipo: {place.get_place_type_display()}")
    if place.short_description:
        parts.append(f"Descripción breve actual: {place.short_description}")
    parts.append(
        "\nRecopila información completa siguiendo el formato JSON especificado. "
        "Considera que el usuario consultará desde Puerto Varas, Chile."
    )
    return "\n".join(parts)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _parse_perplexity_json(text: str) -> tuple[dict[str, Any] | None, str]:
    """Intenta parsear JSON de la respuesta. Tolera bloques markdown.

    Retorna (datos, error_str). datos=None si falla.
    """
    if not text:
        return None, "respuesta vacía"

    candidate = text.strip()

    # Si está envuelto en ```json ... ```, extraer
    fence_match = _JSON_FENCE_RE.search(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()

    # Si después de todo no empieza con {, intentar localizar el primer {
    if not candidate.startswith("{"):
        first_brace = candidate.find("{")
        if first_brace == -1:
            return None, "no se encontró objeto JSON"
        candidate = candidate[first_brace:]

    try:
        return json.loads(candidate), ""
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}"


def _normalize_proposed_data(parsed: dict[str, Any]) -> dict[str, Any]:
    """Coerce types para campos estructurados conocidos.

    LLMs a veces devuelven '2652m' como string en vez de int — limpiamos eso.
    """
    out: dict[str, Any] = {
        "fields": {},
        "long_description": str(parsed.get("long_description") or "").strip(),
        "extra_data": parsed.get("extra_data") or {},
        "photos": parsed.get("photos") or [],
    }

    raw_fields = parsed.get("fields") or {}
    for key in STRUCTURED_FIELDS:
        value = raw_fields.get(key)
        if value is None:
            out["fields"][key] = None
            continue
        if key in INT_FIELDS:
            out["fields"][key] = _coerce_int(value)
        elif key in BOOL_FIELDS:
            out["fields"][key] = bool(value)
        elif key in FLOAT_FIELDS:
            out["fields"][key] = _coerce_float(value)
        elif key in STR_FIELDS:
            out["fields"][key] = str(value).strip()
        else:
            out["fields"][key] = value

    return out


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    digits = re.search(r"-?\d+", s)
    return int(digits.group(0)) if digits else None


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", ".")
    match = re.search(r"-?\d+(\.\d+)?", s)
    return float(match.group(0)) if match else None
