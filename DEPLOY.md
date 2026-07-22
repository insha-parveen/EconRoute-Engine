# EconRoute — Deployment Guide (Railway + Vercel)

## Architecture

```text
                        ┌──────────────────────┐
                        │  Neon (Postgres)       │
                        │  Serverless · Free     │
                        │  500MB storage         │
                        └──────────┬───────────┘
                                   │
┌──────────────┐        ┌──────────┴───────────┐
│  Vercel       │        │  Railway             │
│  (Frontend)   │──HTTP─▶│  (FastAPI Gateway)   │
│  Free tier    │  WS    │  1 container · $5/mo │
└──────────────┘        └──────────┬───────────┘
                                   │
                        ┌──────────┴───────────┐
                        │  Upstash (Redis)      │
                        │  Serverless · Free    │
                        │  10MB · 1000 req/day  │
                        └──────────────────────┘
```

**Only 1 container to manage** (the gateway on Railway). Postgres via Neon, Redis via Upstash.

---

## Prerequisites (5 minutes each)

| Service | Sign Up | Free Tier |
|---------|---------|-----------|
| [Railway](https://railway.app) | GitHub login | $5 credit/mo (no credit card) |
| [Neon](https://neon.tech) | GitHub login | 500MB Postgres |
| [Upstash](https://upstash.com) | GitHub login | 10MB Redis |
| [Vercel](https://vercel.com) | GitHub login | Frontend hosting |
| [Groq](https://console.groq.com) | Email login | Free LLM API |

---

## Step 1: Get Your Connection Strings

### Neon (Postgres)
```bash
# 1. Go to https://neon.tech → sign up with GitHub
# 2. Create project → region: Singapore (closest to India)
# 3. Copy the connection string
#    Looks like: postgresql://user:pass@ep-xxx.neon.tech/econroute?sslmode=require
```

### Upstash (Redis)
```bash
# 1. Go to https://upstash.com → sign up with GitHub
# 2. Create Redis database → region: Singapore
# 3. Copy the REST URL
#    Looks like: redis://default:pass@xxx.upstash.io:6379
```

### Groq (LLM API)
```bash
# 1. Go to https://console.groq.com → sign up
# 2. Create API Key → copy it
#    Looks like: gsk_your_key_here
```

---

## Step 2: Deploy Backend to Railway

### Option A: Via GitHub (easiest)
```bash
# 1. Push your code to GitHub first
git add -A
git commit -m "chore: add Railway deployment config"
git push origin main
```

1. Go to https://railway.app → **Login with GitHub**
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repo (`insha-parveen/EconRoute-Engine`)
4. Railway auto-detects `railway.toml` and `Dockerfile.prod`
5. Go to **"Variables"** tab and add:
   - `GROQ_API_KEY` = `gsk_your_key_here`
   - `DATABASE_URL` = your Neon connection string
   - `REDIS_URL` = your Upstash connection string
   - `LOG_LEVEL` = `INFO`
   - `FALLBACK_TO_OLLAMA` = `false`
6. Go to **"Settings"** → **"Generate Domain"** → copy the URL (e.g. `econroute.up.railway.app`)
7. Deploy happens automatically

### Option B: Via Railway CLI
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway init

# Set variables
railway variables set GROQ_API_KEY="gsk_your_key_here"
railway variables set DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/econroute"
railway variables set REDIS_URL="redis://default:pass@xxx.upstash.io:6379"

# Deploy
railway up

# Get URL
railway domain
```

---

## Step 3: Deploy Frontend to Vercel

1. Go to https://vercel.com/new
2. **Import your GitHub repo**
3. Settings:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`
4. Environment Variables:
   - `NEXT_PUBLIC_API_URL`: `https://econroute.up.railway.app` (your Railway URL)
   - `NEXT_PUBLIC_WS_URL`: `wss://econroute.up.railway.app/ws/requests`
5. Click **Deploy**

---

## Step 4: Verify

```bash
# Health check
curl https://econroute.up.railway.app/health
# Expected: {"status":"ok","cache":"connected","db":"connected","groq":"ok"}

# Chat completion
curl -X POST https://econroute.up.railway.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"What is Python?"}]}'

# Open dashboard
open https://econroute.vercel.app
```

---

## Local Development Still Works

Your `docker-compose up -d` runs everything locally. Production is a mirror with managed services:

```
LOCAL (docker-compose)          PRODUCTION
──────────────────────────────────────────────────
gateway:8000        ──→        Railway (1 container)
postgres:5432       ──→        Neon (serverless)
redis:6379          ──→        Upstash (serverless)
frontend:3000       ──→        Vercel
```

---

## Cost Breakdown

| Service | Plan | Monthly Cost |
|---------|------|-------------|
| Railway (gateway) | Free tier ($5 credit) | **$0** |
| Neon (Postgres) | Free tier (500MB) | **$0** |
| Upstash (Redis) | Free tier (10MB) | **$0** |
| Vercel (frontend) | Hobby (100GB bandwidth) | **$0** |
| Groq (LLM) | Free tier (30 RPM) | **$0** |
| GitHub Actions | Free (2000 min/month) | **$0** |
| **Total** | | **$0.00/mo** |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `db: "error"` in /health | Check `DATABASE_URL` in Railway Variables |
| `cache: "error"` | Check `REDIS_URL` in Railway Variables |
| `groq: "not_configured"` | Check `GROQ_API_KEY` in Railway Variables |
| 503 on chat | Groq API key invalid or rate-limited |
| Frontend can't connect | Check `NEXT_PUBLIC_API_URL` in Vercel env vars — must point to Railway URL |
| WebSocket disconnects | Railway keeps connection alive automatically with `railway.toml` |
