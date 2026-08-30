"""
scorer_prototype.py — REJECTED PROTOTYPE. Not wired into the gateway.

This file is preserved documentation, not live code. It was briefly imported as
`gateway/scorer.py`; it is parked here so the rework can start from real code.
Do NOT re-import it without fixing defects D1-D6 first.

    Verdict + measurements: docs/proposals/multi-dimensional-scorer.md

Known-broken as written:
  D1  _token_score is inverted vs its own comment — favours 'complex' at EVERY
      token count, making 25% of the weight a permanent vote for the priciest tier.
  D2  _TIER_MAX_TOKENS holds output generation caps, not context windows. All three
      Groq models hold 128K+; this compares input length against an output cap.
  D3  _TIER_COST_RATES is non-monotone in price (medium reads cheaper than simple),
      so a tighter cost budget routes to the BIGGER model.
  D4  score() returns a winner/runner-up margin ratio bounded in [0.5, 1.0]. The
      old router blended it into classifier_confidence with max(), overwriting
      nearly every real value (mean 0.33) with ~0.55.
  D5  Invisible to evals/run_eval.py, which calls classify() directly.
  D6  Duplicates tier facts that providers/model_config.py owns.

Original design intent (the part still worth building) — route on 5 dimensions
instead of complexity alone:
  1. Complexity (semantic-router) — 35% weight
  2. Token count (request length) — 25% weight
  3. Conversation history depth — 15% weight
  4. Latency budget (X-Latency-Budget-Ms header) — 15% weight
  5. Cost budget (X-Cost-Budget-Usd header) — 10% weight

The scorer is transparent (not a black-box ML model) — each dimension
contributes a weighted score per tier, and the highest-scoring tier wins.
Weights are hand-tuned and can be adjusted via environment variables.
"""

import logging
import os
from typing import Optional

from gateway.models import ChatRequest, ChatMessage

logger = logging.getLogger(__name__)

# ─── Configurable weights (sum to 1.0) ────────────────────────────────────────
# Override via env vars: SCORER_WEIGHT_COMPLEXITY=0.40 etc.
_WEIGHTS = {
    "complexity": float(os.getenv("SCORER_WEIGHT_COMPLEXITY", "0.35")),
    "token_fit": float(os.getenv("SCORER_WEIGHT_TOKEN_FIT", "0.25")),
    "history": float(os.getenv("SCORER_WEIGHT_HISTORY", "0.15")),
    "latency": float(os.getenv("SCORER_WEIGHT_LATENCY", "0.15")),
    "cost": float(os.getenv("SCORER_WEIGHT_COST", "0.10")),
}

# ─── Tier context limits (from providers/model_config.py) ────────────────────
_TIER_MAX_TOKENS = {
    "simple": 1024,
    "medium": 2048,
    "complex": 4096,
}

# ─── Tier typical latency ranges (ms) — used for latency budget scoring ──────
_TIER_TYPICAL_LATENCY = {
    "simple": 150,
    "medium": 400,
    "complex": 800,
}

# ─── Tier theoretical cost rates (per 1K tokens) — for cost budget ─────────
_TIER_COST_RATES = {
    "simple": 0.00025,   # input rate
    "medium": 0.00015,
    "complex": 0.00500,
}


class RoutingScorer:
    """
    Scores each tier on 5 dimensions and returns the best-matching tier.

    Usage:
        scorer = RoutingScorer()
        tier, confidence = scorer.score(request, classifier_tier, classifier_confidence)
    """

    def __init__(self) -> None:
        self.weights = _WEIGHTS.copy()
        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            for k in self.weights:
                self.weights[k] /= total
        logger.info(f"RoutingScorer initialized with weights: {self.weights}")

    def score(
        self,
        request: ChatRequest,
        classifier_tier: str,
        classifier_confidence: float,
    ) -> tuple[str, float]:
        """
        Score all tiers and return the best one with a confidence score.

        Args:
            request: The incoming ChatRequest
            classifier_tier: The tier from semantic-router
            classifier_confidence: Confidence from semantic-router [0, 1]

        Returns:
            (best_tier, confidence) where confidence is [0, 1]
        """
        # Extract request features
        token_count = self._estimate_tokens(request.messages)
        history_depth = len(request.messages)
        latency_budget = self._get_latency_budget(request)
        cost_budget = self._get_cost_budget(request)

        scores = {}
        for tier in ("simple", "medium", "complex"):
            scores[tier] = (
                self._complexity_score(tier, classifier_tier, classifier_confidence)
                * self.weights["complexity"]
                + self._token_score(tier, token_count)
                * self.weights["token_fit"]
                + self._history_score(tier, history_depth)
                * self.weights["history"]
                + self._latency_score(tier, latency_budget)
                * self.weights["latency"]
                + self._cost_score(tier, cost_budget, token_count)
                * self.weights["cost"]
            )

        best_tier = max(scores, key=scores.get)
        # Confidence = how much the winner beat the runner-up, normalized
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
            confidence = min(1.0, sorted_scores[0] / (sorted_scores[0] + sorted_scores[1]))
        else:
            confidence = classifier_confidence

        logger.debug(
            f"Scorer: tier={best_tier} confidence={confidence:.3f} "
            f"scores={scores} tokens={token_count} history={history_depth} "
            f"latency_budget={latency_budget} cost_budget={cost_budget}"
        )

        return (best_tier, round(confidence, 4))

    # ─── Dimension scorers (each returns [0, 1]) ──────────────────────────────

    def _complexity_score(self, tier: str, classifier_tier: str, confidence: float) -> float:
        """How well the tier matches the classifier's recommendation."""
        if tier == classifier_tier:
            return confidence  # Direct match — use classifier confidence
        # Partial credit for adjacent tiers
        tier_order = {"simple": 0, "medium": 1, "complex": 2}
        distance = abs(tier_order[tier] - tier_order[classifier_tier])
        return max(0.0, confidence * (1.0 - distance * 0.5))

    def _token_score(self, tier: str, token_count: int) -> float:
        """How well the tier's context window fits the token count."""
        max_tokens = _TIER_MAX_TOKENS.get(tier, 1024)
        if token_count <= max_tokens:
            # Fits comfortably — higher score for smaller tiers (cheaper)
            utilization = token_count / max_tokens
            return 1.0 - utilization * 0.3  # 0.7 to 1.0 range
        # Doesn't fit — penalize heavily
        overflow = (token_count - max_tokens) / max_tokens
        return max(0.0, 0.3 - overflow * 0.1)

    def _history_score(self, tier: str, history_depth: int) -> float:
        """Longer conversations need more capable models."""
        if history_depth <= 2:
            # Short conversation — simple tier is fine
            return {"simple": 1.0, "medium": 0.6, "complex": 0.3}.get(tier, 0.5)
        elif history_depth <= 6:
            # Medium conversation
            return {"simple": 0.5, "medium": 1.0, "complex": 0.6}.get(tier, 0.5)
        else:
            # Long conversation — complex tier preferred
            return {"simple": 0.2, "medium": 0.7, "complex": 1.0}.get(tier, 0.5)

    def _latency_score(self, tier: str, latency_budget: Optional[float]) -> float:
        """If user specified a latency budget, prefer faster tiers."""
        if latency_budget is None:
            return 0.5  # No budget — neutral

        typical = _TIER_TYPICAL_LATENCY.get(tier, 400)
        if typical <= latency_budget:
            return 1.0  # Fits within budget
        # Penalize tiers that exceed the budget
        return max(0.0, 1.0 - (typical - latency_budget) / latency_budget)

    def _cost_score(self, tier: str, cost_budget: Optional[float], token_count: int) -> float:
        """If user specified a cost budget, prefer cheaper tiers."""
        if cost_budget is None:
            return 0.5  # No budget — neutral

        rate = _TIER_COST_RATES.get(tier, 0.001)
        estimated_cost = (token_count / 1000) * rate
        if estimated_cost <= cost_budget:
            return 1.0  # Fits within budget
        return max(0.0, 1.0 - (estimated_cost - cost_budget) / cost_budget)

    # ─── Feature extractors ──────────────────────────────────────────────────

    def _estimate_tokens(self, messages: list[ChatMessage]) -> int:
        """Estimate token count from message content (~4 chars per token)."""
        total_chars = sum(len(m.content) for m in messages)
        return max(1, total_chars // 4)

    def _get_latency_budget(self, request: ChatRequest) -> Optional[float]:
        """Extract latency budget from request (if set via header/env)."""
        # In a real implementation, this would read from request headers
        # For now, return None (no budget specified)
        return None

    def _get_cost_budget(self, request: ChatRequest) -> Optional[float]:
        """Extract cost budget from request (if set via header/env)."""
        # In a real implementation, this would read from request headers
        # For now, return None (no budget specified)
        return None
