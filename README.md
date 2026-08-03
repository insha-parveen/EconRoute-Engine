# EconRoute

<p align="center">
  <img src="docs/images/architecture.png" width="1100" alt="EconRoute architecture overview" />
</p>

<p align="center">
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white" alt="Redis" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine"><img src="https://img.shields.io/badge/Next.js-14-000000?logo=next.js&logoColor=white" alt="Next.js 14" /></a>
  <a href="https://github.com/insha-parveen/EconRoute-Engine/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-7c3aed" alt="MIT License" /></a>
</p>

<p align="center">
  <strong>Routes every LLM request to the cheapest capable model.</strong><br>
  Zero actual spend, real-time savings analytics, and a fully OpenAI-compatible gateway.
</p>

> EconRoute is an intelligent LLM routing system built to minimize cost without sacrificing quality. It checks a semantic cache first, classifies request complexity, routes to the cheapest viable model on free Groq infrastructure, falls back to local Ollama if needed, and logs every request for live economic analysis.

---

## Why this project exists

Most applications pay for premium LLMs even when a smaller or cheaper model would work. That creates unnecessary cost, slower user experiences, and a poor cost-to-quality ratio.

EconRoute solves that by combining:

1. Semantic caching for repeated prompts
2. Complexity-aware routing using semantic classification
3. Real-time analytics that compare routing value against a GPT-4o baseline

The result is a drop-in OpenAI-compatible gateway that keeps the developer experience simple while adding smart decision-making under the hood.

---

## Demo video and architecture

<p align="center">
  <video
    src="docs/videos/econroute-demo.mp4"
    poster="docs/images/architecture.png"
    controls
    playsinline
    preload="metadata"
    style="display:block; max-width:100%; width:960px; height:auto; border-radius:12px; background:#0b1220;"
  >
    Your browser does not support the video tag.
  </video>
</p>

<p align="center">
  <img src="docs/images/architecture.png" width="1000" alt="EconRoute live architecture demonstration" />
</p>

---

## System overview

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

### Request flow

- Last user message is embedded and compared against Redis cache entries
- Semantic similarity decides whether a prior answer can be reused
- If no hit, the request is classified into simple / medium / complex
- The correct tier is selected using the cheapest capable model
- If Groq fails or rate limits, the router escalates or falls back to a local Ollama model
- Final output is logged and displayed in the real-time dashboard with cost metadata

---

## Featured capabilities

### Semantic cache

- Uses Redis + `all-MiniLM-L6-v2` embeddings
- Cosine-similarity lookup across cached prompts
- Cache-hit latency measured around 11–15 ms p95
- Prevents redundant inference for repeated queries

### Complexity-aware routing

- Uses a semantic router to classify prompts
- Routes quick tasks to simpler models and complex reasoning to larger models
- Keeps the cost profile optimized while preserving answer quality

### Free model inference

- Primary models run on Groq free-tier infrastructure
- Local fallback through Ollama for resilience during rate limiting or outages
- Actual inference cost remains $0.00 in the project model

### Cost analytics

- Calculates actual spend, theoretical cost, GPT-4o baseline cost, and savings
- Stores request history and route metadata in PostgreSQL
- Exposes analytics via FastAPI and a live dashboard

### OpenAI compatibility

- `POST /v1/chat/completions` works as a drop-in replacement for many OpenAI SDK client flows
- Existing apps can route through EconRoute with minimal integration changes

---

## Model routing matrix

| Tier    | Primary model                  | Fallback model        | Typical use case                                           | Cost profile |
| ------- | ------------------------------ | --------------------- | ---------------------------------------------------------- | ------------ |
| Simple  | `groq/openai/gpt-oss-20b`      | `ollama/qwen2.5:0.5b` | Short factual answers, quick formatting, lightweight tasks | $0 actual    |
| Medium  | `groq/llama-3.3-70b-versatile` | `ollama/llama3.2:3b`  | General reasoning, summarization, assistive writing        | $0 actual    |
| Complex | `groq/openai/gpt-oss-120b`     | `ollama/llama3.1:8b`  | Deep analysis, structured reasoning, multi-step work       | $0 actual    |

This project calculates theoretical value against the GPT-4o baseline, even though the real backend is running on free infrastructure.

---

## Performance and evaluation results

The project includes evaluation artifacts under `evals/` and a classifier validation report in `evals/results/classifier_eval.json`.

### Core metrics

| Metric                   | Result                     | Evidence                                   |
| ------------------------ | -------------------------- | ------------------------------------------ |
| Cache hit latency p95    | ~11–15 ms                  | Redis + embedding cache benchmark          |
| Classifier accuracy      | 90%                        | `evals/results/classifier_eval.json`       |
| Total requests evaluated | 60                         | held-out eval set                          |
| Actual spend             | $0.00                      | free-tier Groq + local fallback            |
| Savings benchmark        | GPT-4o baseline comparison | cost model in`tracking/cost_calculator.py` |

### Evaluation summary

```json
{
  "accuracy": 0.9,
  "correct": 54,
  "total": 60,
  "target_accuracy": 0.8,
  "passed": true
}
```

This is a strong signal that the routing logic is not just cheap — it is also directionally accurate on varied prompt complexity.

---

## Tech stack

| Layer          | Stack                                                     |
| -------------- | --------------------------------------------------------- |
| API layer      | FastAPI, Pydantic, OpenAI-compatible schema               |
| Model routing  | Groq, LiteLLM, semantic-router                            |
| Cache layer    | Redis, sentence-transformers,`all-MiniLM-L6-v2`           |
| Local fallback | Ollama                                                    |
| Persistence    | PostgreSQL + SQLAlchemy + asyncpg                         |
| Dashboard      | Streamlit + Plotly; Next.js frontend with live WebSockets |
| Deployment     | Docker Compose, Railway, Vercel                           |

---

## Repository structure

```text
EconRoute-Engine/
├── README.md
├── DEPLOY.md
├── IMPLEMENTATION_PLAN.md
├── FREE_DEPLOYMENT_PLAN.md
├── Dockerfile
├── Dockerfile.prod
├── docker-compose.yml
├── railway.toml
├── requirements.txt
├── requirements-dev.txt
├── requirements-locked.txt
├── prometheus.yml
├── .env.example
├── gateway/
│   ├── __init__.py
│   ├── analytics.py
│   ├── cache.py
│   ├── classifier.py
│   ├── fallback.py
│   ├── main.py
│   ├── models.py
│   └── router.py
├── providers/
│   ├── __init__.py
│   ├── litellm_client.py
│   └── model_config.py
├── tracking/
│   ├── __init__.py
│   ├── cost_calculator.py
│   └── db.py
├── dashboard/
│   ├── __init__.py
│   └── app.py
├── websocket/
│   ├── __init__.py
│   └── manager.py
├── tests/
│   ├── test_cost_calculator.py
│   ├── test_logging.py
│   └── test_websocket.py
├── evals/
│   ├── __init__.py
│   ├── classifier_eval.py
│   ├── eval_set.jsonl
│   ├── run_eval.py
│   ├── testset.py
│   └── results/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── Dockerfile
│   ├── README.md
│   ├── next.config.mjs
│   ├── package.json
│   └── tailwind.config.ts
├── docs/
│   └── images/
└── scripts/
```

---

## Quick start

### 1) Clone the repo

```bash
git clone https://github.com/insha-parveen/EconRoute-Engine.git
cd EconRoute-Engine
```

### 2) Configure environment variables

Create a local `.env` file based on the project defaults and your environment.

```bash
copy .env.example .env
```

Typical values:

```env
GROQ_API_KEY=your_groq_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql+asyncpg://econroute:econroute@localhost:5432/econroute
DASHBOARD_DATABASE_URL=postgresql+psycopg2://econroute:econroute@localhost:5432/econroute
LOG_LEVEL=INFO
FALLBACK_TO_OLLAMA=true
```

### 3) Start local services

```bash
docker compose up -d
```

This starts the gateway, Redis, Postgres, dashboard, and frontend stack together.

### 4) Verify the API

```bash
curl http://localhost:8000/health
```

Example response:

```json
{
  "status": "ok",
  "cache": "connected",
  "db": "connected",
  "groq": "ok"
}
```

### 5) Send a chat request

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

## Python client example

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

## Dashboard access

The project exposes a live analytics dashboard and request feed.

- Streamlit dashboard: `http://localhost:8501`
- Frontend dashboard: `http://localhost:3000`
- WebSocket feed: `ws://localhost:8000/ws/requests`
- Prometheus metrics: `http://localhost:9090`

The dashboard visualizes:

- route-tier distribution
- cache-hit rates
- cumulative theoretical savings
- latency percentiles
- recent request log history

---

## Deployment

This project is designed for both local Docker development and managed deployments.

### Local development

```bash
docker compose up -d
```

### Production-friendly options

- Railway for the FastAPI backend
- Vercel for the Next.js frontend
- Neon/Postgres for database storage
- Upstash/Redis for managed cache

See `DEPLOY.md` for a production deployment walkthrough.

---

## Notes on the cost model

EconRoute does not claim to reduce real cloud bill spend to zero in production by magic. Instead, it models the theoretical value of routing against a GPT-4o baseline using published pricing estimates.

In practice:

- actual spend remains zero on free-tier Groq/Ollama usage
- theoretical savings provide a meaningful business signal
- routing decisions are transparent, explainable, and auditable

This makes the project well suited for portfolio demonstration, cost-aware infrastructure experiments, and LLM routing research.

---

## Testing

The project includes a lightweight test suite covering the cost calculator, logging behavior, and WebSocket broadcasting.

```bash
pytest
```
## License

This project is licensed under the MIT License. See `LICENSE` for details.

<p align="center">
  <a href="https://github.com/insha-parveen/EconRoute-Engine" target="_blank">
    <img src="https://img.shields.io/badge/⭐_Star_this_project-111827?style=for-the-badge" alt="Star this project" />
  </a>
</p>

```

⭐ If you found this project useful, consider giving it a star.
```
