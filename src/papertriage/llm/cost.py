from typing import Any

# Approximate prices as of 2024-Q4. Check https://anthropic.com/pricing for current rates.
# Units: USD per million tokens.
PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {
        "input": 1.00,
        "output": 5.00,
        "cache_creation": 1.25,  # 1.25x input price
        "cache_read": 0.10,      # 0.1x input price
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_creation": 3.75,
        "cache_read": 0.30,
    },
}

_FALLBACK = {"input": 3.00, "output": 15.00, "cache_creation": 3.75, "cache_read": 0.30}


def estimate(model: str, usage: Any) -> float:
    """Return approximate cost in USD. Prices are estimates, not guaranteed."""
    price = PRICING.get(model, _FALLBACK)

    input_tokens: int = getattr(usage, "input_tokens", 0) or 0
    output_tokens: int = getattr(usage, "output_tokens", 0) or 0
    cache_creation: int = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read: int = getattr(usage, "cache_read_input_tokens", 0) or 0

    # Tokens counted for cache creation/read are separate from regular input tokens
    # in Anthropic's billing model.
    cost = (
        input_tokens * price["input"]
        + output_tokens * price["output"]
        + cache_creation * price["cache_creation"]
        + cache_read * price["cache_read"]
    ) / 1_000_000

    return cost
