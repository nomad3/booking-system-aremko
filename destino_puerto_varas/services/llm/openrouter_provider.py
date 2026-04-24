"""Cliente OpenRouter — usa el SDK OpenAI por compatibilidad de protocolo.

Siempre retorna LLMResult; nunca lanza excepción hacia arriba. Eso simplifica el fallback.
"""

import logging
import time

from django.conf import settings

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)


class LLMResult:
    """Resultado de una llamada al LLM."""

    def __init__(self, text, model, input_tokens, output_tokens, latency_ms, error=""):
        self.text = text
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.error = error

    @property
    def ok(self) -> bool:
        return not self.error


class OpenRouterProvider:
    """Cliente OpenRouter usando el SDK OpenAI por compatibilidad de protocolo."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.default_model = settings.DPV_LLM_MODEL
        self.max_tokens = settings.DPV_LLM_MAX_TOKENS
        self.temperature = settings.DPV_LLM_TEMPERATURE
        self.timeout = settings.DPV_LLM_TIMEOUT_SECONDS
        self._client = None

    def _get_client(self):
        if not self.api_key:
            return None
        if self._client is None:
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
    ) -> LLMResult:
        """Genera respuesta. Siempre devuelve LLMResult (nunca lanza hacia arriba)."""
        model_effective = model or self.default_model

        if not self.api_key:
            return LLMResult(
                "", model_effective, 0, 0, 0,
                error="OPENROUTER_API_KEY no configurada",
            )

        client = self._get_client()
        if not client:
            return LLMResult(
                "", model_effective, 0, 0, 0,
                error="Cliente OpenRouter no inicializable",
            )

        start = time.monotonic()
        try:
            resp = client.chat.completions.create(
                model=model_effective,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                extra_headers={
                    "HTTP-Referer": settings.DPV_LLM_SITE_URL,
                    "X-Title": settings.DPV_LLM_SITE_NAME,
                },
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            choice = resp.choices[0]
            text = (choice.message.content or "").strip()
            usage = resp.usage
            return LLMResult(
                text=text,
                model=model_effective,
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                latency_ms=elapsed_ms,
            )
        except APITimeoutError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning("OpenRouter timeout: %s", e)
            return LLMResult("", model_effective, 0, 0, elapsed_ms,
                             error=f"timeout: {str(e)[:150]}")
        except RateLimitError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning("OpenRouter rate limit: %s", e)
            return LLMResult("", model_effective, 0, 0, elapsed_ms,
                             error=f"rate_limit: {str(e)[:150]}")
        except APIError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("OpenRouter APIError: %s", e)
            return LLMResult("", model_effective, 0, 0, elapsed_ms,
                             error=f"api_error: {str(e)[:150]}")
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("OpenRouter unexpected error: %s", e)
            return LLMResult("", model_effective, 0, 0, elapsed_ms,
                             error=f"unexpected: {str(e)[:150]}")
