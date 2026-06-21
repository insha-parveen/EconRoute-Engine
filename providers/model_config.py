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
    - Haiku equiv:  Claude Haiku pricing (similar capability to gpt-oss-20b)
    - Mini equiv:   GPT-4o-mini pricing (similar capability to llama-3.3-70b)

Model status (verified June 2026 — console.groq.com/docs/models):
  simple  : openai/gpt-oss-20b       — Production, 1000 t/s (fastest on Groq)
  medium  : llama-3.3-70b-versatile  — Production, 280 t/s  (proven quality)
  complex : openai/gpt-oss-120b      — Production, 500 t/s  (flagship, reasoning)

LiteLLM prefix rule:
  groq/{model_id} tells LiteLLM to route to Groq.
  model_id must match EXACTLY what Groq's API expects.
  e.g. groq/openai/gpt-oss-20b — 'groq' = provider, 'openai/gpt-oss-20b' = model on Groq.
"""

import os
from typing import TypedDict


# Resolved once at import time — same value used for all three tiers.
# Override in .env:
#   Windows/Mac Docker : OLLAMA_BASE_URL=http://host.docker.internal:11434
#   Linux Docker       : OLLAMA_BASE_URL=http://172.17.0.1:11434
#   Local dev          : OLLAMA_BASE_URL=http://localhost:11434 (default)
_OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"


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
        "model": "groq/openai/gpt-oss-20b",        # 1000 t/s — fastest on Groq
        "actual_cost_per_1k_input": 0.0,
        "actual_cost_per_1k_output": 0.0,
        # Theoretical equivalent: Claude Haiku ($0.00025 input / $0.00125 output per 1K)
        "theoretical_cost_per_1k_input": 0.00025,
        "theoretical_cost_per_1k_output": 0.00125,
        "max_tokens": 1024,
    },
    "medium": {
        "model": "groq/llama-3.3-70b-versatile",   # 280 t/s — proven, stable
        "actual_cost_per_1k_input": 0.0,
        "actual_cost_per_1k_output": 0.0,
        # Theoretical equivalent: GPT-4o-mini ($0.00015 input / $0.00060 output per 1K)
        "theoretical_cost_per_1k_input": 0.00015,
        "theoretical_cost_per_1k_output": 0.00060,
        "max_tokens": 2048,
    },
    "complex": {
        "model": "groq/openai/gpt-oss-120b",       # 500 t/s — flagship, reasoning capable
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
    "simple": {
        "model": "ollama/qwen2.5:0.5b",
        "api_base": _OLLAMA_BASE,
        "actual_cost_per_1k_input": 0.0,
        "actual_cost_per_1k_output": 0.0,
        "theoretical_cost_per_1k_input": 0.00025,
        "theoretical_cost_per_1k_output": 0.00125,
        "max_tokens": 1024,
    },
    "medium": {
        "model": "ollama/llama3.2:3b",
        "api_base": _OLLAMA_BASE,
        "actual_cost_per_1k_input": 0.0,
        "actual_cost_per_1k_output": 0.0,
        "theoretical_cost_per_1k_input": 0.00015,
        "theoretical_cost_per_1k_output": 0.00060,
        "max_tokens": 2048,
    },
    "complex": {
        "model": "ollama/llama3.1:8b",
        "api_base": _OLLAMA_BASE,
        "actual_cost_per_1k_input": 0.0,
        "actual_cost_per_1k_output": 0.0,
        "theoretical_cost_per_1k_input": 0.00500,
        "theoretical_cost_per_1k_output": 0.01500,
        "max_tokens": 4096,
    },
}

# ─── GPT-4o Baseline (for theoretical savings calculation ONLY) ───────────────

BASELINE_RATES = {
    "input":  0.00500,   # $ per 1K input tokens
    "output": 0.01500,   # $ per 1K output tokens
    # Source: https://openai.com/pricing — update if OpenAI changes pricing
}

# ─── Helper: all valid tier names ─────────────────────────────────────────────

VALID_TIERS = list(GROQ_TIERS.keys())   # ["simple", "medium", "complex"]

# ─── Groq free tier limits ────────────────────────────────────────────────────
# Source: https://console.groq.com/docs/models (verified June 2026)
# Note: Free tier = Developer plan limits below

GROQ_RATE_LIMITS = {
    "groq/openai/gpt-oss-20b":       {"rpm": 1000, "tpm": 250_000, "rpd": 14_400},
    "groq/llama-3.3-70b-versatile":  {"rpm": 1000, "tpm": 300_000, "rpd": 14_400},
    "groq/openai/gpt-oss-120b":      {"rpm": 1000, "tpm": 250_000, "rpd": 14_400},
}
