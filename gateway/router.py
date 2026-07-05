"""
gateway/router.py — The brain of EconRoute.

Flow per request:
  1. Semantic cache check  (Week 2 — stub in Week 1)
  2. Complexity classify   (Week 3 — semantic-router replacing keyword heuristic)
  3. Call model via LiteLLM
  4. Compute costs
  5. Log to DB             (Week 4 — print to console in Week 1)
  6. Return ChatResponse

Design: route() is the single entry point called by main.py.
All complexity lives here, main.py stays clean.
"""

import time
import uuid
import logging
import os
from typing import Literal

from gateway.models import ChatRequest, ChatResponse, ChatResponseChoice, ChatMessage, RouteDecision, CostBreakdown
from providers.litellm_client import call_model, LLMError, LLMResponse
from tracking.cost_calculator import compute_costs, estimate_tokens_from_text
from gateway.cache import find_match, store
from gateway.classifier import classify
from gateway.fallback import call_with_fallback

logger = logging.getLogger(__name__)


# ─── Week 3 Complexity Classifier (semantic-router) ─────────────────────────
# Replaces Week 1 keyword heuristic with meaning-based classification.
# "Can you tell me about Python?" → simple (keyword missed this; semantic gets it)

def _classify_complexity(messages: list[ChatMessage]) -> str:
    """
    Classify query complexity using semantic-router.
    Returns: "simple" | "medium" | "complex"

    Extracts last user message → passes to classify() in classifier.py.
    Falls back to "medium" on empty input or classifier error (handled inside classify()).
    """
    user_messages = [m for m in messages if m.role == "user"]
    if not user_messages:
        return "medium"

    last_user_msg = user_messages[-1].content
    return classify(last_user_msg)


# ─── Cache (Week 2 — Redis + sentence-transformers) ─────────────────────────

async def _check_cache(messages: list[ChatMessage]) -> str | None:
    """
    Week 2: cosine similarity lookup via Redis.
    Delegates to gateway.cache.find_match().
    Returns cached response string or None on miss/error.
    """
    return await find_match(messages)


async def _store_cache(messages: list[ChatMessage], response_text: str, tier: str = "unknown") -> None:
    """
    Week 2: store embedding + response in Redis with TTL.
    Truly fire-and-forget — any error (embed failure, Redis error) is caught
    and logged here so it never propagates to route() or the caller.
    A failed cache write must never break the response already sent to the user.
    """
    try:
        await store(messages, response_text, tier=tier)
    except Exception as e:
        logger.warning(f"Cache store skipped — {type(e).__name__}: {e}")


# ─── Logger Stub (Week 4 will write to Postgres) ─────────────────────────────

async def _log_request(response: ChatResponse) -> None:
    """
    Week 1: print to console.
    Week 4: replaces with async PostgreSQL insert + WebSocket emit.
    """
    logger.info(
        f"[ROUTE] tier={response.tier} | model={response.model_used} | "
        f"cache_hit={response.cache_hit} | latency={response.latency_ms:.0f}ms | "
        f"actual=${response.actual_cost_usd:.5f} | "
        f"theoretical=${response.theoretical_cost_usd:.5f} | "
        f"baseline=${response.baseline_cost_usd:.5f} | "
        f"savings=${response.savings_usd:.5f} ({response.savings_source})"
    )


# ─── Main Route Function ──────────────────────────────────────────────────────

async def route(request: ChatRequest) -> ChatResponse:
    """
    Main entry point: takes a ChatRequest, returns a ChatResponse.

    This function is called by main.py for every POST /v1/chat/completions.

    Steps:
      1. Check semantic cache (Week 2 — Redis cosine similarity)
      2. Classify complexity → tier
      3. Call model via LiteLLM (with Ollama fallback attempt)
      4. Compute costs
      5. Log (console in Week 1)
      6. Return full ChatResponse

    Edge cases:
      - Groq fails → try Ollama fallback if FALLBACK_TO_OLLAMA=true
      - Ollama also fails → raise original LLMError (500 to client)
    """
    start_time = time.perf_counter()
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # ── Step 1: Cache Check ──────────────────────────────────────────────────
    cached_text = await _check_cache(request.messages)

    if cached_text:
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Estimate tokens so baseline_cost + savings reflect real economic value.
        # We use estimates here (not actuals) because no LLM was called —
        # actual token counts only come from the LLM response object.
        estimated_input  = sum(estimate_tokens_from_text(m.content) for m in request.messages)
        estimated_output = estimate_tokens_from_text(cached_text)

        costs = compute_costs(
            tier="simple",
            input_tokens=estimated_input,
            output_tokens=estimated_output,
            cache_hit=True,
        )

        response = _build_response(
            request_id=request_id,
            request=request,
            content=cached_text,
            model_used="cache",
            tier="cache",
            cache_hit=True,
            fallback_used=False,
            latency_ms=latency_ms,
            costs=costs,
        )
        await _log_request(response)
        return response

    # ── Step 2: Classify Complexity ──────────────────────────────────────────
    tier = _classify_complexity(request.messages)

    # ── Step 3: Call Model (with full fallback chain) ───────────────────────
    # call_with_fallback handles: backoff on rate limits, tier escalation,
    # Ollama fallback, and clear error messages.
    llm_response, tier_used, fallback_used = await call_with_fallback(
        tier=tier,
        messages=request.messages,
        temperature=request.temperature or 0.7,
        max_tokens=request.max_tokens,
    )
    # Update tier in case fallback chain escalated (simple → medium etc.)
    tier = tier_used

    latency_ms = (time.perf_counter() - start_time) * 1000

    # ── Step 4: Compute Costs ────────────────────────────────────────────────
    costs = compute_costs(
        tier=tier,
        input_tokens=llm_response["input_tokens"],
        output_tokens=llm_response["output_tokens"],
        cache_hit=False,
    )

    # ── Step 5: Store in cache for next time (Week 2 — Redis + embeddings) ───
    await _store_cache(request.messages, llm_response["content"], tier=tier)

    # ── Step 6: Build + log + return ─────────────────────────────────────────
    response = _build_response(
        request_id=request_id,
        request=request,
        content=llm_response["content"],
        model_used=llm_response["model_used"],
        tier=tier,
        cache_hit=False,
        fallback_used=fallback_used,
        latency_ms=latency_ms,
        costs=costs,
    )
    await _log_request(response)
    return response


# ─── Response Builder ─────────────────────────────────────────────────────────

def _build_response(
    request_id: str,
    request: ChatRequest,
    content: str,
    model_used: str,
    tier: str,
    cache_hit: bool,
    fallback_used: bool,
    latency_ms: float,
    costs: CostBreakdown,
) -> ChatResponse:
    """Assemble the full ChatResponse from all computed parts."""
    return ChatResponse(
        id=request_id,
        object="chat.completion",
        model=request.model,
        choices=[
            ChatResponseChoice(
                index=0,
                message=ChatMessage(role="assistant", content=content),
                finish_reason="stop",
            )
        ],
        model_used=model_used,
        tier=tier,
        cache_hit=cache_hit,
        latency_ms=round(latency_ms, 2),
        actual_cost_usd=costs.actual_cost_usd,
        theoretical_cost_usd=costs.theoretical_cost_usd,
        baseline_cost_usd=costs.baseline_cost_usd,
        savings_usd=costs.savings_usd,
        savings_source=costs.savings_source,
        input_tokens=costs.input_tokens,
        output_tokens=costs.output_tokens,
    )
