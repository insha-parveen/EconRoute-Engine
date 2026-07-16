"""
tracking/db.py — Async PostgreSQL persistence for request logs (Week 4).

Design:
  - One request → one row in `request_logs`. This is the history the dashboard reads.
  - SQLAlchemy 2.0 async engine + asyncpg driver (DATABASE_URL from env).
  - Engine + sessionmaker are module-level singletons (same rationale as the Redis
    client in gateway/cache.py: per-request engines leak connection pools).
  - Every public coroutine is BEST-EFFORT: a logging/DB failure must never break the
    response already computed for the user. Errors are caught + logged, never raised.
    (Same contract as gateway.cache.store.)

Schema note:
  We store `query_id` (sha256 hash), NEVER the raw query text — raw prompts are PII.
  This mirrors the gateway/cache.py::_query_id convention.

Table creation:
  init_db() runs Base.metadata.create_all at startup (create_all is idempotent).
  No Alembic this week — see CLAUDE.md decisions log.
"""

import logging
import os

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    func,
    select,
    text,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

logger = logging.getLogger(__name__)


# ─── URL normalisation ───────────────────────────────────────────────────────
def _async_url() -> str:
    """
    Resolve DATABASE_URL and coerce it to an async (asyncpg) driver.

    The gateway's engine is async, but env vars in the wild are often plain
    'postgresql://...' (e.g. a Supabase connection string) which SQLAlchemy loads
    with the SYNC psycopg2 dialect → 'requires an async driver' error. We rewrite
    the scheme to '+asyncpg' so the same URL works for the async gateway.
    """
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://econroute:econroute@postgres:5432/econroute",
    )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):  # some providers still emit the legacy scheme
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# ─── Engine + session (lazy singletons) ──────────────────────────────────────
# Created on first use, NOT at import time. Import-time creation would crash the
# whole gateway (and test collection) if the driver/URL were misconfigured; the
# lazy getter lets init_db/log_request/check_db catch that in their try/except and
# degrade gracefully (logging is best-effort, never a hard dependency).
_engine: AsyncEngine | None = None
_Session: async_sessionmaker[AsyncSession] | None = None


def _get_session() -> async_sessionmaker[AsyncSession]:
    """Build (once) and return the sessionmaker. Raises if the driver/URL is bad."""
    global _engine, _Session
    if _Session is None:
        # echo=False: SQLAlchemy's query logging is noisy; we log our own summary.
        _engine = create_async_engine(_async_url(), echo=False, pool_pre_ping=True)
        _Session = async_sessionmaker(_engine, expire_on_commit=False)
    return _Session


class Base(DeclarativeBase):
    pass


class RequestLog(Base):
    """One row per routed request — the analytics fact table the dashboard reads."""

    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Correlation / privacy
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    query_id: Mapped[str] = mapped_column(String(128))  # sha256 hash, never raw text

    # Routing decision
    tier: Mapped[str] = mapped_column(String(16), index=True)   # cache|simple|medium|complex
    model_used: Mapped[str] = mapped_column(String(128))
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    # Human-readable why: "cache · cosine match" | "classifier · simple" | "fallback · ollama"
    routing_reason: Mapped[str] = mapped_column(String(512), default="")
    classifier_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Performance
    latency_ms: Mapped[float] = mapped_column(Float)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Economics
    actual_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    theoretical_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    savings_usd: Mapped[float] = mapped_column(Float, default=0.0)
    savings_source: Mapped[str] = mapped_column(String(16), default="routing")


# ─── Lifecycle ───────────────────────────────────────────────────────────────

async def init_db() -> None:
    """
    Create tables if they don't exist. Called once from the FastAPI lifespan.

    Best-effort: if Postgres is unreachable at startup we log a warning and let the
    gateway boot anyway — request logging is an analytics feature, not a hard
    dependency of serving inference.
    """
    try:
        _get_session()  # ensure engine is built
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # create_all never alters existing tables; add Week-5 columns in place.
            # IF NOT EXISTS keeps this idempotent (our no-Alembic stance, see CLAUDE.md).
            # Add columns for week-5 features (IF NOT EXISTS = idempotent)
            await conn.execute(text(
                "ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS "
                "routing_reason VARCHAR(512) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS "
                "classifier_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0"
            ))
        logger.info("✅ Postgres ready — request_logs table ensured")
    except Exception as e:
        logger.warning(
            f"⚠️  init_db skipped — Postgres unreachable ({type(e).__name__}: {e}). "
            f"Gateway will run; request logging disabled until DB is back."
        )


async def dispose_engine() -> None:
    """Dispose the connection pool on shutdown (mirror of cache.close_redis)."""
    if _engine is None:
        return  # never built — nothing to dispose
    try:
        await _engine.dispose()
        logger.info("Postgres engine disposed")
    except Exception as e:
        logger.warning(f"Engine dispose failed — {type(e).__name__}: {e}")


async def check_db() -> str:
    """Health probe: 'connected' if SELECT 1 succeeds, else 'error'."""
    try:
        _get_session()  # ensure engine is built
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "connected"
    except Exception as e:
        logger.warning(f"DB health check failed — {type(e).__name__}: {e}")
        return "error"


# ─── Write path ──────────────────────────────────────────────────────────────

async def log_request(
    *,
    request_id: str,
    query_id: str,
    tier: str,
    model_used: str,
    cache_hit: bool,
    fallback_used: bool,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
    actual_cost_usd: float,
    theoretical_cost_usd: float,
    baseline_cost_usd: float,
    savings_usd: float,
    savings_source: str,
    routing_reason: str = "",
    classifier_confidence: float = 0.0,
) -> None:
    """
    Insert one request row. BEST-EFFORT — swallows all errors.

    A DB write failure must never surface to the caller: the user already has their
    response, and a dropped analytics row is preferable to a failed request.
    """
    try:
        Session = _get_session()
        async with Session() as session:
            session.add(
                RequestLog(
                    request_id=request_id,
                    query_id=query_id,
                    tier=tier,
                    model_used=model_used,
                    cache_hit=cache_hit,
                    fallback_used=fallback_used,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    actual_cost_usd=actual_cost_usd,
                    theoretical_cost_usd=theoretical_cost_usd,
                    baseline_cost_usd=baseline_cost_usd,
                    savings_usd=savings_usd,
                    savings_source=savings_source,
                    routing_reason=routing_reason,
                    classifier_confidence=classifier_confidence,
                )
            )
            await session.commit()
    except Exception as e:
        logger.warning(f"Request log write skipped — {type(e).__name__}: {e}")


# ─── Read path (Week 5 — analytics endpoints) ────────────────────────────────

async def fetch_logs(
    limit: int | None = None,
    *,
    since: object | None = None,
    offset: int = 0,
    tier: str | None = None,
    cache_hits_only: bool = False,
    fallback_only: bool = False,
) -> list["RequestLog"]:
    """
    Read request rows, newest first. Best-effort: returns [] on any DB error or
    empty table so the analytics endpoints can always return a valid 200 payload
    (same contract as log_request — an analytics read must never 500).

    Args:
        since: datetime lower bound on created_at (time-range pills: today/7d/30d).
        limit/offset: server-side pagination for the history table.
        tier / cache_hits_only / fallback_only: history table filters.
    """
    try:
        Session = _get_session()
        async with Session() as session:
            stmt = select(RequestLog).order_by(RequestLog.created_at.desc())
            if since is not None:
                stmt = stmt.where(RequestLog.created_at >= since)
            if tier:
                stmt = stmt.where(RequestLog.tier == tier)
            if cache_hits_only:
                stmt = stmt.where(RequestLog.cache_hit.is_(True))
            if fallback_only:
                stmt = stmt.where(RequestLog.fallback_used.is_(True))
            if offset:
                stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows)
    except Exception as e:
        logger.warning(f"fetch_logs skipped — {type(e).__name__}: {e}")
        return []


async def count_logs(
    *,
    since: object | None = None,
    tier: str | None = None,
    cache_hits_only: bool = False,
    fallback_only: bool = False,
) -> int:
    """Row count matching the same filters as fetch_logs (for pagination). Best-effort → 0."""
    try:
        Session = _get_session()
        async with Session() as session:
            stmt = select(func.count()).select_from(RequestLog)
            if since is not None:
                stmt = stmt.where(RequestLog.created_at >= since)
            if tier:
                stmt = stmt.where(RequestLog.tier == tier)
            if cache_hits_only:
                stmt = stmt.where(RequestLog.cache_hit.is_(True))
            if fallback_only:
                stmt = stmt.where(RequestLog.fallback_used.is_(True))
            return int((await session.execute(stmt)).scalar_one())
    except Exception as e:
        logger.warning(f"count_logs skipped — {type(e).__name__}: {e}")
        return 0
