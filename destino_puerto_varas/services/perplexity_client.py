"""Cliente HTTP para Perplexity API.

Perplexity es búsqueda web sintetizada por LLM con citas — ideal para enriquecer
Places con info turística (altura, infraestructura, fauna, accesos, etc.).

Endpoint usado: POST {base_url}/chat/completions (OpenAI-compatible).
Modelo recomendado: 'sonar-pro' (con búsqueda web activa + síntesis).

Uso:
    from destino_puerto_varas.services.perplexity_client import query_perplexity
    result = query_perplexity(
        system="...",
        user="Información turística de Volcán Osorno...",
    )
    if result["ok"]:
        print(result["text"])
        print(result["citations"])  # lista de URLs
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
class PerplexityResult:
    ok: bool = False
    text: str = ""
    citations: list[str] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "text": self.text,
            "citations": self.citations,
            "raw_response": self.raw_response,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


def is_perplexity_configured() -> bool:
    return bool(getattr(settings, "PERPLEXITY_API_KEY", "").strip())


def query_perplexity(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    timeout: int | None = None,
) -> PerplexityResult:
    """Llama a Perplexity y retorna texto + citas.

    Temperature baja (0.2) por defecto: queremos hechos verificables, no creatividad.
    """
    api_key = getattr(settings, "PERPLEXITY_API_KEY", "").strip()
    base_url = getattr(settings, "PERPLEXITY_BASE_URL", "https://api.perplexity.ai")
    default_model = getattr(settings, "PERPLEXITY_MODEL", "sonar-pro")
    default_timeout = getattr(settings, "PERPLEXITY_TIMEOUT_SECONDS", 60)

    result = PerplexityResult(model=model or default_model)

    if not api_key:
        result.error = "PERPLEXITY_API_KEY no configurada"
        return result

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": result.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
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
    try:
        result.text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        result.error = "estructura de respuesta inesperada"
        return result

    # Perplexity devuelve citas en data["citations"] (lista de URLs)
    result.citations = data.get("citations") or []

    usage = data.get("usage") or {}
    result.input_tokens = int(usage.get("prompt_tokens") or 0)
    result.output_tokens = int(usage.get("completion_tokens") or 0)
    result.ok = True
    return result
