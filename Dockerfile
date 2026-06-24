# ─── EconRoute Dockerfile ─────────────────────────────────────────────────────
# Base: python:3.11-slim (full Python, minimal OS — no unnecessary tools)
#
# Layer caching trick (important for fast rebuilds):
#   COPY requirements.txt first → pip install → COPY rest of code
#   Why? If only your .py files change, Docker reuses the cached pip layer.
#   If you did COPY . . first, ANY file change invalidates the pip cache.

FROM python:3.11-slim

# ─── System dependencies ──────────────────────────────────────────────────────
# build-essential: needed to compile some Python packages (e.g. numpy, tokenizers)
# curl: for health checks in docker-compose and Railway
RUN apt-get update && apt-get install -y \
  build-essential \
  curl \
  && rm -rf /var/lib/apt/lists/*   # clean up apt cache — keeps image small

# ─── Working directory ───────────────────────────────────────────────────────
# All commands after this run from /app inside the container
WORKDIR /app

# ─── Install Python dependencies (cached layer) ──────────────────────────────
# Copy requirements files first (locked file used for reproducible prod builds).
# This layer is only re-run if either requirements file changes.
COPY requirements.txt requirements-locked.txt ./
# Install torch CPU-only FIRST — prevents triton (197MB GPU lib) from downloading.
# Triton is only needed for GPU inference; we use CPU for embeddings.
# --timeout 120 handles slow PyPI connections.
RUN pip install --no-cache-dir --timeout 120     torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --timeout 120 -r requirements-locked.txt

# ─── Pre-download sentence-transformers model at build time ──────────────────
# Why here (not at runtime)?
#   If we download at container start, every `docker-compose up` hits the internet.
#   Baking it into the image means: download once, fast start forever.
#   ~22MB model cached in this layer — Docker reuses it unless pip layer changes.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ─── Copy application code ───────────────────────────────────────────────────
# This layer is re-run on any code change (that's fine — it's fast).
COPY . .

# ─── Create non-root user (security best practice) ───────────────────────────
# Running as root inside containers is a security risk.
RUN useradd -m -u 1000 econroute && chown -R econroute:econroute /app
USER econroute

# ─── Expose port ─────────────────────────────────────────────────────────────
EXPOSE 8000

# ─── Health check ─────────────────────────────────────────────────────────────
# Docker itself will ping this every 30s to know if container is healthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# ─── Start command ────────────────────────────────────────────────────────────
# uvicorn: the ASGI server that runs FastAPI
# --host 0.0.0.0: listen on all interfaces (not just localhost inside container)
# --port 8000: must match EXPOSE above
# --reload: auto-restarts on code change (dev only — remove for production)
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
