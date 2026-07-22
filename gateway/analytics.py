"""
gateway/analytics.py — read-only analytics endpoints for the dashboard (Week 5).

The Next.js frontend runs in the browser and cannot read Postgres directly (the
Streamlit dashboard can, because it runs server-side). These two endpoints expose
the same aggregates Streamlit computes, so the numbers match bit-for-bit:

  GET /v1/stats             — KPI totals, tier distribution, latency percentiles,
                              cumulative-savings timeseries, cache hit/miss.
  GET /v1/requests?limit=N  — recent request rows (PII-safe: hashed query_id only).

Aggregation is done in pure Python over the full row set (mirrors dashboard/app.py).
At portfolio scale the table fits in memory and one SELECT guarantees parity with
Streamlit. If request_logs ever exceeds ~100k rows, push this into SQL
(percentile_cont WITHIN GROUP + GROUP BY + a windowed cumulative sum).

Best-effort: every endpoint returns a valid 200 with an empty/zero payload if the
DB is empty or unreachable — an analytics read must never surface a 500.
"""

import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from gateway.models import (
    CacheHitMiss,
    CumulativePoint,
    LatencyPercentile,
    ModelCount,
    RequestRow,
    RequestsResponse,
    SavingsSplit,
    StatsResponse,
    StatsTotals,
    TierCount,
)
from tracking.db import count_logs, fetch_logs

logger = logging.getLogger(__name__)

# NOTE: these are plain async functions, NOT an APIRouter. gateway/main.py wires
# them to @app.get endpoints directly. Registering via app.include_router() trips a
# bug in the installed prometheus-fastapi-instrumentator ('_IncludedRouter' object
# has no attribute 'path'), which walks app.routes on every request. The decorator
# path (used by all other endpoints) is unaffected.

# Cap on cumulative-savings points sent to the browser. Beyond this we downsample
# evenly but always keep the last point, so the final cumulative total is exact.
_MAX_TIMESERIES_POINTS = 200

# The three Groq tiers + the Ollama fallback. The model-distribution card always
# renders every one of these (even at 0 traffic) so the fallback path is visibly
# monitored. Source of truth: providers/model_config.py.
_KNOWN_MODELS = [
    "groq/openai/gpt-oss-20b",
    "groq/llama-3.3-70b-versatile",
    "groq/openai/gpt-oss-120b",
    "ollama (fallback)",
]


def since_from_range(range_key: str | None) -> datetime | None:
    """Map the UI's time-range pills to a created_at lower bound (None = all)."""
    now = datetime.now(timezone.utc)
    if range_key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_key == "7d":
        return now - timedelta(days=7)
    if range_key == "30d":
        return now - timedelta(days=30)
    return None  # "all" / unknown


def _distribution_key(model_used: str) -> str:
    """Collapse any ollama/* model into one fallback bucket; cache rows excluded."""
    return "ollama (fallback)" if model_used.startswith("ollama") else model_used


def _pandas_quantile(sorted_vals: list[float], q: float) -> float:
    """
    Replicate pandas' default 'linear' quantile interpolation so /v1/stats matches
    the Streamlit dashboard (df.quantile) exactly. `sorted_vals` must be ascending.
    """
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_vals[0])
    pos = q * (n - 1)          # 0-based virtual index
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


async def compute_stats(range_key: str | None = None) -> StatsResponse:
    """KPI totals + charts data for a time range. Empty/valid payload when no rows."""
    try:
        since = since_from_range(range_key)
        rows = await fetch_logs(since=since)  # full window, newest first
        if not rows:
            return StatsResponse()

        total = len(rows)
        total_savings = sum(r.savings_usd for r in rows)
        total_baseline = sum(r.baseline_cost_usd for r in rows)
        cache_hits = sum(1 for r in rows if r.cache_hit)
        fallbacks = sum(1 for r in rows if r.fallback_used)

        totals = StatsTotals(
            requests=total,
            savings_usd=round(total_savings, 8),
            baseline_usd=round(total_baseline, 8),
            savings_pct=round(total_savings / total_baseline * 100, 2) if total_baseline else 0.0,
            cache_hit_rate=round(cache_hits / total * 100, 2) if total else 0.0,
            fallback_rate=round(fallbacks / total * 100, 2) if total else 0.0,
            actual_spend=0.0,
        )

        # ── Tier distribution (routing decision) ─────────────────────────────
        tier_counts = Counter(r.tier for r in rows)
        tier_distribution = [TierCount(tier=t, count=c) for t, c in tier_counts.items()]

        # ── Model distribution (actual model traffic) ────────────────────────
        # Exclude cache rows (no model served). Always render every known model —
        # including ollama at 0 — so the fallback path stays visibly monitored.
        served = [r for r in rows if not r.cache_hit]
        model_counts = Counter(_distribution_key(r.model_used) for r in served)
        served_total = len(served)
        seen = set(model_counts) | set(_KNOWN_MODELS)
        model_distribution = [
            ModelCount(
                model=m,
                count=model_counts.get(m, 0),
                pct=round(model_counts.get(m, 0) / served_total * 100, 1) if served_total else 0.0,
            )
            for m in sorted(seen, key=lambda m: (m not in _KNOWN_MODELS, _KNOWN_MODELS.index(m) if m in _KNOWN_MODELS else 0))
        ]

        # ── Savings split: cache vs routing ──────────────────────────────────
        cache_savings = sum(r.savings_usd for r in rows if r.savings_source == "cache")
        routing_savings = total_savings - cache_savings
        savings_split = SavingsSplit(
            cache_usd=round(cache_savings, 8),
            routing_usd=round(routing_savings, 8),
            cache_pct=round(cache_savings / total_savings * 100, 1) if total_savings else 0.0,
            routing_pct=round(routing_savings / total_savings * 100, 1) if total_savings else 0.0,
        )

        # ── Latency percentiles per tier (pandas-linear parity) ──────────────
        by_tier: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            by_tier[r.tier].append(r.latency_ms)
        latency_percentiles = []
        for tier, vals in by_tier.items():
            vals.sort()
            latency_percentiles.append(
                LatencyPercentile(
                    tier=tier,
                    p50=round(_pandas_quantile(vals, 0.50), 1),
                    p95=round(_pandas_quantile(vals, 0.95), 1),
                    count=len(vals),
                )
            )

        # ── Cumulative savings over time (ascending), downsampled ────────────
        asc = sorted(rows, key=lambda r: r.created_at)
        running = 0.0
        full_series: list[CumulativePoint] = []
        for r in asc:
            running += r.savings_usd
            full_series.append(
                CumulativePoint(
                    timestamp=r.created_at.isoformat(),
                    cumulative_savings=round(running, 8),
                )
            )
        cumulative_savings = _downsample(full_series, _MAX_TIMESERIES_POINTS)

        cache_hit_vs_miss = CacheHitMiss(hit=cache_hits, miss=total - cache_hits)

        return StatsResponse(
            totals=totals,
            tier_distribution=tier_distribution,
            latency_percentiles=latency_percentiles,
            cumulative_savings=cumulative_savings,
            cache_hit_vs_miss=cache_hit_vs_miss,
            model_distribution=model_distribution,
            savings_split=savings_split,
        )
    except Exception as e:  # belt-and-suspenders on top of fetch_logs's own guard
        logger.warning(f"/v1/stats degraded to empty — {type(e).__name__}: {e}")
        return StatsResponse()


async def list_recent_requests(
    limit: int = 5,
    *,
    page: int = 1,
    range_key: str | None = None,
    tier: str | None = None,
    cache_hits_only: bool = False,
    fallback_only: bool = False,
) -> RequestsResponse:
    """
    Paginated, filtered request history. PII-safe: hashed query_id only.
    Default (page 1, limit 5, no filters) = the "at a glance" 5-most-recent view.
    """
    try:
        since = since_from_range(range_key)
        page = max(1, page)
        offset = (page - 1) * limit
        rows = await fetch_logs(
            limit=limit,
            offset=offset,
            since=since,
            tier=tier,
            cache_hits_only=cache_hits_only,
            fallback_only=fallback_only,
        )
        total = await count_logs(
            since=since,
            tier=tier,
            cache_hits_only=cache_hits_only,
            fallback_only=fallback_only,
        )
        return RequestsResponse(
            total=total,
            page=page,
            page_size=limit,
            requests=[
                RequestRow(
                    created_at=r.created_at.isoformat(),
                    tier=r.tier,
                    model_used=r.model_used,
                    query_id=r.query_id,
                    cache_hit=r.cache_hit,
                    fallback_used=r.fallback_used,
                    routing_reason=r.routing_reason or "",
                    latency_ms=r.latency_ms,
                    input_tokens=r.input_tokens,
                    output_tokens=r.output_tokens,
                    theoretical_cost_usd=r.theoretical_cost_usd,
                    baseline_cost_usd=r.baseline_cost_usd,
                    savings_usd=r.savings_usd,
                    savings_source=r.savings_source,
                )
                for r in rows
            ],
        )
    except Exception as e:
        logger.warning(f"/v1/requests degraded to empty — {type(e).__name__}: {e}")
        return RequestsResponse()


def _downsample(series: list[CumulativePoint], cap: int) -> list[CumulativePoint]:
    """Keep at most `cap` points, evenly spaced, but always include the last point
    so the final cumulative total stays exact."""
    n = len(series)
    if n <= cap:
        return series
    step = math.ceil(n / cap)
    sampled = series[::step]
    if sampled[-1] is not series[-1]:
        sampled.append(series[-1])
    return sampled
