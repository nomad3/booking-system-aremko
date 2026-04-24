"""Cliente OpenRouter — usa el SDK OpenAI por compatibilidad de protocolo.

Siempre retorna LLMResult; nunca lanza excepción hacia arriba. Eso simplifica el fallback.
"""

import json
import logging
import time

from django.conf import settings

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)


class LLMResult:
    """Resultado de una llamada al LLM."""

    def __init__(
        self,
        text,
        model,
        input_tokens,
        output_tokens,
        latency_ms,
        error="",
        tool_calls_executed=None,
    ):
        self.text = text
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.error = error
        # Lista de dicts {"name": str, "arguments": dict, "result": dict} — auditoría
        self.tool_calls_executed = tool_calls_executed or []

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

    def generate_with_tools(
        self,
        messages: list,
        tools: list,
        tool_executor,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
        max_iterations: int = 3,
    ) -> LLMResult:
        """Genera respuesta con tool-calling. Loop hasta que el LLM retorna texto final.

        Args:
            messages: lista de dicts con formato OpenAI chat (role, content).
                      Debe incluir el system prompt como primer mensaje.
            tools: lista de tools en formato OpenAI function-calling.
            tool_executor: callable(name: str, arguments: dict) -> dict/str
                           que ejecuta la tool y retorna el resultado serializable.
            max_iterations: cuántas rondas de tool-use permitir antes de forzar respuesta.

        Retorna siempre LLMResult. Si hay error, .text es fallback vacío.
        """
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

        working_messages = list(messages)
        total_input_tokens = 0
        total_output_tokens = 0
        total_latency_ms = 0
        tool_calls_executed = []

        try:
            for iteration in range(max_iterations + 1):
                start = time.monotonic()
                is_last_iteration = iteration == max_iterations

                kwargs = {
                    "model": model_effective,
                    "messages": working_messages,
                    "max_tokens": max_tokens or self.max_tokens,
                    "temperature": temperature if temperature is not None else self.temperature,
                    "extra_headers": {
                        "HTTP-Referer": settings.DPV_LLM_SITE_URL,
                        "X-Title": settings.DPV_LLM_SITE_NAME,
                    },
                }
                # En la última iteración forzamos respuesta de texto (sin tools)
                if not is_last_iteration:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                resp = client.chat.completions.create(**kwargs)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                total_latency_ms += elapsed_ms

                usage = resp.usage
                total_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
                total_output_tokens += getattr(usage, "completion_tokens", 0) or 0

                choice = resp.choices[0]
                msg = choice.message
                finish_reason = choice.finish_reason
                tool_calls = getattr(msg, "tool_calls", None) or []

                if not tool_calls or is_last_iteration:
                    text = (msg.content or "").strip()
                    return LLMResult(
                        text=text,
                        model=model_effective,
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        latency_ms=total_latency_ms,
                        tool_calls_executed=tool_calls_executed,
                    )

                # Persistir el turn del assistant con tool_calls en el contexto
                working_messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                # Ejecutar cada tool call y agregar los resultados como mensajes "tool"
                for tc in tool_calls:
                    tool_name = tc.function.name
                    try:
                        arguments = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    try:
                        result = tool_executor(tool_name, arguments)
                    except Exception as exc:
                        logger.exception("Tool %s falló: %s", tool_name, exc)
                        result = {"error": f"tool_execution_failed: {str(exc)[:150]}"}

                    tool_calls_executed.append({
                        "name": tool_name,
                        "arguments": arguments,
                        "result": result,
                    })

                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

            # Si llegamos aquí algo raro pasó — retornar lo último que tengamos
            return LLMResult(
                text="",
                model=model_effective,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                latency_ms=total_latency_ms,
                error="max_iterations_without_final_text",
                tool_calls_executed=tool_calls_executed,
            )

        except APITimeoutError as e:
            logger.warning("OpenRouter (tools) timeout: %s", e)
            return LLMResult("", model_effective, total_input_tokens, total_output_tokens,
                             total_latency_ms, error=f"timeout: {str(e)[:150]}",
                             tool_calls_executed=tool_calls_executed)
        except RateLimitError as e:
            logger.warning("OpenRouter (tools) rate limit: %s", e)
            return LLMResult("", model_effective, total_input_tokens, total_output_tokens,
                             total_latency_ms, error=f"rate_limit: {str(e)[:150]}",
                             tool_calls_executed=tool_calls_executed)
        except APIError as e:
            logger.error("OpenRouter (tools) APIError: %s", e)
            return LLMResult("", model_effective, total_input_tokens, total_output_tokens,
                             total_latency_ms, error=f"api_error: {str(e)[:150]}",
                             tool_calls_executed=tool_calls_executed)
        except Exception as e:
            logger.exception("OpenRouter (tools) unexpected: %s", e)
            return LLMResult("", model_effective, total_input_tokens, total_output_tokens,
                             total_latency_ms, error=f"unexpected: {str(e)[:150]}",
                             tool_calls_executed=tool_calls_executed)
