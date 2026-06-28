"""
gateway/classifier.py — Semantic complexity classifier using semantic-router.

Week 1 was: keyword heuristic ("write code" → complex, "what is" → simple)
Week 3 is:  semantic-router — meaning-based, not word-based

Why semantic-router over keyword matching?
  Keyword: "Can you tell me about Python?" → no keyword match → "medium" (wrong)
  Semantic: query vector closest to "What is Python?" examples → "simple" (correct)

  Also handles multilingual, paraphrasing, and novel phrasings that
  keyword lists never anticipated.

Design:
  - HuggingFaceEncoder with all-MiniLM-L6-v2 (same model as cache.py — no extra download)
  - RouteLayer built once at module import (like cache._model — eager init)
  - classify() is synchronous (semantic-router is not async) — called from router.py
  - None result from RouteLayer → fallback to "medium" (safe default)

Route design rationale:
  simple  = factual lookups, definitions, single-fact questions
            → short output, no reasoning chain needed
            → 8B model sufficient
  medium  = explanations, comparisons, summaries, translations
            → paragraph-length output, some reasoning
            → 70B model appropriate
  complex = code generation, debugging, essays, analysis, design
            → long output, multi-step reasoning, quality matters
            → 120B flagship model
"""

import logging
import os
from typing import Optional

from semantic_router import Route, RouteLayer
from semantic_router.encoders import HuggingFaceEncoder

logger = logging.getLogger(__name__)

# ─── Route definitions ────────────────────────────────────────────────────────
# Each utterance is an example of what that tier looks like.
# More examples = better accuracy (diminishing returns after ~15 per route).
# Spread examples across domains — don't overfit to tech queries only.

_simple_route = Route(
    name="simple",
    utterances=[
        # Factual questions
        "What is Python?",
        "Who invented the telephone?",
        "What is the capital of France?",
        "When was the Eiffel Tower built?",
        "What does API stand for?",
        # Definitions
        "Define machine learning",
        "What is a neural network?",
        "What does HTTP mean?",
        "What is recursion?",
        # Simple lookups
        "What is 2 + 2?",
        "How do you spell necessary?",
        "What is the boiling point of water?",
        "How many days are in a leap year?",
        # Conversions / yes-no
        "Convert 100 Celsius to Fahrenheit",
        "Is Python object-oriented?",
        "What year did World War 2 end?",
    ],
)

_medium_route = Route(
    name="medium",
    utterances=[
        # Explanations
        "Explain how neural networks work",
        "How does the internet work?",
        "Explain the difference between RAM and ROM",
        "How does photosynthesis work?",
        "Explain TCP/IP in simple terms",
        # Comparisons
        "Compare Python and JavaScript",
        "What are the differences between SQL and NoSQL?",
        "Compare Docker and virtual machines",
        "What are the pros and cons of microservices?",
        # Summaries and translations
        "Summarize the French Revolution",
        "Translate this paragraph to French",
        "Give me an overview of machine learning",
        # How-to (conceptual, not code)
        "How do I improve my writing skills?",
        "What is the best way to learn programming?",
        "How should I structure a REST API?",
    ],
)

_complex_route = Route(
    name="complex",
    utterances=[
        # Code generation
        "Write a Python function for binary search",
        "Implement a linked list in Python",
        "Write a REST API endpoint in FastAPI",
        "Create a sorting algorithm in JavaScript",
        "Write a SQL query to find duplicate records",
        # Debugging
        "Debug this code and explain what is wrong",
        "Why is my code throwing a TypeError?",
        "Fix this Python function that has a bug",
        # Design and architecture
        "Design a database schema for an e-commerce app",
        "Architect a microservices system for a social network",
        "How would you design a URL shortener like bit.ly?",
        # Long-form writing
        "Write an essay about climate change and its economic impact",
        "Write a detailed analysis of the French Revolution",
        "Write a technical blog post about Docker",
        # Deep analysis
        "Analyze the time complexity of quicksort",
        "Explain the CAP theorem with examples",
        "What are the trade-offs between consistency and availability?",
    ],
)

# ─── Encoder + RouteLayer — built once at module import ──────────────────────
# HuggingFaceEncoder reuses all-MiniLM-L6-v2 — same model as cache.py.
# Already downloaded to /app/.cache at Docker build time — zero extra cost.

logger.info("Building semantic-router RouteLayer (all-MiniLM-L6-v2)...")

_encoder = HuggingFaceEncoder(name="sentence-transformers/all-MiniLM-L6-v2")

_route_layer = RouteLayer(
    encoder=_encoder,
    routes=[_simple_route, _medium_route, _complex_route],
)

logger.info("RouteLayer ready — 3 routes: simple / medium / complex")


# ─── Public API ───────────────────────────────────────────────────────────────

def classify(text: str) -> str:
    """
    Classify a query as simple / medium / complex.

    Args:
        text: the user's query text

    Returns:
        "simple" | "medium" | "complex"

    Fallback:
        Any error or None result → "medium" (safe default — never over-routes
        to simple and risks quality loss, never wastes complex on trivia)

    Note:
        semantic-router is synchronous — not async. Called from the async
        router.py context but completes fast enough (<5ms on CPU) that
        wrapping in run_in_executor is not necessary at this scale.
        Add executor wrapping if p99 latency becomes a concern at high QPS.
    """
    if not text or not text.strip():
        logger.debug("Empty query → default medium")
        return "medium"

    # Truncate very long inputs — all-MiniLM-L6-v2 has 512 token limit
    # ~4 chars per token → 2000 char safety limit
    truncated = text[:2000] if len(text) > 2000 else text

    try:
        result = _route_layer(truncated)
        tier = result.name if result and result.name else "medium"
        logger.debug(f"Classified as {tier.upper()} — len={len(truncated)}")
        return tier
    except Exception as e:
        logger.warning(f"Classifier error — falling back to medium: {e}")
        return "medium"
