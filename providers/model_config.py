"""
providers/model_config.py — Single source of truth for model tiers and cost rates.

Architecture note:
  - GROQ_TIERS   : primary inference (actual cost = $0.00, free tier)
  - OLLAMA_TIERS : local fallback (actual cost = $0.00, runs on your machine)
  - BASELINE_RATES: GPT-4o published pricing — used ONLY to compute theoretical savings

Why theoretical rates?
  EconRoute runs free models. "Theoretical cost" = what the same request would cost
  on an equivalent paid model. This lets us show routing value in a cost-neutral env.
  Rate sources:
    - GPT-4o:       https://openai.com/pricing
    - Haiku equiv:  Claude Haiku pricing (similar capability to llama-3.1-8b)
    - Mini equiv:   GPT-4o-mini pricing (similar capability to llama-3.3-70b)
"""

from typing import TypedDict


class TierConfig(TypedDict):
    model: str
    actual_cost_per_1k_input: float
    actual_cost_per_1k_output: float
    theoretical_cost_per_1k_input: float
    theoretical_cost_per_1k_output: float
    max_tokens: int


# ─── Primary Inference (Groq Free Tier) ───────────────────────────────────────

GROQ_TIERS: dict[str, TierConfig] = {
    "simple": {
        "model": "groq/llama-3.1-8b-instant",
        "actual_cost_per_1k_input": 0.0,       # free tier
        "actual_cost_per_1k_output": 0.0,
        # Theoretical equivalent: Claude Haiku ($0.00025 input / $0.00125 output per 1K)
        "theoretical_cost_per_1k_input": 0.00025,
        "theoretical_cost_per_1k_output": 0.00125,
        "max_tokens": 1024,
    },
    "medium": {
        "model": "groq/llama-3.3-70b-versatile",
        "actual_cost_per_1k_input": 0.0,
        "actual_cost_per_1k_output": 0.0,
        # Theoretical equivalent: GPT-4o-mini ($0.00015 input / $0.00060 output per 1K)
        "theoretical_cost_per_1k_input": 0.00015,
        "theoretical_cost_per_1k_output": 0.00060,
        "max_tokens": 2048,
    },
    "complex": {
        "model": "groq/deepseek-r1-distill-llama-70b",
        "actual_cost_per_1k_input": 0.0,
        "actual_cost_per_1k_output": 0.0,
        # Theoretical equivalent: GPT-4o ($0.00500 input / $0.01500 output per 1K)
        "theoretical_cost_per_1k_input": 0.00500,
        "theoretical_cost_per_1k_output": 0.01500,
        "max_tokens": 4096,
    },
}

# ─── Local Fallback (Ollama — runs on your machine) ───────────────────────────

OLLAMA_TIERS: dict[str, dict] = {
    "simple":  {"model": "ollama/qwen2.5:0.5b",  "api_base": "http://localhost:11434"},
    "medium":  {"model": "ollama/llama3.2:3b",   "api_base": "http://localhost:11434"},
    "complex": {"model": "ollama/llama3.1:8b",   "api_base": "http://localhost:11434"},
}

# ─── GPT-4o Baseline (for theoretical savings calculation ONLY) ───────────────

BASELINE_RATES = {
    "input":  0.00500,   # $ per 1K input tokens
    "output": 0.01500,   # $ per 1K output tokens
    # Source: https://openai.com/pricing — update if OpenAI changes pricing
}

# ─── Helper: all valid tier names ─────────────────────────────────────────────

VALID_TIERS = list(GROQ_TIERS.keys())   # ["simple", "medium", "complex"]

# ─── Groq free tier limits (for rate limit awareness) ─────────────────────────
# Source: https://console.groq.com/docs/rate-limits

GROQ_RATE_LIMITS = {
    "llama-3.1-8b-instant":          {"rpm": 30, "tpm": 131_072, "rpd": 14_400},
    "llama-3.3-70b-versatile":       {"rpm": 30, "tpm": 131_072, "rpd": 14_400},
    "deepseek-r1-distill-llama-70b": {"rpm": 30, "tpm": 131_072, "rpd": 14_400},
}
