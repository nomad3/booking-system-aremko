"""Precios en USD por 1.000.000 de tokens.

Fuente: https://openrouter.ai/models — actualizar manualmente si cambian.
"""

PRICING = {
    "anthropic/claude-haiku-4.5": {"input": 1.00, "output": 5.00},
    "anthropic/claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "google/gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "google/gemini-2.5-pro": {"input": 1.25, "output": 5.00},
}

DEFAULT_FALLBACK = {"input": 1.00, "output": 5.00}


def get_model_pricing(model: str) -> dict:
    """Devuelve {"input": float, "output": float} por 1M tokens."""
    return PRICING.get(model, DEFAULT_FALLBACK)


def calculate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calcula el costo estimado de una llamada."""
    p = get_model_pricing(model)
    return (input_tokens / 1_000_000 * p["input"]) + (output_tokens / 1_000_000 * p["output"])
