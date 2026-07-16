"""
dashboard/queries.py — Read-only analytics queries for the EconRoute dashboard.

Synchronous psycopg2 queries consumed by the Next.js frontend (via /v1/stats
and /v1/requests) and the Streamlit dashboard (dashboard/app.py).

Design:
  - Pure functions: take a sync engine, return dicts/DataFrames.
  - All queries accept an optional `since` filter for time-range pills.
  - Best-effort: return empty/zero payloads on any DB error.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def since_from_range(range_key: str | None = None) -> datetime | None:
    """Map UI time-range pills to a lower-bound datetime. None = all time."""
    now = datetime.now(timezone.utc)
    if range_key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_key == "7d":
        return now - timedelta(days=7)
    if range_key == "30d":
        return now - timedelta(days=30)
    return None  # "all" / unknown


def _make_time_clause(since: datetime | None) -> str:
    """Return a SQL WHERE fragment and any params for the `since` filter."""
    if since is None:
        return "", {}
    return "AND created_at >= :since", {"since": since}


# ─── KPI totals ──────────────────────────────────────────────────────────────

def get_totals(engine: Any, since: datetime | None = None) -> dict[str, Any]:
    """Aggregate KPIs: request count, savings, baseline, cache rate, fallback rate."""
    time_clause, params = _make_time_clause(since)
    query = text(f"""
        SELECT
            COUNT(*)                                           AS requests,
            COALESCE(SUM(savings_usd), 0)                      AS savings_usd,
            COALESCE(SUM(baseline_cost_usd), 0)                AS baseline_usd,
            COALESCE(AVG(CASE WHEN cache_hit THEN 1 ELSE 0 END), 0) AS cache_hit_rate,
            COALESCE(AVG(CASE WHEN fallback_used THEN 1 ELSE 0 END), 0) AS fallback_rate
        FROM request_logs
        WHERE 1=1 {time_clause}
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, params).mappings().one()
            requests = row["requests"]
            baseline = row["baseline_usd"]
            savings = row["savings_usd"]
            return {
                "requests": requests,
                "savings_usd": round(savings, 8),
                "baseline_usd": round(baseline, 8),
                "savings_pct": round(savings / baseline * 100, 2) if baseline else 0.0,
                "cache_hit_rate": round(row["cache_hit_rate"] * 100, 2),
                "fallback_rate": round(row["fallback_rate"] * 100, 2),
                "actual_spend": 0.0,
            }
    except Exception as e:
        logger.warning(f"get_totals failed — {e}")
        return {"requests": 0, "savings_usd": 0.0, "baseline_usd": 0.0,
                "savings_pct": 0.0, "cache_hit_rate": 0.0, "fallback_rate": 0.0, "actual_spend": 0.0}


# ─── Tier distribution ───────────────────────────────────────────────────────

def get_tier_distribution(engine: Any, since: datetime | None = None) -> list[dict[str, Any]]:
    """Count of requests per routing tier."""
    time_clause, params = _make_time_clause(since)
    query = text(f"""
        SELECT tier, COUNT(*) AS count
        FROM request_logs
        WHERE 1=1 {time_clause}
        GROUP BY tier
        ORDER BY count DESC
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"get_tier_distribution failed — {e}")
        return []


# ─── Model distribution (actual models served) ───────────────────────────────

_KNOWN_MODELS = [
    "groq/openai/gpt-oss-20b",
    "groq/llama-3.3-70b-versatile",
    "groq/openai/gpt-oss-120b",
    "ollama (fallback)",
]


def get_model_distribution(engine: Any, since: datetime | None = None) -> list[dict[str, Any]]:
    """Traffic per ACTUAL model served, excluding cache hits. Always renders
    every known model even at 0% so the fallback path stays visible."""
    time_clause, params = _make_time_clause(since)
    query = text(f"""
        SELECT
            CASE WHEN model_used LIKE 'ollama%%' THEN 'ollama (fallback)' ELSE model_used END AS model,
            COUNT(*) AS count
        FROM request_logs
        WHERE cache_hit = false {time_clause}
        GROUP BY model
        ORDER BY count DESC
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
            model_counts = {r["model"]: r["count"] for r in rows}
            served_total = sum(model_counts.values())
            result = []
            for m in _KNOWN_MODELS:
                count = model_counts.get(m, 0)
                result.append({
                    "model": m,
                    "count": count,
                    "pct": round(count / served_total * 100, 1) if served_total else 0.0,
                })
            # Add any unknown models
            seen = set(model_counts) | set(_KNOWN_MODELS)
            for m in sorted(seen - set(_KNOWN_MODELS)):
                count = model_counts[m]
                result.append({
                    "model": m,
                    "count": count,
                    "pct": round(count / served_total * 100, 1) if served_total else 0.0,
                })
            return result
    except Exception as e:
        logger.warning(f"get_model_distribution failed — {e}")
        return [{"model": m, "count": 0, "pct": 0.0} for m in _KNOWN_MODELS]


# ─── Savings split (cache vs routing) ────────────────────────────────────────

def get_savings_split(engine: Any, since: datetime | None = None) -> dict[str, Any]:
    """Where savings came from: cache hits vs cheaper-model routing."""
    time_clause, params = _make_time_clause(since)
    query = text(f"""
        SELECT
            COALESCE(SUM(CASE WHEN savings_source = 'cache' THEN savings_usd ELSE 0 END), 0) AS cache_usd,
            COALESCE(SUM(CASE WHEN savings_source = 'routing' THEN savings_usd ELSE 0 END), 0) AS routing_usd
        FROM request_logs
        WHERE 1=1 {time_clause}
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, params).mappings().one()
            total = row["cache_usd"] + row["routing_usd"]
            return {
                "cache_usd": round(row["cache_usd"], 8),
                "routing_usd": round(row["routing_usd"], 8),
                "cache_pct": round(row["cache_usd"] / total * 100, 1) if total else 0.0,
                "routing_pct": round(row["routing_usd"] / total * 100, 1) if total else 0.0,
            }
    except Exception as e:
        logger.warning(f"get_savings_split failed — {e}")
        return {"cache_usd": 0.0, "routing_usd": 0.0, "cache_pct": 0.0, "routing_pct": 0.0}


# ─── Request history (paginated, filterable, sortable) ───────────────────────

def get_request_history(
    engine: Any,
    page: int = 1,
    page_size: int = 5,
    since: datetime | None = None,
    tier: str | None = None,
    cache_hits_only: bool = False,
    fallback_only: bool = False,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    """Paginated request rows with total count. Default: 5 most recent."""
    clauses = ["1=1"]
    params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}
    if since:
        clauses.append("created_at >= :since")
        params["since"] = since
    if tier:
        clauses.append("tier = :tier")
        params["tier"] = tier
    if cache_hits_only:
        clauses.append("cache_hit = true")
    if fallback_only:
        clauses.append("fallback_used = true")

    where = " AND ".join(clauses)
    valid_sort = {"created_at", "tier", "model_used", "latency_ms", "savings_usd"}
    sort_col = sort_by if sort_by in valid_sort else "created_at"
    sort_d = "DESC" if sort_dir == "desc" else "ASC"

    data_query = text(f"""
        SELECT created_at, tier, model_used, query_id, cache_hit, fallback_used,
               routing_reason, latency_ms, input_tokens, output_tokens,
               theoretical_cost_usd, baseline_cost_usd, savings_usd, savings_source
        FROM request_logs
        WHERE {where}
        ORDER BY {sort_col} {sort_d}
        LIMIT :limit OFFSET :offset
    """)
    count_query = text(f"SELECT COUNT(*) AS total FROM request_logs WHERE {where}")

    try:
        with engine.connect() as conn:
            rows = conn.execute(data_query, params).mappings().all()
            total = conn.execute(count_query, params).scalar() or 0
            return {
                "requests": [
                    {
                        "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                        "tier": r["tier"],
                        "model_used": r["model_used"],
                        "query_id": r["query_id"],
                        "cache_hit": r["cache_hit"],
                        "fallback_used": r["fallback_used"],
                        "routing_reason": r["routing_reason"] or "",
                        "latency_ms": float(r["latency_ms"]),
                        "input_tokens": int(r["input_tokens"]),
                        "output_tokens": int(r["output_tokens"]),
                        "theoretical_cost_usd": float(r["theoretical_cost_usd"]),
                        "baseline_cost_usd": float(r["baseline_cost_usd"]),
                        "savings_usd": float(r["savings_usd"]),
                        "savings_source": r["savings_source"],
                    }
                    for r in rows
                ],
                "total": int(total),
                "page": page,
                "page_size": page_size,
            }
    except Exception as e:
        logger.warning(f"get_request_history failed — {e}")
        return {"requests": [], "total": 0, "page": page, "page_size": page_size}
