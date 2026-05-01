"""Cost calculation utilities with exact provider pricing."""
from typing import Literal

ProviderType = Literal["claude-haiku", "claude-sonnet", "gemini-flash", "gemini-pro"]

# Exact pricing as of 2024 (input, output per 1M tokens)
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku": (0.80, 4.00),    # claude-3-5-haiku-20241022
    "claude-sonnet": (3.00, 15.00),  # claude-3-5-sonnet-20241022
    "gemini-flash": (0.075, 0.30),   # gemini-1.5-flash
    "gemini-pro": (1.25, 5.00),      # gemini-1.5-pro
}


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    provider: ProviderType,
) -> float:
    """
    Calculate exact cost for given token usage.

    >>> calculate_cost(1000, 500, "claude-haiku")
    0.0028  # (1000 × $0.80/1M) + (500 × $4.00/1M)
    """
    input_price, output_price = PRICING[provider]
    cost = input_tokens / 1_000_000 * input_price + output_tokens / 1_000_000 * output_price
    return round(cost, 8)


def calculate_all_hypothetical_costs(
    input_tokens: int,
    output_tokens: int,
) -> dict[str, float]:
    """Calculate what this call would cost across all paid providers."""
    return {
        "claude_haiku": calculate_cost(input_tokens, output_tokens, "claude-haiku"),
        "claude_sonnet": calculate_cost(input_tokens, output_tokens, "claude-sonnet"),
        "gemini_flash": calculate_cost(input_tokens, output_tokens, "gemini-flash"),
        "gemini_pro": calculate_cost(input_tokens, output_tokens, "gemini-pro"),
    }
