# EconRoute — LLM Cost + Latency Optimisation Engine

> Routes every LLM request to the cheapest open-source model capable of handling it.
> Zero actual API spend. Full cost analytics against a GPT-4o baseline.

[![CI](https://img.shields.io/github/actions/workflow/status/your-username/econroute/ci.yml?label=CI)](https://github.com/your-username/econroute)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://econroute.up.railway.app)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://python.org)
[![Models](https://img.shields.io/badge/models-open--source%20only-orange)](https://console.groq.com)
[![Cost](https://img.shields.io/badge/API%20spend-%240.00-brightgreen)](https://console.groq.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Why this exists

- **The problem:** A query answerable by an 8B model at $0.0003 gets routed to GPT-4o at $0.03 — 100× more expensive — because most applications have no routing layer. At 1,000 req/day that's ~$10,950/year wasted.
- **What existing tools miss:** Semantic caches exist. Model proxies exist. Nothing open-source combines semantic caching + complexity routing + quality evaluation + a live cost savings dashboard in one deployable service — on entirely free models.
- **What EconRoute does:** Drop-in replacement for any OpenAI SDK call. Change `base_url`, nothing else. Every request flows through cache → classify → route → log → live dashboard showing theoretical savings vs GPT-4o.

### Cost model — how savings work with free models

EconRoute runs entirely on free inference (Groq free tier + local Ollama). Actual spend is always **$0.00**.

Cost figures show **theoretical savings** — what the same requests would cost on equivalent paid APIs, vs a GPT-4o baseline. This uses published pricing as a rate card and is the standard approach for demonstrating routing value in a cost-neutral environment.

```
Actual spend                  =  $0.00   (Groq / Ollama — free)
Theoretical cost (routed)     =  token_count × equivalent-paid-tier rate
Baseline cost (all GPT-4o)    =  token_count × GPT-4o rate ($0.005/1K input)
Theoretical savings           =  baseline − routed theoretical cost
Savings from cache            =  baseline × cache_hits   (zero inference cost)
Savings from smart routing    =  baseline − routed_theoretical × non-cache requests
```

The dashboard surfaces all three numbers — actual spend, theoretical routed cost, and baseline — so the methodology is always transparent.

---

## Architecture

```
Incoming request  (POST /v1/chat/completions — OpenAI-compatible)
        |
        v
+------------------------------------------+
|  1. Semantic cache                       |  Redis + sentence-transformers (local)
|     cosine similarity threshold: 0.92    |  HIT -> return in <20 ms, $0 cost
|     theoretical saving = baseline cost   |  MISS -> continue
+---------------------+--------------------+
                      | MISS
                      v
+------------------------------------------+
|  2. Complexity classifier                |  semantic-router (local, zero-shot)
|     simple / medium / complex            |
+------+-------------+---------------------+
       |             |                |
       v             v                v
Groq:llama-3.1   Groq:llama-3.3   Groq:deepseek-r1
-8b-instant      -70b-versatile   -distill-llama-70b
Simple tier      Medium tier      Complex tier
$0 actual        $0 actual        $0 actual
~$0.0003 theor.  ~$0.003 theor.   ~$0.030 theor.
       |             |                |
       +-------------+----------------+
                     | on error -> escalate + Ollama fallback
                     v
+------------------------------------------+
|  3. Cost calculator + logger             |  PostgreSQL (async)
|     actual_cost      = $0.00            |
|     theoretical_cost = tokens x rate    |
|     baseline_cost    = tokens x GPT-4o  |
|     savings          = baseline-theor.  |
+---------------------+--------------------+
                      v
+------------------------------------------+
|  4. Dashboard                            |  Next.js 14 + WebSocket (live)
|     Savings ticker (theoretical)         |  7-card masonry layout
|     Routing donut + latency bars         |  Recharts + SVG
|     Cache performance + quality          |  Auto-refreshes via WebSocket
+------------------------------------------+
```


![EconRoute Architecture](docs/images/architecture.png)
---

## Tech stack

| Layer             | Tool                                   | Cost           | Why this, not X                                               |
| ----------------- | -------------------------------------- | -------------- | ------------------------------------------------------------- |
| Simple tier       | Groq `llama-3.1-8b-instant`          | **Free** | ~150 ms p95; faster than most paid APIs                       |
| Medium tier       | Groq `llama-3.3-70b-versatile`       | **Free** | 70B quality; Groq's custom chips make it fast                 |
| Complex tier      | Groq `deepseek-r1-distill-llama-70b` | **Free** | Reasoning model; best open-source for hard tasks              |
| Local fallback    | Ollama `llama3.1:8b`                 | **Free** | Offline; handles Groq rate limits automatically               |
| LLM gateway       | LiteLLM                                | Free           | One interface for Groq + Ollama; swap model = config change   |
| Semantic cache    | Redis + sentence-transformers          | Free           | Local embeddings (all-MiniLM-L6-v2); cosine match at <8 ms    |
| Classifier        | semantic-router                        | Free           | Zero-shot local routing; no training data needed to start     |
| API layer         | FastAPI + asyncio                      | Free           | Async parallel calls; OpenAI-compatible schema out of the box |
| Cost tracking     | PostgreSQL + SQLAlchemy                | Free           | Structured logs; SQL views for dashboard metrics              |
| Quality eval      | Ollama LLM-as-judge                    | Free           | Scores outputs offline; no paid judge API                     |
| Frontend          | Next.js 14 + Tailwind                  | Free           | WebSocket client; masonry CSS layout                          |
| Charts            | Recharts                               | Free           | React-native; lightweight; streaming-friendly                 |
| Deploy (backend)  | Railway free                           | Free           | Persistent FastAPI; 500 hrs/month                             |
| Deploy (frontend) | Vercel hobby                           | Free           | Next.js native; instant deploy                                |

**Total monthly cost: $0.00**

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/insha-parveen/EconRoute-Engine
cd EconRoute-Engine

# 2. Get a free Groq API key (no credit card)
# https://console.groq.com -> Create API Key

# 3. Configure
cp .env.example .env
# Add GROQ_API_KEY=gsk_... to .env (only required key)

# 4. Start everything
docker-compose up -d
# Starts: FastAPI + Redis + PostgreSQL + Prometheus + Grafana

# 5. Verify
curl http://localhost:8000/health
# -> {"status": "ok", "cache": "connected", "db": "connected", "groq": "ok"}
```

---

## Usage example

**Request — same as any OpenAI SDK call, just change base_url:**

```python
from openai import OpenAI

client = OpenAI(
    api_key="not-needed",        # EconRoute does not require an OpenAI key
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="auto",                # EconRoute picks the tier automatically
    messages=[{"role": "user", "content": "What is the capital of France?"}]
)
```

**Response with routing metadata:**

```json
{
  "id": "chatcmpl-abc123",
  "model_used": "groq/llama-3.1-8b-instant",
  "tier": "simple",
  "cache_hit": false,
  "latency_ms": 187,
  "actual_cost_usd": 0.00000,
  "theoretical_cost_usd": 0.00008,
  "baseline_cost_usd": 0.00160,
  "savings_usd": 0.00152,
  "savings_source": "routing",
  "choices": [{"message": {"role": "assistant", "content": "Paris."}}]
}
```

**Second identical request (cache hit):**

```json
{
  "model_used": "cache",
  "cache_hit": true,
  "latency_ms": 14,
  "actual_cost_usd": 0.00000,
  "theoretical_cost_usd": 0.00000,
  "baseline_cost_usd": 0.00160,
  "savings_usd": 0.00160,
  "savings_source": "cache"
}
```

---

## Results

> Replace `[X]` with real numbers from `evals/quality_bench.py` and `evals/latency_bench.py` before sharing.

| Metric                                    | Value                           | Notes                              |
| ----------------------------------------- | ------------------------------- | ---------------------------------- |
| **Theoretical cost if all-GPT-4o**  | $[X]                            | Across 1,000 benchmark prompts     |
| **Theoretical cost with EconRoute** | $[X]                            | Routed across 3 open-source tiers  |
| **Total theoretical savings**       | **$[X] ([X]% reduction)** | Routing + cache combined           |
| Savings from semantic cache               | $[X] ([X]% of total)            | [X]% cache hit rate                |
| Savings from smart routing                | $[X] ([X]% of total)            | Routing to cheaper equivalent tier |
| **Actual API spend**                | **$0.00**                 | Groq free tier + Ollama            |
| p95 latency — simple tier                | [X] ms                          | Groq llama-3.1-8b-instant          |
| p95 latency — complex tier               | [X] ms                          | Groq deepseek-r1                   |
| Cache hit rate                            | [X]%                            | similarity threshold = 0.92        |
| Cache false positive rate                 | [X]%                            | Wrong answers served               |
| Quality equivalence — simple tier        | [X]%                            | Rated equal to GPT-4o by LLM judge |
| Quality equivalence — medium tier        | [X]%                            | Rated equal to GPT-4o by LLM judge |
| Classifier accuracy                       | [X]%                            | vs 100 hand-labelled prompts       |

---

## Pinterest-style dashboard

7-card masonry layout — updates live via WebSocket on every request.

| Card                        | What it shows                                                          |
| --------------------------- | ---------------------------------------------------------------------- |
| **Savings ticker**    | Theoretical savings today ($) + sparkline + "$0.00 actual spend" badge |
| **Routing donut**     | % of requests per tier (cache / simple / medium / complex)             |
| **Latency bars**      | p50 and p95 per tier — horizontal colour-coded bars                   |
| **Live feed**         | Last 6 requests: model used, query preview, theoretical cost, latency  |
| **Cache performance** | Hit rate %, false positive rate %, cache vs routing savings split      |
| **Quality monitor**   | LLM-judge equivalence % vs GPT-4o baseline, per tier                   |
| **Cost breakdown**    | Theoretical cost per model + routing % share                           |

---

## Project structure

```
econroute/
├── gateway/
│   ├── main.py              # FastAPI — /v1/chat/completions, /health, /metrics, /ws/requests
│   ├── router.py            # cache -> classify -> route -> cost -> log
│   ├── classifier.py        # semantic-router: simple / medium / complex
│   ├── cache.py             # embed, cosine-match vs Redis, store on miss
│   ├── fallback.py          # Groq -> Ollama; tier escalation; exponential backoff
│   └── models.py            # Pydantic schemas
├── providers/
│   ├── litellm_client.py    # LiteLLM async wrapper; Groq + Ollama
│   └── model_config.py      # tier mapping + theoretical cost rates + baseline rates
├── tracking/
│   ├── logger.py            # async log to Postgres + emit WebSocket event
│   ├── cost_calculator.py   # actual=0, theoretical, baseline, savings
│   └── db.py                # SQLAlchemy models + async engine
├── websocket/
│   └── events.py            # WebSocket manager; broadcast RoutingEvent
├── dashboard/               # Streamlit fallback (Week 4)
│   ├── app.py
│   └── queries.py
├── frontend/                # Next.js 14 Pinterest dashboard (Week 5)
│   ├── app/page.tsx
│   ├── components/          # SavingsCard, RoutingDonut, LatencyCard, LiveFeedCard...
│   ├── lib/websocket.ts
│   └── types/routing.ts
├── evals/
│   ├── quality_bench.py     # 100 prompts; Ollama judge; CSV + summary
│   ├── latency_bench.py     # 200 req/tier async; p50/p95/p99; markdown table
│   └── threshold_sweep.py   # cache similarity sweep: 0.85 / 0.90 / 0.92 / 0.95 / 0.98
├── Dockerfile
├── docker-compose.yml       # FastAPI + Redis + Postgres + Prometheus + Grafana
└── .env.example
```


⭐ If you found this project useful, consider giving it a star.
