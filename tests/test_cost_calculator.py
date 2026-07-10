"""
tests/test_cost_calculator.py — unit tests for the pure cost functions.

cost_calculator has no I/O, so these are fast, deterministic, and dependency-free.
They pin the economic contract EconRoute markets: actual=$0, routing saves vs GPT-4o,
and a cache hit avoids the FULL baseline cost.
"""

import pytest

from providers.model_config import BASELINE_RATES, GROQ_TIERS
from tracking.cost_calculator import compute_costs, estimate_tokens_from_text


def test_actual_cost_is_always_zero():
    for tier in ("simple", "medium", "complex"):
        c = compute_costs(tier=tier, input_tokens=1000, output_tokens=1000)
        assert c.actual_cost_usd == 0.0


def test_routing_savings_is_baseline_minus_theoretical():
    c = compute_costs(tier="simple", input_tokens=1000, output_tokens=1000)

    expected_baseline = BASELINE_RATES["input"] + BASELINE_RATES["output"]  # 1K each
    expected_theoretical = (
        GROQ_TIERS["simple"]["theoretical_cost_per_1k_input"]
        + GROQ_TIERS["simple"]["theoretical_cost_per_1k_output"]
    )

    assert c.baseline_cost_usd == pytest.approx(expected_baseline)
    assert c.theoretical_cost_usd == pytest.approx(expected_theoretical)
    assert c.savings_usd == pytest.approx(expected_baseline - expected_theoretical)
    assert c.savings_source == "routing"
    assert c.savings_usd > 0  # routing must be cheaper than the baseline


def test_cache_hit_avoids_full_baseline():
    c = compute_costs(tier="simple", input_tokens=500, output_tokens=500, cache_hit=True)

    assert c.theoretical_cost_usd == 0.0          # nothing was inferred
    assert c.savings_usd == c.baseline_cost_usd    # full GPT-4o cost avoided
    assert c.savings_source == "cache"


def test_zero_tokens_cost_nothing():
    c = compute_costs(tier="complex", input_tokens=0, output_tokens=0)
    assert c.baseline_cost_usd == 0.0
    assert c.theoretical_cost_usd == 0.0
    assert c.savings_usd == 0.0


def test_invalid_tier_raises_keyerror():
    with pytest.raises(KeyError):
        compute_costs(tier="nonexistent", input_tokens=10, output_tokens=10)


@pytest.mark.parametrize(
    "text,expected",
    [("", 1), ("abcd", 1), ("a" * 400, 100)],
)
def test_estimate_tokens_floor_and_ratio(text, expected):
    assert estimate_tokens_from_text(text) == expected
