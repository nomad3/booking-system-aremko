"""Servicio de enriquecimiento de Place (search → synthesis).

Patrón:
    1. Perplexity Search API → resultados web (URLs + snippets) sobre el lugar.
    2. OpenRouter (Claude/Haiku) → estructura los snippets en JSON estricto
       siguiendo el schema de PlaceEnrichmentDraft.
    3. Crea un PlaceEnrichmentDraft (status='draft') para revisión humana.
    4. apply_draft(draft) vuelca los datos al Place real.

Razón de la separación:
    - Perplexity Search es excelente encontrando páginas relevantes y devolviendo
      snippets curados, pero no devuelve JSON estructurado.
    - Claude/Haiku via OpenRouter es excelente extrayendo datos estructurados
      desde texto, pero no busca en la web.
    - Cada uno hace lo que mejor hace, debugging y costos quedan separados.

NUNCA modifica el Place directamente — siempre pasa por draft + revisión humana.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.utils import timezone

from ..models import Place, PlaceEnrichmentDraft, PlacePhoto
from .llm.openrouter_provider import OpenRouterProvider
from .perplexity_client import is_perplexity_configured, search_perplexity

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

Tu tarea: dado el nombre de un lugar/atracción turística + un bloque de RESULTADOS DE \
BÚSQUEDA WEB (snippets recuperados por Perplexity Search), extraer y estructurar la \
información en JSON estricto.

Reglas críticas:
- USA SOLO LO QUE APAREZCA EN LOS SNIPPETS. Si un dato no está, devuelve null. NO inventes \
  alturas, años, distancias, fees ni infraestructura.
- Si los snippets se contradicen, prefiere el dato más específico/oficial (Wikipedia, CONAF, \
  sernatur, sitios .cl institucionales).
- Para `extra_data` usa claves snake_case temáticas (fauna, flora, actividades_disponibles, \
  historia, datos_curiosos, como_llegar, infraestructura_adicional, etc.) con strings o \
  listas de strings — solo si esos temas aparecen en los snippets.
- Para `photos` lista 3-5 URLs **que aparezcan textualmente en los snippets**. Si no hay URLs \
  de imágenes en los snippets, devuelve array vacío. NO inventes URLs.

Formato de respuesta — DEVUELVE SOLO JSON, sin texto antes ni después, sin bloque \
markdown ```. Estructura exacta:

{
  "fields": {
    "elevation_m": <int|null>,
    "year_established": <int|null>,
    "has_parking": <true|false|null>,
    "has_restrooms": <true|false|null>,
    "has_conaf_office": <true|false|null>,
    "has_food_service": <true|false|null>,
    "entry_fee_clp": <int|null>,
    "best_season": "<string en español o vacío>",
    "accessibility_notes": "<string en español o vacío>",
    "distance_from_pv_km": <float|null>,
    "drive_time_from_pv_min": <int|null>
  },
  "long_description": "<texto editorial 250-400 palabras en español, tono inspiracional pero informativo, basado en los snippets>",
  "extra_data": {
    "<clave_snake_case>": <valor o lista de strings>
  },
  "photos": [
    {"url": "<URL>", "caption": "<descripción breve>", "credit": "<atribución si aparece>"}
  ]
}

Notas:
- entry_fee_clp: 0 si la entrada es explícitamente gratis, null si los snippets no lo mencionan.
- distance_from_pv_km y drive_time_from_pv_min: desde el centro de Puerto Varas.
- El JSON debe ser válido (comillas dobles, sin trailing commas).
"""


def is_enrichment_available() -> bool:
    """Necesitamos Perplexity (search) Y OpenRouter (synthesis)."""
    if not is_perplexity_configured():
        return False
    provider = OpenRouterProvider()
    return bool(provider.api_key)


def enrich_place(
    place: Place,
    *,
    save: bool = True,
    synthesis_model: str | None = None,
) -> PlaceEnrichmentDraft | None:
    """Genera un PlaceEnrichmentDraft para `place`.

    Pipeline:
        1. search_perplexity(query) → snippets web.
        2. OpenRouterProvider.generate(system, user_with_snippets) → JSON.
        3. Persist como PlaceEnrichmentDraft (status='draft').

    Si `save=False`, retorna el draft sin persistir.
    Retorna None si Perplexity u OpenRouter no están configurados.
    """
    if not is_perplexity_configured():
        logger.warning("enrich_place: PERPLEXITY_API_KEY no configurada")
        return None

    provider = OpenRouterProvider()
    if not provider.api_key:
        logger.warning("enrich_place: OPENROUTER_API_KEY no configurada")
        return None

    # ─── Paso 1: búsqueda web ───
    query = _build_search_query(place)
    pp_result = search_perplexity(query)

    if not pp_result.ok:
        logger.warning(
            "enrich_place: Perplexity Search falló para place_id=%s: %s",
            place.id,
            pp_result.error,
        )
        draft = PlaceEnrichmentDraft(
            place=place,
            status=PlaceEnrichmentDraft.STATUS_REJECTED,
            proposed_data={},
            raw_search_response={"perplexity_error": pp_result.error,
                                 "perplexity_raw": pp_result.to_dict()},
            search_provider="perplexity-search",
            llm_model="",
            review_notes=f"[auto] Perplexity Search falló: {pp_result.error}",
        )
        if save:
            draft.save()
        return draft

    if not pp_result.results:
        logger.warning("enrich_place: Perplexity devolvió 0 resultados para '%s'", query)
        draft = PlaceEnrichmentDraft(
            place=place,
            status=PlaceEnrichmentDraft.STATUS_REJECTED,
            proposed_data={},
            raw_search_response={"perplexity_results": [],
                                 "query": query},
            search_provider="perplexity-search",
            review_notes="[auto] Perplexity devolvió 0 resultados.",
        )
        if save:
            draft.save()
        return draft

    # ─── Paso 2: síntesis con OpenRouter ───
    user_prompt = _build_synthesis_prompt(place, pp_result.results)
    llm_result = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=synthesis_model,
        max_tokens=2500,
        temperature=0.2,  # bajo: queremos hechos, no creatividad
    )

    raw_audit = {
        "query": query,
        "perplexity_results": pp_result.results,
        "perplexity_latency_ms": pp_result.latency_ms,
        "synthesis_text": llm_result.text,
        "synthesis_error": llm_result.error,
    }

    if not llm_result.ok:
        draft = PlaceEnrichmentDraft(
            place=place,
            status=PlaceEnrichmentDraft.STATUS_REJECTED,
            proposed_data={},
            raw_search_response=raw_audit,
            search_provider="perplexity-search",
            llm_model=llm_result.model,
            llm_input_tokens=llm_result.input_tokens,
            llm_output_tokens=llm_result.output_tokens,
            llm_latency_ms=llm_result.latency_ms,
            review_notes=f"[auto] Síntesis OpenRouter falló: {llm_result.error}",
        )
        if save:
            draft.save()
        return draft

    parsed, parse_error = _parse_json(llm_result.text)
    proposed = _normalize_proposed_data(parsed) if parsed else {}
    raw_audit["parse_error"] = parse_error

    draft = PlaceEnrichmentDraft(
        place=place,
        status=PlaceEnrichmentDraft.STATUS_DRAFT,
        proposed_data=proposed,
        raw_search_response=raw_audit,
        search_provider="perplexity-search",
        llm_model=llm_result.model,
        llm_input_tokens=llm_result.input_tokens,
        llm_output_tokens=llm_result.output_tokens,
        llm_latency_ms=llm_result.latency_ms,
        review_notes=("[auto] Error parseando JSON: " + parse_error) if parse_error else "",
    )
    if save:
        draft.save()
    return draft


def apply_draft(draft: PlaceEnrichmentDraft, *, reviewer: str = "") -> bool:
    """Aplica un draft aprobado al Place real. Retorna True si tuvo éxito."""
    if draft.status != PlaceEnrichmentDraft.STATUS_APPROVED:
        logger.warning(
            "apply_draft: draft #%s no está aprobado (status=%s)",
            draft.id,
            draft.status,
        )
        return False

    place = draft.place
    proposed = draft.proposed_data or {}

    fields = proposed.get("fields") or {}
    for key, value in fields.items():
        if key in STRUCTURED_FIELDS and value is not None:
            setattr(place, key, value)

    long_desc = proposed.get("long_description")
    if long_desc:
        place.long_description = long_desc

    extra = proposed.get("extra_data") or {}
    if extra:
        merged = dict(place.extra_data or {})
        merged.update(extra)
        place.extra_data = merged

    place.last_enriched_at = timezone.now()
    place.save()

    for idx, photo in enumerate(proposed.get("photos") or []):
        url = (photo.get("url") or "").strip()
        if not url:
            continue
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


def _build_search_query(place: Place) -> str:
    """Arma el query para Perplexity Search.

    Combina nombre + ubicación + términos turísticos relevantes.
    """
    parts = [place.name]
    if place.location_label and place.location_label not in place.name:
        parts.append(place.location_label)
    parts.append("Puerto Varas Chile turismo altura infraestructura acceso")
    return " ".join(parts)


def _build_synthesis_prompt(place: Place, results: list[dict[str, Any]]) -> str:
    """Construye el user prompt para OpenRouter con snippets de Perplexity."""
    lines = [f"Lugar: {place.name}"]
    if place.location_label:
        lines.append(f"Ubicación: {place.location_label}")
    if place.place_type:
        lines.append(f"Tipo: {place.get_place_type_display()}")
    if place.short_description:
        lines.append(f"Descripción breve actual: {place.short_description}")

    lines.append("")
    lines.append("=== RESULTADOS DE BÚSQUEDA WEB (Perplexity) ===")
    for i, r in enumerate(results, 1):
        lines.append("")
        lines.append(f"[{i}] {r.get('title') or '(sin título)'}")
        lines.append(f"URL: {r.get('url') or ''}")
        snippet = (r.get("snippet") or "").strip()
        if snippet:
            lines.append(f"Snippet: {snippet}")

    lines.append("")
    lines.append("=== INSTRUCCIÓN ===")
    lines.append(
        "Extrae y estructura la información de los snippets en el formato JSON "
        "especificado en el system prompt. Recuerda: solo usa lo que aparece "
        "explícitamente en los snippets; si un dato no está, usa null."
    )
    return "\n".join(lines)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _parse_json(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parsea el primer objeto JSON en `text`.

    Tolerante a:
    - Bloques markdown (```json ... ```)
    - Texto antes del primer `{`
    - Contenido extra después del cierre del JSON (citas, comentarios, otro bloque)
      → usa JSONDecoder.raw_decode() en vez de json.loads().
    """
    if not text:
        return None, "respuesta vacía"

    candidate = text.strip()
    fence_match = _JSON_FENCE_RE.search(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()

    if not candidate.startswith("{"):
        first_brace = candidate.find("{")
        if first_brace == -1:
            return None, "no se encontró objeto JSON"
        candidate = candidate[first_brace:]

    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(candidate)
        if not isinstance(obj, dict):
            return None, f"objeto JSON no es dict (got {type(obj).__name__})"
        return obj, ""
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}"


def _normalize_proposed_data(parsed: dict[str, Any]) -> dict[str, Any]:
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
            # Permitimos null aquí (en el schema viejo era false default; ahora null=desconocido)
            if isinstance(value, bool):
                out["fields"][key] = value
            else:
                out["fields"][key] = None
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
