"""
gateway/main.py — FastAPI application entry point.

Endpoints:
  POST /v1/chat/completions  — OpenAI-compatible chat endpoint (main product)
  GET  /health               — checks Redis, DB, Groq connectivity
  GET  /metrics              — Prometheus metrics scrape endpoint

Design principles:
  - main.py is a thin shell. All logic lives in router.py.
  - Global exception handlers return clean JSON (never HTML error pages).
  - Lifespan context manager handles startup/shutdown tasks cleanly.

OpenAI compatibility:
  Any code using the OpenAI Python SDK works unchanged if you set:
    client = OpenAI(api_key="not-needed", base_url="http://localhost:8000/v1")
"""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from gateway.cache import check_redis, close_redis
from gateway.models import ChatRequest, ChatResponse, HealthResponse
from gateway.router import route
from providers.litellm_client import LLMError
from tracking.db import check_db, dispose_engine, init_db
from websocket.manager import manager

# ─── Logging Setup ────────────────────────────────────────────────────────────
# Do this before anything else so all modules inherit the config.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────
# FastAPI lifespan replaces deprecated @app.on_event("startup") pattern.
# Put one-time setup here: DB pool init, model loading, cache warmup etc.

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────────────────────
    logger.info("=" * 55)
    logger.info("  EconRoute Gateway — starting up")
    logger.info("=" * 55)

    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key or groq_key == "gsk_your_key_here":
        logger.warning("⚠️  GROQ_API_KEY not set — Groq calls will fail!")
        logger.warning("   Get a free key at https://console.groq.com")
    else:
        logger.info(f"✅ GROQ_API_KEY loaded (gsk_...{groq_key[-4:]})")

    logger.info(f"✅ Simple  model : {os.getenv('SIMPLE_MODEL',  'groq/llama-3.1-8b-instant')}")
    logger.info(f"✅ Medium  model : {os.getenv('MEDIUM_MODEL',  'groq/llama-3.3-70b-versatile')}")
    logger.info(f"✅ Complex model : {os.getenv('COMPLEX_MODEL', 'groq/deepseek-r1-distill-llama-70b')}")
    logger.info(f"✅ Ollama fallback: {os.getenv('FALLBACK_TO_OLLAMA', 'true')}")

    # Ensure the request_logs table exists (best-effort — see init_db docstring).
    await init_db()
    logger.info("=" * 55)

    yield  # ← app runs here

    # ── SHUTDOWN ─────────────────────────────────────────────────────────────
    logger.info("EconRoute Gateway — shutting down")
    await close_redis()       # Week 4: resolves the aclose() TODO
    await dispose_engine()    # Week 4: release Postgres connection pool


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="EconRoute",
    description="Routes every LLM request to the cheapest capable model. OpenAI-compatible.",
    version="1.0.0",
    docs_url="/docs",      # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",    # ReDoc at http://localhost:8000/redoc
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allows the Next.js frontend (localhost:3000) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Prometheus Metrics ───────────────────────────────────────────────────────
# Automatically instruments all endpoints.
# Exposes /metrics for Prometheus scraping.
Instrumentator().instrument(app).expose(app)


# ─── Global Exception Handlers ───────────────────────────────────────────────

@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    """
    Groq / Ollama downstream failure → 503 Service Unavailable.
    503 is correct here: OUR service is up, but a DEPENDENCY failed.
    (500 = our bug. 503 = dependency down.)
    """
    logger.error(f"LLM call failed: {exc}")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "message": str(exc),
                "type": "service_unavailable",
                "code": 503,
            }
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Catch-all: return clean JSON instead of HTML traceback."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_error",
                "code": 500,
            }
        },
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post(
    "/v1/chat/completions",
    response_model=ChatResponse,
    summary="OpenAI-compatible chat completions with intelligent routing",
    tags=["inference"],
)
async def chat_completions(request: ChatRequest) -> ChatResponse:
    """
    Drop-in replacement for OpenAI's POST /v1/chat/completions.

    Change your client's base_url to http://localhost:8000/v1 — nothing else.

    EconRoute will:
    1. Check semantic cache (Week 2)
    2. Classify query complexity → simple / medium / complex
    3. Route to cheapest capable model
    4. Return response + cost metadata

    Set model="auto" to let EconRoute choose. Any other model value is accepted
    but EconRoute always routes to the optimal tier regardless.
    """
    # stream=True is rejected at Pydantic validation time (ChatRequest.stream_must_be_false).
    # No runtime check needed here — invalid requests never reach this point.
    return await route(request)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    tags=["ops"],
)
async def health_check() -> HealthResponse:
    """
    Returns real connectivity status for all dependencies (Week 4).

    - cache : Redis PING
    - db    : Postgres SELECT 1
    - groq  : GROQ_API_KEY presence (key-only — we don't burn a live call / rate
              limit on every health poll; the router surfaces real Groq errors as 503)

    status is 'ok' only when both cache and db are connected, else 'degraded'.
    """
    cache_status = await check_redis()
    db_status = await check_db()

    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_status = "ok" if groq_key and groq_key != "gsk_your_key_here" else "not_configured"

    overall = "ok" if cache_status == "connected" and db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        cache=cache_status,
        db=db_status,
        groq=groq_status,
    )


@app.websocket("/ws/requests")
async def ws_requests(websocket: WebSocket):
    """
    Real-time request live feed (Week 5).

    Server-push only: every routed request is broadcast here as JSON right after
    it is logged (see router._log_request → broadcast_request_event). The
    Next.js dashboard connects and listens; clients send nothing.

    We await receive_text() purely to detect disconnect — it unblocks by raising
    WebSocketDisconnect when the client closes, at which point we prune the socket.

    Note: CORS middleware does not apply to WebSockets. The browser's WS handshake
    is not subject to the same-origin/CORS rules used for fetch(), so no extra
    config is needed for the frontend on :3000 to connect.
    """
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        # Any other transport error → treat as a disconnect and prune the socket.
        await manager.disconnect(websocket)


@app.get("/", tags=["ops"], summary="Root — links to docs")
async def root():
    """Quick sanity check that the server is running."""
    return {
        "service": "EconRoute",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "chat": "/v1/chat/completions",
        "live_feed": "/ws/requests",
    }
