"""Cost calculation utilities for AI token usage."""

from decimal import Decimal
from typing import Optional


def calculate_cost(
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    input_price_per_1m: Optional[Decimal],
    output_price_per_1m: Optional[Decimal],
) -> Optional[Decimal]:
    """Return the USD cost for a request or ``None`` if any value is missing.

    Args:
        input_tokens: Number of tokens in the prompt.
        output_tokens: Number of tokens in the completion.
        input_price_per_1m: Price per 1 million input tokens (USD).
        output_price_per_1m: Price per 1 million output tokens (USD).

    Returns:
        Decimal cost or ``None`` when tokens or prices are unavailable.
    """
    if (
        input_tokens is None
        or output_tokens is None
        or input_price_per_1m is None
        or output_price_per_1m is None
    ):
        return None

    cost = (
        Decimal(input_tokens) / Decimal(1_000_000) * input_price_per_1m
        + Decimal(output_tokens) / Decimal(1_000_000) * output_price_per_1m
    )
    return cost
