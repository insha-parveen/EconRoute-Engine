"""
tracking/cost_calculator.py — Computes actual / theoretical / baseline / savings.

Design: Pure functions only. No I/O, no side effects.
This makes it trivially unit-testable and reusable across gateway + evals.

Key insight:
  actual_cost      = always $0.00 (Groq / Ollama are free)
  theoretical_cost = tokens × equivalent paid-tier rate
  baseline_cost    = tokens × GPT-4o rate
  savings          = baseline - theoretical

For cache hits:
  theoretical_cost = $0.00 (no inference ran)
  savings          = full baseline (we avoided ALL cost)
"""

from providers.model_config import GROQ_TIERS, BASELINE_RATES
from gateway.models import CostBreakdown


def compute_costs(
    tier: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit: bool = False,
) -> CostBreakdown:
    """
    Compute all cost fields for a single request.

    Args:
        tier        : "simple" | "medium" | "complex"
        input_tokens : number of input tokens used
        output_tokens: number of output tokens generated
        cache_hit   : if True, theoretical_cost = 0 (no inference ran)

    Returns:
        CostBreakdown with all 6 cost fields populated.

    Edge cases:
        - token counts of 0 → costs are $0.00 (no division by zero risk)
        - unknown tier → raises KeyError (caller must validate tier first)
    """
    # ── Baseline cost (GPT-4o equivalent for same tokens) ──────────────────
    baseline_cost = _compute_cost(
        input_tokens, output_tokens,
        BASELINE_RATES["input"], BASELINE_RATES["output"]
    )

    # ── Cache hit: no inference ran, full baseline avoided ──────────────────
    if cache_hit:
        return CostBreakdown(
            actual_cost_usd=0.0,
            theoretical_cost_usd=0.0,        # nothing was called
            baseline_cost_usd=baseline_cost,
            savings_usd=baseline_cost,        # we avoided the full GPT-4o cost
            savings_source="cache",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # ── Routing: called a cheaper model ─────────────────────────────────────
    rates = GROQ_TIERS[tier]                  # KeyError if invalid tier — intentional
    theoretical_cost = _compute_cost(
        input_tokens, output_tokens,
        rates["theoretical_cost_per_1k_input"],
        rates["theoretical_cost_per_1k_output"],
    )

    return CostBreakdown(
        actual_cost_usd=0.0,                  # Groq is always free
        theoretical_cost_usd=theoretical_cost,
        baseline_cost_usd=baseline_cost,
        savings_usd=baseline_cost - theoretical_cost,
        savings_source="routing",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _compute_cost(
    input_tokens: int,
    output_tokens: int,
    input_rate: float,
    output_rate: float,
) -> float:
    """
    Generic cost formula: tokens / 1000 × rate_per_1k

    Args:
        input_tokens  : prompt token count
        output_tokens : completion token count
        input_rate    : $ per 1K input tokens
        output_rate   : $ per 1K output tokens

    Returns:
        total cost in USD (float, rounded to 8 decimal places)
    """
    cost = (input_tokens / 1000 * input_rate) + (output_tokens / 1000 * output_rate)
    return round(cost, 8)


def estimate_tokens_from_text(text: str) -> int:
    """
    Fallback token estimator when the API doesn't return usage stats.

    Rule of thumb: ~4 characters per token (GPT tokenizer average).
    This is a rough estimate — real token counts vary by language/content.
    """
    return max(1, len(text) // 4)
