"""Persiste métricas LLM (tokens, costo, latencia, error) en un ConversationMessage."""

from decimal import Decimal

from .pricing import calculate_cost_usd


class CostTracker:
    """Registra tokens, costo y latencia de una llamada LLM en un ConversationMessage."""

    @staticmethod
    def record_to_message(
        message,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        error: str = "",
    ):
        message.llm_model = model or ""
        message.llm_input_tokens = input_tokens or 0
        message.llm_output_tokens = output_tokens or 0
        message.llm_latency_ms = latency_ms or 0
        message.llm_error = (error or "")[:200]
        if not error:
            message.llm_cost_usd = Decimal(str(round(
                calculate_cost_usd(model, input_tokens, output_tokens), 6
            )))
        message.save(update_fields=[
            "llm_model", "llm_input_tokens", "llm_output_tokens",
            "llm_cost_usd", "llm_latency_ms", "llm_error",
        ])
