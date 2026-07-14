# EconRoute Frontend — Cost Dashboard

Next.js 14 (app router) + Recharts. A live cost-analytics dashboard for the EconRoute
gateway: KPI cards, tier/latency/savings charts, and a real-time request feed streamed
over the gateway's `/ws/requests` WebSocket.

## Run it

### Via docker-compose (recommended)
From the repo root:
```bash
docker compose up -d frontend      # gateway must also be up
```
Open http://localhost:3000. The `frontend` service uses the stock `node:20-alpine`
image (no image build) and runs `npm install && npm run dev` on start.

### On the host
```bash
cd frontend
cp .env.local.example .env.local   # adjust URLs if the gateway isn't on localhost:8000
npm install
npm run dev
```

## Data sources
- `GET /v1/stats` — KPI totals, tier distribution, latency percentiles, cumulative savings.
- `GET /v1/requests?limit=N` — recent request history (PII-safe, hashed query_id).
- `ws://…/ws/requests` — live per-request events (drives the feed + optimistic KPI bumps).

KPIs update instantly from WS events and reconcile against `/v1/stats` every 30s
(server is source of truth). Tier colors match the Streamlit dashboard.

## Config (browser-exposed)
- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)
- `NEXT_PUBLIC_WS_URL` (default `ws://localhost:8000/ws/requests`)

For an HTTPS deploy, switch `ws://` → `wss://` (browsers block mixed content).

## Production build
`Dockerfile` is a deferred multi-stage production build (not wired into compose).
Use it in the Week 5 deploy step; pass the real `NEXT_PUBLIC_*` URLs as build args.
