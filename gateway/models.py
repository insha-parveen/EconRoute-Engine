"""
gateway/models.py — Pydantic schemas for all EconRoute data structures.

Design principle: OpenAI-compatible request/response schema + routing metadata fields.
Any existing OpenAI SDK client can call EconRoute with only base_url changed.

Key schemas:
  ChatRequest     : incoming POST /v1/chat/completions body
  ChatMessage     : a single {role, content} message
  RouteDecision   : which tier/model was chosen and why
  CostBreakdown   : actual / theoretical / baseline / savings
  ChatResponse    : full response — OpenAI fields + EconRoute metadata
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── Request Schemas ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in a conversation (mirrors OpenAI schema)."""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """
    POST /v1/chat/completions body.
    'model' can be 'auto' (EconRoute chooses) or a specific model name.
    All other fields mirror OpenAI's ChatCompletion API.
    """
    model: str = Field(default="auto", description="'auto' lets EconRoute choose the tier")
    messages: list[ChatMessage]
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = Field(default=False)

    @field_validator("stream")
    @classmethod
    def stream_must_be_false(cls, v: Optional[bool]) -> Optional[bool]:
        """
        Reject stream=True at validation time — not just in main.py at runtime.
        Enforces the contract in the schema itself so no request can slip through.
        Remove this validator in the week streaming is implemented.
        """
        if v is True:
            raise ValueError(
                "Streaming is not yet supported. Set stream=false or omit the field."
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "auto",
                "messages": [{"role": "user", "content": "What is the capital of France?"}]
            }
        }
    )


# ─── Internal Routing Schemas ─────────────────────────────────────────────────

class RouteDecision(BaseModel):
    """Internal: what the classifier + router decided for this request."""
    tier: Literal["simple", "medium", "complex"]
    model: str                           # e.g. "groq/llama-3.1-8b-instant"
    classifier_label: str                # raw label from semantic-router
    cache_hit: bool = False
    fallback_used: bool = False          # True if Groq failed and Ollama was used


class CostBreakdown(BaseModel):
    """
    Cost accounting for a single request.

    actual_cost is ALWAYS 0.0 — Groq and Ollama are free.
    theoretical_cost = what the equivalent paid API would charge.
    baseline_cost    = what GPT-4o would charge for the same tokens.
    savings          = baseline - theoretical (the economic value of routing).
    """
    actual_cost_usd: float = 0.0
    theoretical_cost_usd: float = 0.0
    baseline_cost_usd: float = 0.0
    savings_usd: float = 0.0
    savings_source: Literal["cache", "routing"] = "routing"
    input_tokens: int = 0
    output_tokens: int = 0


# ─── Response Schema ──────────────────────────────────────────────────────────

class ChatResponseChoice(BaseModel):
    """Mirrors OpenAI's choices[0] structure."""
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatResponse(BaseModel):
    """
    POST /v1/chat/completions response.

    OpenAI-compatible fields + EconRoute metadata fields.
    The metadata fields are additive — they don't break existing OpenAI SDK parsing.
    """
    # ── OpenAI-compatible fields ──
    id: str                            # e.g. "chatcmpl-abc123"
    object: str = "chat.completion"
    model: str                         # echoes back the model field from request

    choices: list[ChatResponseChoice]

    # ── EconRoute metadata ──
    model_used: str                    # actual model called, e.g. "groq/llama-3.1-8b-instant"
    tier: str                          # "cache" | "simple" | "medium" | "complex"
    cache_hit: bool
    latency_ms: float

    # Cost fields (flat, for easy dashboard consumption)
    actual_cost_usd: float
    theoretical_cost_usd: float
    baseline_cost_usd: float
    savings_usd: float
    savings_source: str                # "cache" | "routing"

    input_tokens: int
    output_tokens: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "chatcmpl-abc123",
                "object": "chat.completion",
                "model": "auto",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Paris."}, "finish_reason": "stop"}],
                "model_used": "groq/llama-3.1-8b-instant",
                "tier": "simple",
                "cache_hit": False,
                "latency_ms": 187.0,
                "actual_cost_usd": 0.0,
                "theoretical_cost_usd": 0.00008,
                "baseline_cost_usd": 0.00160,
                "savings_usd": 0.00152,
                "savings_source": "routing",
                "input_tokens": 12,
                "output_tokens": 3,
            }
        }
    )


# ─── Health Check Schema ──────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    cache: str       # "connected" | "error"
    db: str          # "connected" | "error"
    groq: str        # "ok" | "error"


# ─── Analytics Schemas (Week 5 — /v1/stats, /v1/requests) ─────────────────────
# All fields defaulted so an empty payload (no rows / DB down) still validates and
# returns a clean 200. Consumed by the Next.js dashboard.

class StatsTotals(BaseModel):
    requests: int = 0
    savings_usd: float = 0.0
    baseline_usd: float = 0.0
    savings_pct: float = 0.0          # savings / baseline * 100
    cache_hit_rate: float = 0.0       # % of requests served from cache
    actual_spend: float = 0.0         # always 0 — Groq/Ollama are free


class TierCount(BaseModel):
    tier: str
    count: int


class LatencyPercentile(BaseModel):
    tier: str
    p50: float
    p95: float
    count: int


class CumulativePoint(BaseModel):
    timestamp: str                    # ISO 8601
    cumulative_savings: float


class CacheHitMiss(BaseModel):
    hit: int = 0
    miss: int = 0


class StatsResponse(BaseModel):
    """Aggregated analytics for the dashboard — mirrors the Streamlit computations."""
    totals: StatsTotals = Field(default_factory=StatsTotals)
    tier_distribution: list[TierCount] = Field(default_factory=list)
    latency_percentiles: list[LatencyPercentile] = Field(default_factory=list)
    cumulative_savings: list[CumulativePoint] = Field(default_factory=list)
    cache_hit_vs_miss: CacheHitMiss = Field(default_factory=CacheHitMiss)


class RequestRow(BaseModel):
    """One recent request — PII-safe columns only (query_id is a hash, never raw text)."""
    created_at: str                   # ISO 8601
    tier: str
    model_used: str
    query_id: str
    cache_hit: bool
    fallback_used: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    theoretical_cost_usd: float
    baseline_cost_usd: float
    savings_usd: float
    savings_source: str


class RequestsResponse(BaseModel):
    requests: list[RequestRow] = Field(default_factory=list)
