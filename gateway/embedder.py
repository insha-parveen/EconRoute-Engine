"""
gateway/embedder.py — Single shared ONNX embedding model for cache + classifier.

Why this module exists (Week 6 memory fix):
  Previously cache.py loaded sentence-transformers (torch) and classifier.py
  loaded semantic-router with its own HuggingFaceEncoder — TWO torch-backed
  encoders in RAM. On Render's free tier (512 MB) that combination is
  OOM-killed on boot (exit 137).

  fastembed runs the SAME all-MiniLM-L6-v2 model as ONNX int8 quantized:
    - no torch in the dependency tree at all
    - ~25 MB model + ~60 MB onnxruntime (vs ~300+ MB torch runtime)
    - identical 384-dim output vectors (numerically close; cache entries
      stored before this change should be treated as cold — embeddings are
      compatible but best re-warmed)

  One encoder instance is shared by cache.py and classifier.py, so route
  utterances and cached prompts are in the SAME vector space by construction.

Why module-level singleton?
  Model load is ~1-2 s. Loading once at import means the first request pays
  nothing and every later embed is warm. Same rationale as the old
  cache._model singleton — just lighter.
"""

import logging

import numpy as np
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

# Same underlying model as before — all-MiniLM-L6-v2, 384 dimensions.
_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

logger.info(f"Loading fastembed ONNX model: {_EMBED_MODEL}")
# threads=1: ONNX Runtime defaults to a per-core thread pool, which inflates
# RAM and fights uvicorn for CPU on Render's single-core free instance.
# Single-threaded inference is ~2x slower (~11ms → ~25ms) but far lighter.
_model = TextEmbedding(_EMBED_MODEL, threads=1)
logger.info(f"fastembed model loaded: {_EMBED_MODEL} (384-dim, ONNX int8)")


def embed_batch(texts: list[str]) -> np.ndarray:
    """
    Embed a batch of texts into 384-dim vectors.

    Args:
        texts: list of strings (may be a single-element list)

    Returns:
        numpy array of shape (len(texts), 384), float32, unnormalized.

    Note:
        fastembed yields one embedding per input, lazily. We materialize the
        generator with np.stack so callers get a normal array. Empty input
        returns a (0, 384) array instead of raising.
    """
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    # Chunk into small batches: ONNX Runtime's memory arena grows to the peak
    # batch size and never shrinks. Embedding 60 utterances in one call sized
    # the arena for batch-60 inference (~200 MB); chunks of 8 keep it small
    # with negligible throughput cost at this scale.
    out = [np.asarray(v, dtype=np.float32)
           for i in range(0, len(texts), 8)
           for v in _model.embed(texts[i:i + 8])]
    return np.stack(out)


def embed_one(text: str) -> np.ndarray:
    """Embed a single text → 1-D float32 array of shape (384,)."""
    return embed_batch([text])[0]


def cosine_matrix(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """
    Cosine similarity between one query vector and a matrix of vectors.

    Args:
        query:  (D,) float array
        matrix: (N, D) float array

    Returns:
        (N,) float array of cosine similarities in [-1, 1].

    Zero-magnitude rows are safe (result 0.0, no NaN) — normalization uses
    np.where to avoid dividing by zero, mirroring cache.cosine_similarity's
    edge-case contract.
    """
    q_norm = np.linalg.norm(query)
    m_norms = np.linalg.norm(matrix, axis=1)
    q_safe = query / q_norm if q_norm > 0 else query
    m_safe = np.divide(matrix, m_norms[:, None], out=np.zeros_like(matrix, dtype=np.float32),
                       where=m_norms[:, None] > 0)
    return m_safe @ q_safe
