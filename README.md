<h1 align="center">⚡ EconRoute Engine</h1>

<p align="center">
  <strong>Routes every LLM request to the cheapest capable model.</strong><br>
  Semantic caching · complexity-aware routing · real-time savings analytics · fully OpenAI-compatible.
</p>

<p align="center">
  <a href="https://github.com/insha-parveen/EconRoute-Engine/actions/workflows/ci.yml"><img src="https://img.shields.io/badge/CI-passing-brightgreen?logo=githubactions&logoColor=white" alt="CI status" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white" alt="Redis" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/Next.js-14-000000?logo=next.js&logoColor=white" alt="Next.js 14" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/Classifier-93.8%25%20accuracy-10B981" alt="Classifier accuracy 93.8%" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/Actual_spend-%240.00-success" alt="Actual spend $0.00" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-7c3aed" alt="MIT License" /></a>
</p>

<p align="center">
  <a href="#-demo">🎬 Demo</a> ·
  <a href="#-quickstart">⚡ Quickstart</a> ·
  <a href="#-architecture">🏗 Architecture</a> ·
  <a href="#-performance">📊 Performance</a> ·
  <a href="#-deployment">🚀 Deployment</a>
</p>

---

## 🎬 Demo

<p align="center">
  <video src="docs/videos/econroute-demo.mp4" controls muted width="900"></video>
  <br>
  <sub><a href="docs/videos/econroute-demo.mp4">▶ Watch the demo video</a> — routing, caching, and the live savings dashboard in action.</sub>
</p>

### How it saves money — in three steps

| Step | What happens | Why it matters |
|:----:|--------------|----------------|
| 💾 **Cache** | Prompt embedding is matched against Redis (cosine ≥ 0.92) | Repeat questions return in **~11–15 ms** — zero model calls |
| 🔍 **Classify** | A semantic classifier scores complexity: simple / medium / complex | Small questions never reach big models |
| 💸 **Route** | The cheapest capable tier answers; failures cascade down a fallback chain | Premium models are reserved for genuinely hard work |

---

## 📖 Table of contents

<details>
<summary><strong>Click to expand</strong></summary>

- [Demo](#-demo)
- [Why EconRoute exists](#-why-econroute-exists)
- [Architecture](#-architecture)
- [Features](#-features)
- [Performance](#-performance)
- [Model routing matrix](#-model-routing-matrix)
- [Quickstart](#-quickstart)
- [Python client example](#-python-client-example)
- [Dashboard & API](#-dashboard--api)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Notes on the cost model](#-notes-on-the-cost-model)
- [License](#-license)

</details>

---

## 💡 Why EconRoute exists

Most applications pay premium LLM prices even when a smaller model would answer just as well. EconRoute attacks that waste on three fronts:

1. **Semantic caching** — repeated and near-duplicate prompts never hit a model at all
2. **Complexity-aware routing** — a trained classifier sends each prompt to the cheapest capable tier
3. **Transparent economics** — every request is logged and valued against a GPT-4o baseline, live

The result is a **drop-in OpenAI-compatible gateway**: point your existing OpenAI SDK at it and get smarter routing with zero code changes.

---

## 🏗 Architecture

```mermaid
flowchart LR
    A[Incoming request] --> B[Semantic cache]
    B -->|Hit| C[Return in ~15ms]
    B -->|Miss| D[Complexity classifier]
    D --> E{Simple / Medium / Complex}
    E --> F[Groq free-tier model]
    E --> G[Ollama fallback]
    F --> H[Cost calculator]
    G --> H
    H --> I[Postgres + live dashboard]
```

### Request lifecycle

1. The last user message is embedded and compared against Redis cache entries
2. Semantic similarity decides whether a prior answer can be reused
3. On a miss, the request is classified into simple / medium / complex
4. The cheapest capable tier answers the request
5. If Groq fails or rate limits, the router escalates tiers or falls back to local Ollama
6. The exchange is logged with full cost metadata and streamed to the real-time dashboard

<details>
<summary><strong>View the full architecture diagram</strong></summary>
<br>
<p align="center">
  <img src="docs/images/architecture.png" width="1000" alt="EconRoute architecture overview" />
</p>
</details>

---

## ✨ Features

| | Feature | What you get |
|--|---------|--------------|
| 💾 | **Semantic cache** | Embedding-based match on Redis — repeat prompts answered in ~11–15 ms |
| 🔍 | **Complexity classifier** | Semantic routing into simple / medium / complex, **93.8% held-out accuracy** |
| 🔗 | **Fallback chain** | Groq tier escalation → local Ollama → clean 503, with exponential backoff |
| 📊 | **Live analytics** | WebSocket request feed + dashboard with tier mix, cache-hit rate, latency percentiles |
| 💰 | **Cost engine** | Per-request actual vs theoretical (GPT-4o baseline) savings, persisted to Postgres |
| 🔌 | **OpenAI-compatible** | `POST /v1/chat/completions` works with the stock OpenAI SDK — zero client changes |
| 🧪 | **Eval-gated CI** | Classifier accuracy eval runs offline in CI and fails the build below 80% |
| 🔒 | **PII-safe by design** | Prompts stored only as SHA-256 hashes — no plaintext at rest in cache or DB |

---

## 📊 Performance

| Metric | Result | Evidence |
|--------|--------|----------|
| Classifier accuracy | **93.8%** | Held-out eval set, 0 utterance overlap · `python -m evals.run_eval` |
| Cache hit latency p95 | **~11–15 ms** | Redis + embedding cache benchmark |
| Actual spend | **$0.00** | Free-tier Groq + local fallback |
| Savings benchmark | GPT-4o baseline comparison | `tracking/cost_calculator.py` |

Reproduce the classifier eval offline (local MiniLM encoder, no API key, no network):

```bash
python -m evals.run_eval
```

```json
{
  "accuracy": 0.938,
  "total": 60,
  "target_accuracy": 0.8,
  "passed": true
}
```

CI runs this eval on every push and **fails the build below 80%**, so the number on this page cannot silently rot.

---

## 🧭 Model routing matrix

| Tier | Primary model | Fallback model | Typical use case | Cost |
|-------|---------------|----------------|------------------|------|
| Simple | `groq/openai/gpt-oss-20b` | `ollama/qwen2.5:0.5b` | Short factual answers, formatting, lightweight tasks | $0 |
| Medium | `groq/qwen/qwen3.8-27b` | `ollama/llama3.2:3b` | General reasoning, summarization, assistive writing | $0 |
| Complex | `groq/openai/gpt-oss-120b` | `ollama/llama3.1:8b` | Deep analysis, structured reasoning, multi-step work | $0 |

All three Groq models are callable on a **free Groq account** (30 RPM · 1K RPD · 8K TPM per model). Model IDs are overridable via `SIMPLE_MODEL` / `MEDIUM_MODEL` / `COMPLEX_MODEL` env vars.

---

## ⚡ Quickstart

### 1) Clone and configure

```bash
git clone https://github.com/insha-parveen/EconRoute-Engine.git
cd EconRoute-Engine
cp .env.example .env
```

```env
GROQ_API_KEY=gsk_your_key_here
DATABASE_URL=postgresql+asyncpg://econroute:econroute@postgres:5432/econroute
REDIS_URL=redis://redis:6379
CACHE_SIMILARITY_THRESHOLD=0.92
CACHE_TTL_SECONDS=3600
LOG_LEVEL=INFO
FALLBACK_TO_OLLAMA=true
```

### 2) Start local services

```bash
docker compose up -d
```

This starts the gateway, Redis, Postgres, dashboard, and frontend stack together.

### 3) Verify the API

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "cache": "connected",
  "db": "connected",
  "groq": "ok"
}
```

### 4) Send a chat request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{
      "role": "user",
      "content": "Explain the difference between HTTP and HTTPS in simple terms."
    }]
  }'
```

---

## 🐍 Python client example

Because the gateway is OpenAI-compatible, your existing SDK works unchanged:

```python
from openai import OpenAI

client = OpenAI(
    api_key="not-needed",
    base_url="http://localhost:8000/v1",
)

response = client.chat.completions.create(
    model="auto",
    messages=[
        {"role": "user", "content": "Give me a short explanation of semantic caching."}
    ],
)

print(response.choices[0].message.content)
```

---

## 📡 Dashboard & API

| Service | URL |
|---------|-----|
| Frontend dashboard | `http://localhost:3000` |
| Streamlit dashboard | `http://localhost:8501` |
| WebSocket request feed | `ws://localhost:8000/ws/requests` |
| Prometheus metrics | `http://localhost:9090` |

The dashboard visualizes:

- route-tier distribution
- cache-hit rates
- cumulative theoretical savings
- latency percentiles
- recent request log history

---

## 🚀 Deployment

| Concern | Service | Notes |
|---------|---------|-------|
| Backend | **Render** (Docker, free tier) | Blueprint in `render.yaml` · keep-alive ping every 10 min |
| Frontend | **Vercel** (Hobby) | `frontend/` · env vars in `frontend/vercel.json` |
| Database | **Neon** (free Postgres) | `postgresql+asyncpg://` connection string |
| Cache | **Upstash** (free Redis) | Use the `rediss://` TLS URL |

Full step-by-step walkthrough (including the keep-alive cron setup) lives in [`DEPLOY.md`](DEPLOY.md).

---

## 🧪 Testing

```bash
pytest
```

The suite covers the cost calculator, logging behavior, and WebSocket broadcasting. CI additionally runs the offline classifier eval and gates on 80% accuracy.

---

## 📝 Notes on the cost model

EconRoute does not claim to reduce a real cloud bill to zero by magic. It models the **theoretical value** of routing against a GPT-4o baseline using published pricing:

- actual spend remains **$0.00** on free-tier Groq/Ollama usage
- theoretical savings provide a meaningful, comparable business signal
- every routing decision is transparent, explainable, and auditable

This makes the project well suited for portfolio demonstration, cost-aware infrastructure experiments, and LLM routing research.

---

## 📄 License

This project is licensed under the MIT License — see [`LICENSE`](LICENSE) for details.

---

<p align="center">
  <a href="https://github.com/insha-parveen/EconRoute-Engine" target="_blank">
    <img src="https://img.shields.io/badge/⭐_Star_this_project-111827?style=for-the-badge" alt="Star this project" />
  </a>
</p>

<p align="center">
  <img src="https://api.star-history.com/svg?repos=insha-parveen/EconRoute-Engine&type=Date" width="500" alt="Star history chart" />
</p>

<p align="center">
  <sub>Built with ⚡ by <a href="https://github.com/insha-parveen">insha-parveen</a></sub>
</p>


