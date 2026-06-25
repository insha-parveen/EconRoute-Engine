"""
gateway/cache.py — Semantic cache using Redis + sentence-transformers.

Design:
  1. embed()        : text → 384-dim vector (all-MiniLM-L6-v2)
  2. cosine_sim()   : measure angle between two vectors (0.0 = different, 1.0 = same)
  3. find_match()   : scan Redis keys, find best cosine match above threshold
  4. store()        : save embedding + response in Redis with TTL

Redis key schema:
  cache:{uuid4}  →  JSON {
    "query":     str,          # original query text (for debugging)
    "embedding": list[float],  # 384 floats
    "response":  str,          # cached assistant response
    "tier":      str,          # which tier answered (simple/medium/complex)
    "timestamp": float,        # unix timestamp
  }

Why UUID keys (not text keys)?
  We need to scan ALL cached embeddings to find the best cosine match.
  UUID keys with prefix "cache:" let us do: SCAN 0 MATCH cache:* COUNT 100
  This returns all entries so we can compare each embedding to the new query.

Why embed only the last user message?
  Cache lookup answers: "was this question asked before?"
  Full conversation history changes per session — caching it would cause misses
  for semantically identical questions in different conversation contexts.

Why module-level model load?
  sentence-transformers takes ~2-3s to initialise.
  Loading at import time means the first request pays that cost, not every request.
  Subsequent requests hit an already-warm model — sub-millisecond embedding.
"""

import asyncio
import hashlib
import json
import logging
import math
import os
import time
import uuid
from functools import partial
from typing import Optional

import redis.asyncio as aioredis
from sentence_transformers import SentenceTransformer

from gateway.models import ChatMessage

logger = logging.getLogger(__name__)

# ─── Model — loaded once at module import time ────────────────────────────────
# ~2-3s on first import. After that: <5ms per embed call.
# all-MiniLM-L6-v2: 384 dimensions, 22MB, fast CPU inference, good semantic quality.
_MODEL_NAME = "all-MiniLM-L6-v2"
logger.info(f"Loading sentence-transformers model: {_MODEL_NAME}")
_model = SentenceTransformer(_MODEL_NAME)
logger.info(f"Model loaded: {_MODEL_NAME}")

# ─── Config ───────────────────────────────────────────────────────────────────
_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.92"))
_TTL       = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
_KEY_PREFIX = "cache:"


# ─── Redis singleton client ──────────────────────────────────────────────────
# Created ONCE at module load time, reused for every request.
#
# Why singleton, not per-request client?
#   Each aioredis.from_url() creates a NEW connection pool.
#   Per-request pools are never closed → file descriptors leak → server crash.
#   Singleton reuses the same pool → redis-py manages connections internally.
#
# Why module-level (not global + None check)?
#   Avoids 'global' keyword (Python code smell).
#   REDIS_URL is always available at module load time in Docker (loaded from .env).
#   Simpler: one line creates it, getter just returns it.
#
# Shutdown: call await _redis_client.aclose() in FastAPI lifespan (Week 4).

_redis_client: aioredis.Redis = aioredis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=True,
)


def _get_redis() -> aioredis.Redis:
    """Return the singleton Redis client. Connection pooling handled by redis-py."""
    return _redis_client


# ─── Core functions ───────────────────────────────────────────────────────────

def _query_id(text: str) -> str:
    """
    Return a short non-sensitive identifier for a query — used in logs instead
    of raw text to prevent PII leakage.
    Format: sha256[:8] (len=N) — enough to correlate log lines, nothing more.
    """
    digest = hashlib.sha256(text.encode()).hexdigest()[:8]
    return f"sha256:{digest}(len={len(text)})"


def embed(text: str) -> list[float]:
    """
    Convert text to a 384-dimensional embedding vector.

    Args:
        text: any string (query, response, etc.)

    Returns:
        list of 384 floats — the semantic "fingerprint" of the text

    Note:
        The same meaning in different words produces similar vectors.
        "What is Python?" ≈ "Explain Python to me" → cosine similarity ~0.94
    """
    vector = _model.encode(text, convert_to_numpy=True)
    return vector.tolist()


async def embed_async(text: str) -> list[float]:
    """
    Async wrapper around embed() — runs in a thread pool.

    Why needed?
      _model.encode() is CPU-bound (5-50ms). Calling it directly in an
      async function blocks the event loop — no other requests can be
      processed during that time.

      run_in_executor() offloads the work to a thread pool so the event
      loop stays free for other requests while embedding runs in parallel.

    Why get_running_loop() not get_event_loop()?
      get_event_loop() is deprecated in Python 3.10+.
      get_running_loop() is the correct modern approach — it returns the
      currently running loop (guaranteed to exist inside an async context).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, embed, text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Formula: cos θ = (A · B) / (|A| × |B|)

    Returns:
        float in [-1.0, 1.0]
        1.0  = identical direction (same meaning)
        0.0  = perpendicular (unrelated)
       -1.0  = opposite directions (rare in text embeddings)

    Edge cases:
        Dimension mismatch  → return 0.0 (skip comparison, treat as unrelated)
        Zero-magnitude vector → return 0.0 (avoid division by zero)

    Why dimension check?
        zip(a, b) silently truncates to the shorter vector — a 384-dim query
        compared to a corrupt 100-dim stored embedding would produce a plausible
        but wrong similarity score. Explicit length check + strict=True makes
        mismatches visible and safe.
    """
    if len(a) != len(b):
        logger.warning(
            f"cosine_similarity: dimension mismatch ({len(a)} vs {len(b)}) — skipping"
        )
        return 0.0

    dot   = sum(x * y for x, y in zip(a, b, strict=True))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot / (mag_a * mag_b)


def _extract_query_text(messages: list[ChatMessage]) -> str:
    """
    Extract the last user message content for embedding.

    Why last user message only?
    → Cache answers "was this question asked before?"
    → Full history changes per session — would cause cache misses
      for semantically identical questions in different conversations.
    """
    user_messages = [m for m in messages if m.role == "user"]
    if not user_messages:
        return ""
    return user_messages[-1].content


# ─── Public API ───────────────────────────────────────────────────────────────

async def find_match(messages: list[ChatMessage]) -> Optional[str]:
    """
    Check Redis for a semantically similar cached response.

    Steps:
      1. Extract last user message
      2. Embed it → query_vec
      3. Scan all cache:* keys in Redis
      4. For each stored entry, compute cosine similarity
      5. Return response if best match ≥ threshold, else None

    Args:
        messages: conversation history (we use last user message)

    Returns:
        Cached response string if match found, None otherwise.

    Errors:
        Any Redis error → log warning, return None (cache miss is safe,
        crashing the gateway is not).
    """
    query_text = _extract_query_text(messages)
    if not query_text:
        return None

    try:
        query_vec = await embed_async(query_text)
    except Exception as e:
        logger.warning(f"Cache embed failed — {type(e).__name__}: {e}")
        return None

    try:
        r = _get_redis()
        best_score    = -1.0
        best_response = None

        # SCAN is non-blocking — safer than KEYS * in production
        async for key in r.scan_iter(match=f"{_KEY_PREFIX}*", count=100):
            raw = await r.get(key)
            if not raw:
                continue

            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"Corrupt cache entry at key {key} — skipping")
                continue

            stored_vec = entry.get("embedding")
            if not stored_vec:
                continue

            score    = cosine_similarity(query_vec, stored_vec)
            response = entry.get("response")

            # Only consider entries that actually have a response.
            # Without this guard a high-scoring entry with a missing
            # response would shadow a lower-scoring entry that has one,
            # causing a spurious cache miss despite a valid candidate existing.
            if score > best_score and response:
                best_score    = score
                best_response = response

        if best_score >= _THRESHOLD and best_response:
            logger.info(
                f"Cache HIT — similarity={best_score:.4f} "
                f"(threshold={_THRESHOLD}) query={_query_id(query_text)}"
            )
            return best_response

        logger.debug(
            f"Cache MISS — best_similarity={best_score:.4f} "
            f"(threshold={_THRESHOLD}) query={_query_id(query_text)}"
        )
        return None

    except Exception as e:
        # Redis down / timeout / connection refused → safe to skip cache
        logger.warning(f"Cache lookup failed (Redis error?) — {e}")
        return None


async def store(
    messages:  list[ChatMessage],
    response:  str,
    tier:      str = "unknown",
) -> None:
    """
    Store a query-response pair in Redis with its embedding.

    Args:
        messages : conversation (last user message is embedded)
        response : assistant response text to cache
        tier     : which Groq tier answered (for debugging / analytics)

    Errors:
        Any Redis error → log warning, don't crash.
        Caching is best-effort — a store failure should never break the response.
    """
    query_text = _extract_query_text(messages)
    if not query_text or not response:
        return

    try:
        query_vec = await embed_async(query_text)   # embed_async inside try — failures caught here
        key       = f"{_KEY_PREFIX}{uuid.uuid4()}"

        entry = {
            "query":     query_text,
            "embedding": query_vec,
            "response":  response,
            "tier":      tier,
            "timestamp": time.time(),
        }

        r = _get_redis()
        await r.set(key, json.dumps(entry), ex=_TTL)
        logger.debug(
            f"Cache STORE — key={key} tier={tier} "
            f"ttl={_TTL}s query={_query_id(query_text)}"
        )
    except Exception as e:
        logger.warning(f"Cache store failed — {type(e).__name__}: {e}")
