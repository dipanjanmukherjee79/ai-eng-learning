"""
AUD pricing per provider, per model.
Verify rates yourself; they change.
"""
from providers.base import Usage


PRICING_AUD: dict[str, dict[str, dict[str, float]]] = {
    "claude": {
        "claude-sonnet-4-5": {"input": 4.50, "output": 22.50},
    },
    "openai": {
        "gpt-4o-mini": {"input": 0.23, "output": 0.93},
    },
}


def calculate_cost_aud(provider: str, model: str, usage: Usage) -> float:
    """Calculate AUD cost from per-call usage."""
    rates = PRICING_AUD.get(provider, {}).get(model)
    if not rates:
        return 0.0
    input_cost = (usage.input_tokens / 1_000_000) * rates["input"]
    output_cost = (usage.output_tokens / 1_000_000) * rates["output"]
    return input_cost + output_cost