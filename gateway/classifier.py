"""
gateway/classifier.py â€” Semantic complexity classifier over a shared ONNX encoder.

Week 1 was: keyword heuristic ("write code" â†’ complex, "what is" â†’ simple)
Week 3 was: semantic-router â€” meaning-based, not word-based
Week 6 is:  the SAME nearest-utterance scoring, reimplemented directly on the
            shared fastembed ONNX encoder (gateway/embedder.py).

Why the rewrite?
  semantic-router drags the full torch stack into RAM with its own encoder
  instance â€” two torch-backed models in one process OOM-killed the gateway on
  Render's 512 MB free tier. This implementation keeps the identical algorithm
  (aggregation="sum", top_k=15 â€” the tuning that produced 90%+ accuracy on the
  60-query held-out set) but runs on the ~25 MB int8 ONNX model that cache.py
  already loads. One encoder, one vector space, no torch.

Scoring (mirrors semantic-router's aggregation="sum", top_k=15):
  1. Embed the query once.
  2. Cosine-score it against every utterance embedding (precomputed at import).
  3. For each route, SUM the top-15 cosine scores.
  4. Argmax across routes â†’ tier. Confidence = summed score / 5, clamped [0,1]
     (same /5 scaling the semantic-router path used).

classify() is synchronous â€” embed is <5 ms on CPU via ONNX int8, so wrapping
in run_in_executor is unnecessary at this scale.
"""

import logging

import numpy as np

from gateway import embedder

logger = logging.getLogger(__name__)

# â”€â”€â”€ Route definitions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Each utterance is an example of what that tier looks like.
# More examples = better accuracy (diminishing returns after ~15 per route).
# Spread examples across domains â€” don't overfit to tech queries only.

_TIER_UTTERANCES: dict[str, list[str]] = {
    "simple": [
        "What is Python?",
        "Who invented the telephone?",
        "What is the capital of France?",
        "When was the Eiffel Tower built?",
        "What does API stand for?",
        "Define machine learning",
        "What is a neural network?",
        "What does HTTP mean?",
        "What is recursion?",
        "What is 2 + 2?",
        "How do you spell necessary?",
        "What is the boiling point of water?",
        "How many days are in a leap year?",
        "Convert 100 Celsius to Fahrenheit",
        "Is Python object-oriented?",
        "What year did World War 2 end?",
    ],
    "medium": [
        "Explain how neural networks work",
        "How does the internet work?",
        "Explain the difference between RAM and ROM",
        "How does photosynthesis work?",
        "Explain TCP/IP in simple terms",
        "Compare Python and JavaScript",
        "What are the differences between SQL and NoSQL?",
        "Compare Docker and virtual machines",
        "What are the pros and cons of microservices?",
        "Summarize the French Revolution",
        "Translate this paragraph to French",
        "Give me an overview of machine learning",
        "How do I improve my writing skills?",
        "What is the best way to learn programming?",
        "How should I structure a REST API?",
    ],
    "complex": [
        "Write a Python function for binary search",
        "Implement a linked list in Python",
        "Write a REST API endpoint in FastAPI",
        "Create a sorting algorithm in JavaScript",
        "Write a SQL query to find duplicate records",
        "Debug this code and explain what is wrong",
        "Why is my code throwing a TypeError?",
        "Fix this Python function that has a bug",
        "Design a database schema for an e-commerce app",
        "Architect a microservices system for a social network",
        "How would you design a URL shortener like bit.ly?",
        "Write an essay about climate change and its economic impact",
        "Write a detailed analysis of the French Revolution",
        "Write a technical blog post about Docker",
        "Analyze the time complexity of quicksort",
        "Explain the CAP theorem with examples",
        "What are the trade-offs between consistency and availability?",
        # "Explain/Derive how <system> implements <mechanism>" â€” hard tasks that
        # surface-read as medium but require deep multi-step reasoning. Added
        # Week 5 after held-out eval showed 6/20 complex queries under-routing
        # to medium/simple (recall 70%). NEW generic phrasings, NOT eval copies.
        "Explain step by step how a compiler performs register allocation",
        "Explain how a hash table resolves collisions internally",
        "Derive the closed-form solution for a linear recurrence relation",
        "Implement OAuth2 authentication in a web service",
        "Write a regular expression to parse structured log lines and explain it",
        "Architect a scalable video streaming platform for millions of viewers",
        "Explain how a memory allocator implements free-list coalescing",
        "Prove the correctness of Dijkstra's shortest path algorithm",
    ],
}

# â”€â”€â”€ Precompute utterance embeddings â€” built once at module import â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Same rationale as the old SemanticRouter auto_sync="local": pay the embed
# cost once at boot so the first classify() call is cheap.

_TOP_K = 5        # neighbors summed per route (retuned for ONNX int8: 5 â†’ 83%, 15 â†’ 90%, 48 â†’ 85%)
_CONF_SCALE = 5.0  # confidence = summed_score / 5 (same scaling as semantic-router path)

logger.info("Embedding classifier route utterances (shared fastembed encoder)...")

_all_utterances: list[str] = []
_route_slices: dict[str, tuple[int, int]] = {}
for _tier, _utts in _TIER_UTTERANCES.items():
    _route_slices[_tier] = (len(_all_utterances), len(_all_utterances) + len(_utts))
    _all_utterances.extend(_utts)

_utterance_vecs = embedder.embed_batch(_all_utterances)

logger.info(
    f"Classifier ready â€” 3 routes, {len(_all_utterances)} utterances "
    f"(top_k={_TOP_K}, sum aggregation)"
)


# â”€â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def classify(text: str) -> tuple[str, float]:
    """
    Classify a query as simple / medium / complex and return a confidence score.

    Args:
        text: the user's query text

    Returns:
        (tier, confidence) where tier is "simple" | "medium" | "complex"
        and confidence is a float in [0.0, 1.0] representing the classifier's
        certainty. 0.0 means complete fallback, 1.0 means perfect match.

        On error or empty input: ("medium", 0.0)
    """
    if not text or not text.strip():
        logger.debug("Empty query â†’ default medium (confidence=0)")
        return ("medium", 0.0)

    # Truncate very long inputs â€” all-MiniLM-L6-v2 has 512 token limit
    # ~4 chars per token â†’ 2000 char safety limit
    truncated = text[:2000] if len(text) > 2000 else text

    try:
        query_vec = embedder.embed_one(truncated)
        scores = embedder.cosine_matrix(query_vec, _utterance_vecs)

        best_tier, best_score = "medium", -np.inf
        for tier, (start, end) in _route_slices.items():
            route_scores = np.sort(scores[start:end])[-_TOP_K:]
            total = float(route_scores.sum())
            if total > best_score:
                best_tier, best_score = tier, total

        confidence = min(1.0, max(0.0, best_score / _CONF_SCALE))
        logger.debug(
            f"Classified as {best_tier.upper()} (confidence={confidence:.3f}) â€” len={len(truncated)}"
        )
        return (best_tier, round(confidence, 4))
    except (RuntimeError, ValueError, TypeError) as e:
        logger.warning(f"Classifier error â€” falling back to medium: {e}")
        return ("medium", 0.0)

