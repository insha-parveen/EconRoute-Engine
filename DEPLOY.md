# EconRoute — Deployment Guide (Render + Vercel)

> **Stack:** FastAPI gateway on Render (Docker) · Postgres on Neon · Redis on Upstash · Frontend on Vercel.
> Replaces the previous Railway setup (`railway.toml` has been removed).

```
┌──────────┐      ┌──────────────┐
│  Vercel  │      │    Render    │
│ (Next.js)│─────▶│  (FastAPI)   │
└──────────┘      └──────┬───────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        ┌──────────┐         ┌──────────┐
        │  Neon    │         │  Upstash │
        │ (Postgres│         │  (Redis) │
        └──────────┘         └──────────┘
```

**Only 1 container to manage** (the gateway on Render). Postgres via Neon, Redis via Upstash.

| Service | Cost | Notes |
| --------- | --------------------- | ----------------------------------------- |
| Render (gateway) | Free tier (750 hrs/mo) | Spins down after 15 min idle — see keep-alive below |
| Neon (Postgres) | Free tier | Serverless, scale-to-zero |
| Upstash (Redis) | Free tier | 10K commands/day |
| Vercel (frontend) | Free (Hobby) | |
| Groq (LLM) | Free tier | gpt-oss-20b / qwen3.8-27b / gpt-oss-120b |

## Step 1: Prep the Repo

The repo contains a `render.yaml` Blueprint (service, health check, prod start command).
Commit and push it:

```bash
git add render.yaml
git commit -m "deploy: add Render blueprint with prod start command and health check"
git push origin main
```

## Step 2: Deploy Backend to Render

### Option A: Via Render Dashboard (Blueprint)

1. Go to https://dashboard.render.com → **Login with GitHub**
2. **New → Blueprint** → select the `EconRoute-Engine` repo
3. Render reads `render.yaml` → fill in the `sync: false` secrets:
   - `GROQ_API_KEY`: from https://console.groq.com
   - `DATABASE_URL`: Neon connection string (`postgresql+asyncpg://...?sslmode=require`)
   - `REDIS_URL`: Upstash **`rediss://`** URL (double-s — TLS is in the scheme)
4. **Apply** — first build takes ~10–15 min (torch + MiniLM model baked into image)

### Option B: Via Render Dashboard (manual, no Blueprint)

1. **New → Web Service** → connect the repo
2. **Runtime**: Docker · **Dockerfile**: `Dockerfile.prod`
3. **Start command**: `uvicorn gateway.main:app --host 0.0.0.0 --port $PORT --workers 1`
4. **Health check path**: `/health` · **Region**: match your Neon/Upstash region
5. Add the env vars listed above

### Keep-alive ping (prevents free-tier spin-down)

Render free services sleep after ~15 min without traffic. Use cron-job.org (free):

1. Go to https://cron-job.org → Create cronjob
2. **URL**: `https://<your-service>.onrender.com/health`
3. **Schedule**: every 10 minutes → Save & enable

## Step 3: Deploy Frontend to Vercel

1. Go to https://vercel.com → **Add New → Project** → import the repo
2. **Root Directory**: `frontend`
3. Environment variables:
   - `NEXT_PUBLIC_API_URL`: `https://<your-service>.onrender.com`
   - `NEXT_PUBLIC_WS_URL`: `wss://<your-service>.onrender.com/ws/requests`
4. Deploy

## Step 4: Verify

```bash
curl https://<your-service>.onrender.com/health

curl -X POST https://<your-service>.onrender.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What is inflation?"}]}'
```

Expected /health response: `{"status":"ok","db":"ok","cache":"ok","groq":"ok"}`

## Monthly Cost

| Service | Tier | Cost |
| ------------------ | ---------------------- | ------ |
| Render (gateway) | Free tier (750 hrs/mo) | **$0** |
| Neon (Postgres) | Free tier | **$0** |
| Upstash (Redis) | Free tier | **$0** |
| Vercel (frontend) | Hobby | **$0** |
| Groq (LLM) | Free tier | **$0** |
| **Total** | | **$0** |

## Troubleshooting

| Problem | Fix |
| -------------------------- | -------------------------------------------------------------- |
| `db: "error"` in /health | Check `DATABASE_URL` in Render → Environment |
| `cache: "error"` | Check `REDIS_URL` — must be the `rediss://` (TLS) URL from Upstash |
| `groq: "not_configured"` | Check `GROQ_API_KEY` in Render env vars |
| Service keeps sleeping | cron-job.org not hitting `/health`, or wrong URL |
| Frontend can't connect | Check `NEXT_PUBLIC_API_URL` in Vercel env vars — must point to the Render URL |
| WebSocket disconnects | Ensure URL uses `wss://` (not `ws://`) — Vercel/Render handle TLS |
