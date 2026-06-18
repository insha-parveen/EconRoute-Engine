"""
gateway/router.py — The brain of EconRoute.

Flow per request:
  1. Semantic cache check  (Week 2 — stub in Week 1)
  2. Complexity classify   (Week 3 semantic-router — keyword heuristic in Week 1)
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
from tracking.cost_calculator import compute_costs

logger = logging.getLogger(__name__)


# ─── Week 1 Complexity Classifier (Keyword Heuristic) ────────────────────────
# This is a TEMPORARY placeholder. Week 3 replaces this with semantic-router.
# It works well enough to demonstrate routing — don't over-engineer now.

COMPLEX_KEYWORDS = {
    "analyze", "analyse", "explain in detail", "compare", "contrast",
    "write a program", "write code", "debug", "implement", "algorithm",
    "design", "architecture", "proof", "derive", "calculate", "solve",
    "research", "summarize this", "translate this entire", "essay",
}

SIMPLE_KEYWORDS = {
    "what is", "who is", "when was", "where is", "capital of",
    "define", "spell", "how do you say", "what does", "abbreviation",
    "yes or no", "true or false", "convert", "temperature",
}


def _classify_complexity(messages: list[ChatMessage]) -> str:
    """
    Week 1 heuristic classifier.
    Returns: "simple" | "medium" | "complex"

    Logic: check last user message for keywords.
    Defaults to "medium" when ambiguous (safer than guessing wrong tier).
    """
    # Get the last user message content
    user_messages = [m for m in messages if m.role == "user"]
    if not user_messages:
        return "medium"

    last_user_msg = user_messages[-1].content.lower()

    # Check complex keywords first (higher cost = be conservative)
    for keyword in COMPLEX_KEYWORDS:
        if keyword in last_user_msg:
            logger.debug(f"Classified as COMPLEX (keyword: '{keyword}')")
            return "complex"

    # Check simple keywords
    for keyword in SIMPLE_KEYWORDS:
        if keyword in last_user_msg:
            logger.debug(f"Classified as SIMPLE (keyword: '{keyword}')")
            return "simple"

    # Default: medium (safe middle ground)
    logger.debug("Classified as MEDIUM (default)")
    return "medium"


# ─── Cache Stub (Week 2 will fill this in) ───────────────────────────────────

async def _check_cache(messages: list[ChatMessage]) -> str | None:
    """
    Week 1 stub — always returns None (cache miss).
    Week 2 replaces this with Redis cosine similarity lookup.
    """
    return None


async def _store_cache(messages: list[ChatMessage], response_text: str) -> None:
    """
    Week 1 stub — no-op.
    Week 2 replaces this with Redis embedding storage.
    """
    pass


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
      1. Check semantic cache (stub in Week 1)
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
        costs = compute_costs(tier="simple", input_tokens=0, output_tokens=0, cache_hit=True)

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

    # ── Step 3: Call Model ───────────────────────────────────────────────────
    fallback_used = False
    llm_response: LLMResponse | None = None

    # Try Groq first
    try:
        llm_response = await call_model(
            tier=tier,
            messages=request.messages,
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens,
            use_ollama=False,
        )
    except LLMError as groq_error:
        logger.warning(f"Groq failed for tier={tier}: {groq_error}")

        # Fallback to Ollama if enabled
        fallback_enabled = os.getenv("FALLBACK_TO_OLLAMA", "true").lower() == "true"
        if fallback_enabled:
            logger.info(f"Attempting Ollama fallback for tier={tier}")
            try:
                llm_response = await call_model(
                    tier=tier,
                    messages=request.messages,
                    temperature=request.temperature or 0.7,
                    max_tokens=request.max_tokens,
                    use_ollama=True,
                )
                fallback_used = True
                logger.info(f"Ollama fallback succeeded for tier={tier}")
            except LLMError as ollama_error:
                logger.error(f"Ollama fallback also failed: {ollama_error}")
                raise groq_error   # raise original Groq error to caller

        else:
            raise groq_error

    latency_ms = (time.perf_counter() - start_time) * 1000

    # ── Step 4: Compute Costs ────────────────────────────────────────────────
    costs = compute_costs(
        tier=tier,
        input_tokens=llm_response["input_tokens"],
        output_tokens=llm_response["output_tokens"],
        cache_hit=False,
    )

    # ── Step 5: Store in cache for next time (stub in Week 1) ────────────────
    await _store_cache(request.messages, llm_response["content"])

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
