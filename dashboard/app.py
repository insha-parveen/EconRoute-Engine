"""
dashboard/app.py — EconRoute cost-analytics dashboard (Week 4, Streamlit).

Reads the `request_logs` table (written by tracking/db.py) and visualises the
economic value of intelligent routing: theoretical savings vs a GPT-4o baseline,
cache-hit rate, tier distribution, and latency.

Why a SEPARATE (synchronous) DB connection?
  Streamlit is not an ASGI app — it can't share the gateway's async SQLAlchemy
  engine. We use a psycopg2 sync engine here. The URL differs from the gateway's:
    - gateway  : postgresql+asyncpg://...@postgres:5432   (async, in-compose host)
    - dashboard: postgresql+psycopg2://...@localhost:5432  (sync, local host)
  Override with DASHBOARD_DATABASE_URL for compose (host 'postgres').

Run locally:
    pip install -r requirements-dev.txt
    streamlit run dashboard/app.py
Or via docker-compose (dashboard service) → http://localhost:8501
"""

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

# ─── Config ───────────────────────────────────────────────────────────────────
DB_URL = os.getenv(
    "DASHBOARD_DATABASE_URL",
    "postgresql+psycopg2://econroute:econroute@localhost:5432/econroute",
)

# Brand-neutral, colour-blind-safe categorical palette (consistent across charts).
TIER_COLORS = {
    "cache": "#4E79A7",
    "simple": "#59A14F",
    "medium": "#F28E2B",
    "complex": "#E15759",
}

st.set_page_config(page_title="EconRoute — Cost Analytics", page_icon="💸", layout="wide")


# ─── Data access ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_engine():
    """One sync engine per Streamlit session (cached across reruns)."""
    return create_engine(DB_URL, pool_pre_ping=True)


@st.cache_data(ttl=10)
def load_logs() -> pd.DataFrame:
    """
    Load request history. Returns an empty DataFrame (not an error) when the table
    is empty or unreachable, so the UI can show a friendly empty-state instead.
    """
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(
                text("SELECT * FROM request_logs ORDER BY created_at DESC"), conn
            )
    except Exception as e:  # table not created yet / DB down
        st.warning(f"Could not read request_logs yet: {type(e).__name__}: {e}")
        return pd.DataFrame()


# ─── Header ───────────────────────────────────────────────────────────────────
st.title("💸 EconRoute — Cost Analytics")
st.caption("Routes every LLM request to the cheapest capable model. Actual spend: **$0.00**.")

col_l, col_r = st.columns([6, 1])
with col_r:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

df = load_logs()

if df.empty:
    st.info(
        "No requests logged yet. Send a request to "
        "`POST /v1/chat/completions`, then hit **Refresh**."
    )
    st.stop()

# Normalise dtypes
df["created_at"] = pd.to_datetime(df["created_at"])

# ─── KPI row ──────────────────────────────────────────────────────────────────
total_requests = len(df)
total_savings = df["savings_usd"].sum()
total_baseline = df["baseline_cost_usd"].sum()
avg_savings_pct = (total_savings / total_baseline * 100) if total_baseline else 0.0
cache_hit_rate = df["cache_hit"].mean() * 100

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total requests", f"{total_requests:,}")
k2.metric("Theoretical savings", f"${total_savings:,.4f}")
k3.metric("Savings vs GPT-4o", f"{avg_savings_pct:.1f}%")
k4.metric("Cache-hit rate", f"{cache_hit_rate:.1f}%")
k5.metric("Actual spend", "$0.00")

st.divider()

# ─── Charts ───────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.subheader("Requests by tier")
    tier_counts = df["tier"].value_counts().reset_index()
    tier_counts.columns = ["tier", "count"]
    fig = px.pie(
        tier_counts, names="tier", values="count", hole=0.5,
        color="tier", color_discrete_map=TIER_COLORS,
    )
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Cumulative savings over time")
    ts = df.sort_values("created_at").copy()
    ts["cumulative_savings"] = ts["savings_usd"].cumsum()
    fig = px.area(ts, x="created_at", y="cumulative_savings", labels={
        "created_at": "Time", "cumulative_savings": "Cumulative savings ($)"})
    fig.update_traces(line_color=TIER_COLORS["simple"])
    st.plotly_chart(fig, use_container_width=True)

c3, c4 = st.columns(2)

with c3:
    st.subheader("Latency by tier (ms)")
    fig = px.box(
        df, x="tier", y="latency_ms", color="tier",
        color_discrete_map=TIER_COLORS, points="outliers",
    )
    st.plotly_chart(fig, use_container_width=True)

with c4:
    st.subheader("Cache hit vs miss")
    hit = df["cache_hit"].map({True: "hit", False: "miss"}).value_counts().reset_index()
    hit.columns = ["result", "count"]
    fig = px.bar(hit, x="result", y="count", color="result",
                 color_discrete_map={"hit": TIER_COLORS["cache"], "miss": TIER_COLORS["complex"]})
    st.plotly_chart(fig, use_container_width=True)

# ─── Latency percentiles ──────────────────────────────────────────────────────
st.subheader("Latency percentiles by tier")
pcts = (
    df.groupby("tier")["latency_ms"]
    .agg(p50=lambda s: s.quantile(0.50), p95=lambda s: s.quantile(0.95), count="count")
    .round(1)
    .reset_index()
)
st.dataframe(pcts, use_container_width=True, hide_index=True)

# ─── Recent requests ──────────────────────────────────────────────────────────
st.subheader("Recent requests")
st.dataframe(
    df[[
        "created_at", "tier", "model_used", "cache_hit", "fallback_used",
        "latency_ms", "input_tokens", "output_tokens",
        "theoretical_cost_usd", "baseline_cost_usd", "savings_usd", "savings_source",
    ]].head(50),
    use_container_width=True,
    hide_index=True,
)
