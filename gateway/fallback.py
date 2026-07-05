"""
gateway/fallback.py — Groq → Ollama fallback chain with exponential backoff.

Week 1 had a simple try/except in router.py.
Week 3 replaces it with a proper fallback chain:

  1. Try Groq at classified tier
  2. On rate limit (429) → exponential backoff + retry (same tier)
  3. On timeout / other error → try next tier up
  4. All Groq tiers exhausted → Ollama fallback
  5. Ollama fails → raise original error → 503 to client

Why exponential backoff?
  Groq rate limits reset every minute (30 RPM free tier).
  Hammering the API immediately after a 429 wastes retries.
  Waiting 1s → 2s → 4s gives the server time to recover.
  `tenacity` handles this cleanly without manual sleep loops.

Why tier escalation on timeout (not on rate limit)?
  Rate limit = "slow down, server is fine"  → retry same tier
  Timeout    = "server busy / model slow"   → try bigger tier which
               may have different load, or try Ollama
"""

import logging
import os
import asyncio
from typing import Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from providers.litellm_client import call_model, LLMError, LLMResponse
from gateway.models import ChatMessage

logger = logging.getLogger(__name__)

# ─── Tier escalation order ────────────────────────────────────────────────────
# When a tier fails due to timeout/error (not rate limit), try the next tier.
# simple → medium → complex → Ollama

_TIER_ESCALATION = {
    "simple":  "medium",
    "medium":  "complex",
    "complex": None,          # no higher Groq tier → go to Ollama
}


# ─── Rate limit detection ─────────────────────────────────────────────────────

def _is_rate_limit(error: LLMError) -> bool:
    """Detect Groq 429 rate limit errors from LLMError message."""
    msg = str(error).lower()
    return "rate limit" in msg or "429" in msg or "ratelimit" in msg


def _is_deprecated(error: LLMError) -> bool:
    """Detect decommissioned/deprecated model errors."""
    msg = str(error).lower()
    return "decommissioned" in msg or "deprecated" in msg or "not supported" in msg


# ─── Single Groq call with backoff on rate limit ──────────────────────────────

async def _call_with_backoff(
    tier: str,
    messages: list[ChatMessage],
    temperature: float,
    max_tokens: Optional[int],
    max_retries: int = 3,
) -> LLMResponse:
    """
    Call Groq for a given tier with exponential backoff on rate limits.

    Retries up to max_retries times on 429.
    Raises LLMError immediately on timeout, deprecated model, or other errors
    so the caller can decide whether to escalate tier.

    Backoff: 1s → 2s → 4s (configurable via tenacity)
    """
    last_error: Optional[LLMError] = None

    for attempt in range(1, max_retries + 1):
        try:
            return await call_model(
                tier=tier,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                use_ollama=False,
            )
        except LLMError as e:
            last_error = e

            if _is_rate_limit(e):
                wait = 2 ** (attempt - 1)   # 1s, 2s, 4s
                logger.warning(
                    f"Groq rate limit on {tier} tier "
                    f"(attempt {attempt}/{max_retries}) — waiting {wait}s"
                )
                if attempt < max_retries:
                    await asyncio.sleep(wait)
                continue   # retry same tier

            # Not a rate limit — raise immediately for tier escalation
            raise

    # All retries exhausted on rate limit
    raise last_error


# ─── Ollama fallback ──────────────────────────────────────────────────────────

async def _call_ollama(
    tier: str,
    messages: list[ChatMessage],
    temperature: float,
    max_tokens: Optional[int],
) -> LLMResponse:
    """
    Try Ollama as last resort fallback.

    Uses same tier (simple→qwen2.5, medium→llama3.2, complex→llama3.1).
    Ollama must be running at OLLAMA_BASE_URL (host.docker.internal:11434).
    """
    fallback_enabled = os.getenv("FALLBACK_TO_OLLAMA", "true").lower() == "true"
    if not fallback_enabled:
        raise LLMError("Ollama fallback disabled (FALLBACK_TO_OLLAMA=false)")

    logger.info(f"Attempting Ollama fallback — tier={tier}")
    try:
        result = await call_model(
            tier=tier,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            use_ollama=True,
        )
        logger.info(f"Ollama fallback succeeded — tier={tier}")
        return result
    except LLMError as e:
        # Helpful message for the common Docker networking mistake
        if "connection" in str(e).lower() or "connect" in str(e).lower():
            logger.error(
                f"Ollama connection failed — is Ollama running? "
                f"On Docker: set OLLAMA_BASE_URL=http://host.docker.internal:11434 "
                f"(Windows/Mac) or http://172.17.0.1:11434 (Linux). Error: {e}"
            )
        else:
            logger.error(f"Ollama fallback failed — tier={tier}: {e}")
        raise


# ─── Main fallback chain ──────────────────────────────────────────────────────

async def call_with_fallback(
    tier: str,
    messages: list[ChatMessage],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> tuple[LLMResponse, str, bool]:
    """
    Call Groq with full fallback chain. Returns (response, tier_used, fallback_used).

    Chain:
      1. Try Groq at `tier` — with backoff on rate limits
      2. On timeout/error → escalate to next tier
      3. All Groq tiers exhausted → Ollama at original tier
      4. Ollama fails → raise original LLMError

    Args:
        tier        : starting tier ("simple" | "medium" | "complex")
        messages    : conversation history
        temperature : sampling temperature
        max_tokens  : optional output token cap

    Returns:
        (LLMResponse, tier_actually_used, was_ollama_fallback)

    Raises:
        LLMError: when all options exhausted
    """
    original_tier = tier
    current_tier: Optional[str] = tier
    first_error: Optional[LLMError] = None

    # ── Try Groq tiers in escalation order ────────────────────────────────
    while current_tier is not None:
        try:
            response = await _call_with_backoff(
                tier=current_tier,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if current_tier != original_tier:
                logger.info(
                    f"Tier escalated: {original_tier} → {current_tier} "
                    f"(Groq error on original tier)"
                )
            return response, current_tier, False

        except LLMError as e:
            if first_error is None:
                first_error = e

            next_tier = _TIER_ESCALATION.get(current_tier)

            if _is_deprecated(e):
                logger.warning(
                    f"Model deprecated on {current_tier} tier — "
                    f"escalating to {next_tier or 'Ollama'}"
                )
            elif next_tier:
                logger.warning(
                    f"Groq failed on {current_tier} tier — "
                    f"escalating to {next_tier}"
                )
            else:
                logger.warning(
                    f"Groq failed on {current_tier} tier (top tier) — "
                    f"trying Ollama"
                )

            current_tier = next_tier

    # ── All Groq tiers exhausted → try Ollama ─────────────────────────────
    try:
        response = await _call_ollama(
            tier=original_tier,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response, original_tier, True   # fallback_used=True

    except LLMError:
        # Raise the first Groq error (more informative than Ollama connection error)
        raise first_error
