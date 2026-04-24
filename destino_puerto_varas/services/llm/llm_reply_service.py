"""Fachada entre conversation_flow_service y el provider LLM.

Siempre devuelve (text, metadata) — el metadata se registra en el ConversationMessage
del asistente por el caller usando CostTracker.
"""

from django.conf import settings

from .openrouter_provider import OpenRouterProvider
from .prompts import (
    SYSTEM_PROMPT,
    build_follow_up_prompt,
    build_recommend_circuit_prompt,
)


class LLMReplyService:
    """Entry point único desde el flujo. Encapsula fallback determinístico."""

    def __init__(self):
        self.provider = OpenRouterProvider()
        self.enabled = settings.DPV_LLM_ENABLED

    def reply_recommend_circuit(self, context: dict, fallback_text: str) -> dict:
        """Genera respuesta LLM para RECOMMEND_CIRCUIT; si falla o está apagado → fallback."""
        return self._generate_with_fallback(
            fallback_text,
            user_prompt_fn=lambda: build_recommend_circuit_prompt(context),
        )

    def reply_follow_up(self, context: dict, user_message: str, fallback_text: str) -> dict:
        """Genera respuesta LLM para FOLLOW_UP; si falla o está apagado → fallback."""
        return self._generate_with_fallback(
            fallback_text,
            user_prompt_fn=lambda: build_follow_up_prompt(context, user_message),
        )

    def _generate_with_fallback(self, fallback_text: str, user_prompt_fn) -> dict:
        if not self.enabled:
            return {"text": fallback_text, "llm_used": False, "metadata": {}}

        user_prompt = user_prompt_fn()
        result = self.provider.generate(SYSTEM_PROMPT, user_prompt)

        if not result.ok or not result.text:
            return {
                "text": fallback_text,
                "llm_used": False,
                "metadata": {
                    "model": result.model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "latency_ms": result.latency_ms,
                    "error": result.error or "empty_response",
                },
            }

        return {
            "text": result.text,
            "llm_used": True,
            "metadata": {
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": result.latency_ms,
                "error": "",
            },
        }


_instance = None


def get_llm_reply_service() -> LLMReplyService:
    """Singleton liviano — evita reinstanciar el cliente HTTP por request."""
    global _instance
    if _instance is None:
        _instance = LLMReplyService()
    return _instance
