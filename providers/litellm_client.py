"""
providers/litellm_client.py — Async LiteLLM wrapper for Groq + Ollama.

Design:
  - Single async function call_model() used by gateway/router.py
  - LiteLLM handles the actual HTTP calls to Groq / Ollama
  - Returns a typed dict with response text + token counts
  - Raises LLMError on failure (caller handles fallback in Week 3)

Why LiteLLM?
  Without it: separate SDK per provider (groq SDK, ollama SDK, openai SDK...)
  With it:    one interface. Switch model = change the string. That's it.

  Example:
    litellm.acompletion(model="groq/llama-3.1-8b-instant", ...)  # Groq
    litellm.acompletion(model="ollama/llama3.1:8b", ...)          # Ollama
    Same code, different string.
"""

import logging
from typing import TypedDict

import litellm
from litellm import acompletion

from providers.model_config import GROQ_TIERS, OLLAMA_TIERS
from gateway.models import ChatMessage

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose logging — we handle our own
litellm.set_verbose = False


class LLMResponse(TypedDict):
    """Typed return value from call_model()."""
    content: str           # the assistant's reply text
    input_tokens: int      # prompt tokens used
    output_tokens: int     # completion tokens generated
    model_used: str        # full model string, e.g. "groq/llama-3.1-8b-instant"
    raw: object            # the raw LiteLLM response object (for debugging)


class LLMError(Exception):
    """Raised when Groq (or Ollama) returns an error or times out."""
    pass


async def call_model(
    tier: str,
    messages: list[ChatMessage],
    temperature: float = 0.7,
    max_tokens: int | None = None,
    use_ollama: bool = False,
) -> LLMResponse:
    """
    Call the appropriate model for the given tier.

    Args:
        tier        : "simple" | "medium" | "complex"
        messages    : conversation history (list of ChatMessage)
        temperature : sampling temperature (0.0 = deterministic, 2.0 = creative)
        max_tokens  : cap on output tokens. None = model default.
        use_ollama  : if True, use local Ollama instead of Groq

    Returns:
        LLMResponse TypedDict

    Raises:
        LLMError: on API error, timeout, or rate limit

    Edge cases:
        - usage stats missing from response → estimate from text length
        - empty content in response → return empty string (caller handles)
    """
    # ── Pick model config based on tier + provider ──────────────────────────
    if use_ollama:
        config = OLLAMA_TIERS[tier]
        model_str = config["model"]
        api_base = config.get("api_base", "http://localhost:11434")
    else:
        config = GROQ_TIERS[tier]
        model_str = config["model"]
        api_base = None   # Groq uses LiteLLM's default Groq endpoint

    # Respect tier max_tokens unless caller overrides
    effective_max_tokens = max_tokens or GROQ_TIERS[tier]["max_tokens"]

    # ── Convert Pydantic ChatMessage → plain dicts for LiteLLM ──────────────
    messages_dicts = [{"role": m.role, "content": m.content} for m in messages]

    logger.info(f"Calling {model_str} (tier={tier}, tokens_cap={effective_max_tokens})")

    try:
        kwargs: dict = {
            "model": model_str,
            "messages": messages_dicts,
            "temperature": temperature,
            "max_tokens": effective_max_tokens,
        }

        # Ollama needs an explicit api_base; Groq does not
        if api_base:
            kwargs["api_base"] = api_base

        # acompletion = async completion (non-blocking)
        response = await acompletion(**kwargs)

    except litellm.exceptions.RateLimitError as e:
        raise LLMError(f"Rate limit hit on {model_str}: {e}") from e
    except litellm.exceptions.APIConnectionError as e:
        raise LLMError(f"Connection error for {model_str}: {e}") from e
    except litellm.exceptions.Timeout as e:
        raise LLMError(f"Timeout calling {model_str}: {e}") from e
    except Exception as e:
        raise LLMError(f"Unexpected error calling {model_str}: {e}") from e

    # ── Extract content ──────────────────────────────────────────────────────
    content = response.choices[0].message.content or ""

    # ── Extract token counts (Groq returns these; Ollama may not) ───────────
    usage = getattr(response, "usage", None)
    if usage:
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
    else:
        # Fallback estimation when usage stats are missing
        prompt_text = " ".join(m["content"] for m in messages_dicts)
        input_tokens = len(prompt_text) // 4
        output_tokens = len(content) // 4
        logger.warning(f"No usage stats from {model_str} — estimated tokens")

    return LLMResponse(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_used=model_str,
        raw=response,
    )
