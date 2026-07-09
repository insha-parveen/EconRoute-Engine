"""
tests/test_logging.py — best-effort contract of the Postgres write path.

The critical guarantee: a DB failure must NEVER surface to the caller. The user
already has their response; a dropped analytics row is acceptable, a raised
exception is not. We assert log_request returns cleanly even when Postgres is
unreachable — so no live database is required to run this test.
"""

import pytest

# The async write path needs asyncpg + pytest-asyncio (installed via
# requirements-dev.txt / in the Docker image). Skip cleanly where they're absent
# so `pytest` still runs the pure cost_calculator suite locally.
pytest.importorskip("asyncpg")
pytest.importorskip("pytest_asyncio")

from tracking.db import log_request


@pytest.mark.asyncio
async def test_log_request_swallows_db_errors():
    """With no reachable Postgres (CI / local), the insert must fail silently."""
    result = await log_request(
        request_id="chatcmpl-test123",
        query_id="sha256:deadbeef(len=5)",
        tier="simple",
        model_used="groq/openai/gpt-oss-20b",
        cache_hit=False,
        fallback_used=False,
        latency_ms=42.0,
        input_tokens=10,
        output_tokens=5,
        actual_cost_usd=0.0,
        theoretical_cost_usd=0.00001,
        baseline_cost_usd=0.0001,
        savings_usd=0.00009,
        savings_source="routing",
    )
    assert result is None  # returns cleanly, never raises
