"use client";

// components/ConsoleDashboard.tsx — SECTION 2: Cost console dashboard.
// Integrates: header with health dots (SWR polling every 30s), time range pills,
// HeroSavings + sparkline + split bar, PipelineFlow, MetricCards,
// RequestHistoryTable, ModelDistribution.

import { useCallback, useEffect, useRef, useState } from "react";
import HeroSavings from "@/components/HeroSavings";
import PipelineFlow from "@/components/PipelineFlow";
import MetricCards from "@/components/MetricCards";
import RequestHistoryTable from "@/components/RequestHistoryTable";
import ModelDistribution from "@/components/ModelDistribution";
import { getHealth, getStats, getRequests } from "@/lib/api";
import { useLiveFeed } from "@/lib/useLiveFeed";
import type { HealthResponse, RequestRow, StatsResponse } from "@/lib/types";

const RECONCILE_MS = 30_000;
const HEALTH_POLL_MS = 30_000;

type RangeKey = "today" | "7d" | "30d" | "all";

const RANGE_PILLS: { key: RangeKey; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d", label: "7D" },
  { key: "30d", label: "30D" },
  { key: "all", label: "All" },
];

function healthDot(status: string): { color: string; label: string } {
  switch (status) {
    case "connected":
    case "ok":
      return { color: "#5DCAA5", label: status };
    case "degraded":
    case "error":
      return { color: "#EF9F27", label: status };
    default:
      return { color: "#5F6A76", label: status || "?" };
  }
}

export default function ConsoleDashboard({
  initialStats,
  initialRequests,
}: {
  initialStats: StatsResponse;
  initialRequests: RequestRow[];
}) {
  const [stats, setStats] = useState<StatsResponse>(initialStats);
  const [range, setRange] = useState<RangeKey>("all");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  // WebSocket live feed
  const { events, status: wsStatus } = useLiveFeed(50);
  const appliedRef = useRef<Set<string>>(new Set());

  // ── Health polling (SWR-like with setInterval) ──────────────────────────
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const h = await getHealth();
        if (!cancelled) setHealth(h);
      } catch {
        // transient
      }
    };
    poll();
    const id = setInterval(poll, HEALTH_POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // ── Periodic reconcile with the authoritative server snapshot ────────────
  useEffect(() => {
    let cancelled = false;
    const reconcile = async () => {
      try {
        const fresh = await getStats();
        if (cancelled) return;
        setStats(fresh);
      } catch {
        // transient — keep showing optimistic state
      }
    };
    reconcile();
    const id = setInterval(reconcile, RECONCILE_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [range]);

  // ── Optimistic KPI bumps from new WS events ─────────────────────────────
  useEffect(() => {
    const fresh = events.filter((e) => !appliedRef.current.has(e.id));
    if (fresh.length === 0) return;
    for (const e of fresh) {
      appliedRef.current.add(e.id);
    }
    // Stats will be reconciled on the next 30s tick
  }, [events]);

  const isEmpty = stats.totals.requests === 0 && events.length === 0;

  return (
    <section className="border-t border-bg-border bg-bg-page py-8">
      <div className="mx-auto max-w-7xl px-4">
        {/* Header with health dots */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-text-primary">💸 EconRoute</span>
            <span className="text-[10px] text-text-muted">Cost Console</span>
          </div>
          <div className="flex items-center gap-4">
            {/* WebSocket status */}
            <HealthIndicator color={wsStatus === "open" ? "#5DCAA5" : "#EF9F27"} label={wsStatus} />
            {/* Health dots */}
            {health ? (
              <>
                <HealthDot name="cache" status={health.cache} />
                <HealthDot name="db" status={health.db} />
                <HealthDot name="groq" status={health.groq} />
                <HealthDot name="ollama" status={health.status} />
              </>
            ) : (
              <span className="text-[10px] text-text-muted">Checking health...</span>
            )}
          </div>
        </div>

        {/* Time range pills */}
        <div className="mb-6 flex gap-2">
          {RANGE_PILLS.map((pill) => (
            <button
              key={pill.key}
              onClick={() => setRange(pill.key)}
              className={`rounded-md px-3 py-1 text-[11px] font-semibold uppercase tracking-wider transition ${
                range === pill.key
                  ? "bg-tier-simple text-black"
                  : "bg-bg-card text-text-secondary hover:text-text-primary"
              }`}
            >
              {pill.label}
            </button>
          ))}
        </div>

        {isEmpty ? (
          <div className="rounded-xl border border-bg-border bg-bg-card p-12 text-center">
            <p className="text-sm text-text-muted">
              No requests logged yet. Send a request to POST /v1/chat/completions
              or try the demo above.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Hero savings + split bar */}
            <HeroSavings stats={stats} />

            {/* Pipeline flow */}
            <PipelineFlow stats={stats} events={events} />

            {/* Metric strip */}
            <MetricCards totals={stats.totals} />

            {/* Two-column row: ModelDistribution + RequestHistoryTable */}
            <div className="grid gap-6 lg:grid-cols-2">
              <ModelDistribution data={stats.model_distribution} />
              <RequestHistoryTable
                initialRequests={initialRequests}
                total={stats.totals.requests}
              />
            </div>
          </div>
        )}

        <footer className="mt-8 text-center text-[10px] text-text-muted">
          live feed via /ws/requests &middot; reconcile every {RECONCILE_MS / 1000}s
        </footer>
      </div>
    </section>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function HealthDot({ name, status }: { name: string; status: string }) {
  const dot = healthDot(status);
  return (
    <div className="flex items-center gap-1.5">
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: dot.color }}
      />
      <span className="text-[9px] font-semibold uppercase text-text-muted">
        {name}
      </span>
    </div>
  );
}

function HealthIndicator({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="text-[9px] font-semibold uppercase text-text-muted">
        ws: {label}
      </span>
    </div>
  );
}
