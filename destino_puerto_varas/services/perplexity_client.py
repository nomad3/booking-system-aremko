"""Cliente HTTP para Perplexity Search API.

Endpoint: POST {base_url}/search
Body: {"query": str, "max_results": int, "max_tokens_per_page": int}

Devuelve resultados de búsqueda web (URLs + snippets), NO síntesis. Para sintetizar
en JSON estructurado usamos OpenRouter (Claude) en place_enrichment_service.py.

Esta separación (search → synthesis) es deliberada:
  - Perplexity Search es muy bueno encontrando páginas relevantes.
  - Claude/Haiku via OpenRouter es bueno extrayendo y estructurando datos.
  - Cada uno hace lo suyo; debugging y costos quedan separados.

Uso:
    from destino_puerto_varas.services.perplexity_client import search_perplexity
    result = search_perplexity("Volcán Osorno altura turismo Puerto Varas")
    if result.ok:
        for r in result.results:
            print(r["title"], r["url"], r["snippet"][:100])
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class PerplexitySearchResult:
    ok: bool = False
    results: list[dict[str, Any]] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "results": self.results,
            "raw_response": self.raw_response,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


def is_perplexity_configured() -> bool:
    return bool(getattr(settings, "PERPLEXITY_API_KEY", "").strip())


def search_perplexity(
    query: str,
    *,
    max_results: int | None = None,
    max_tokens_per_page: int | None = None,
    timeout: int | None = None,
) -> PerplexitySearchResult:
    """Llama a Perplexity Search API y retorna lista de resultados normalizados.

    Cada resultado tiene shape: {"title": str, "url": str, "snippet": str}
    (algunos campos pueden venir vacíos según la respuesta del API).
    """
    api_key = getattr(settings, "PERPLEXITY_API_KEY", "").strip()
    base_url = getattr(settings, "PERPLEXITY_BASE_URL", "https://api.perplexity.ai")
    default_max_results = getattr(settings, "PERPLEXITY_SEARCH_MAX_RESULTS", 5)
    default_max_tokens = getattr(settings, "PERPLEXITY_SEARCH_MAX_TOKENS_PER_PAGE", 512)
    default_timeout = getattr(settings, "PERPLEXITY_TIMEOUT_SECONDS", 60)

    result = PerplexitySearchResult()

    if not api_key:
        result.error = "PERPLEXITY_API_KEY no configurada"
        return result

    if not query or not query.strip():
        result.error = "query vacía"
        return result

    url = f"{base_url.rstrip('/')}/search"
    payload = {
        "query": query.strip(),
        "max_results": max_results or default_max_results,
        "max_tokens_per_page": max_tokens_per_page or default_max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start = time.monotonic()
    try:
        resp = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload),
            timeout=timeout or default_timeout,
        )
    except requests.Timeout:
        result.error = f"timeout tras {timeout or default_timeout}s"
        result.latency_ms = int((time.monotonic() - start) * 1000)
        return result
    except requests.RequestException as exc:
        result.error = f"network_error: {exc}"
        result.latency_ms = int((time.monotonic() - start) * 1000)
        return result

    result.latency_ms = int((time.monotonic() - start) * 1000)

    if resp.status_code >= 400:
        body_preview = resp.text[:300] if resp.text else "<sin body>"
        result.error = f"http_{resp.status_code}: {body_preview}"
        return result

    try:
        data = resp.json()
    except ValueError:
        result.error = "respuesta no-JSON"
        return result

    result.raw_response = data
    raw_results = (
        data.get("results")
        or data.get("search_results")
        or data.get("data")
        or []
    )
    if not isinstance(raw_results, list):
        result.error = f"estructura inesperada: results no es lista (got {type(raw_results).__name__})"
        return result

    normalized: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "title": str(item.get("title") or "").strip(),
            "url": str(item.get("url") or item.get("link") or "").strip(),
            "snippet": str(
                item.get("snippet")
                or item.get("content")
                or item.get("text")
                or ""
            ).strip(),
        })

    result.results = normalized
    result.ok = True
    return result
