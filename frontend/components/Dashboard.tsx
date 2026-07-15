"use client";

// components/Dashboard.tsx — the live-updating client shell.
//
// State strategy (locked with the user):
//   - Seed KPIs + charts from the server's initial /v1/stats snapshot.
//   - Optimistically bump KPIs from each WS event for a live feel (tracking applied
//     event ids so we never double-count).
//   - Every 30s re-fetch /v1/stats and REPLACE state wholesale — the server snapshot
//     is the source of truth; this reconciles drift and refreshes the charts.
//     We deliberately do NOT clear the applied-id set on reconcile: ids already in
//     the snapshot stay marked, so post-reconcile events still stack correctly on top.

import { useEffect, useRef, useState } from "react";

import Card from "@/components/Card";
import CumulativeSavingsArea from "@/components/CumulativeSavingsArea";
import EmptyState from "@/components/EmptyState";
import KpiRow from "@/components/KpiRow";
import LatencyBar from "@/components/LatencyBar";
import LiveFeed from "@/components/LiveFeed";
import TierDonut from "@/components/TierDonut";
import { getStats } from "@/lib/api";
import { useLiveFeed } from "@/lib/useLiveFeed";
import type { RequestRow, StatsResponse, StatsTotals } from "@/lib/types";

const RECONCILE_MS = 30_000;

export default function Dashboard({
  initialStats,
  initialRequests,
}: {
  initialStats: StatsResponse;
  initialRequests: RequestRow[];
}) {
  const [stats, setStats] = useState<StatsResponse>(initialStats);
  const [totals, setTotals] = useState<StatsTotals>(initialStats.totals);

  const { events, status } = useLiveFeed(50);
  const appliedRef = useRef<Set<string>>(new Set());
  const hitsRef = useRef<number>(initialStats.cache_hit_vs_miss.hit);

  // ── Optimistic KPI bumps from new WS events ────────────────────────────────
  useEffect(() => {
    const fresh = events.filter((e) => !appliedRef.current.has(e.id));
    if (fresh.length === 0) return;

    let dReq = 0;
    let dSav = 0;
    let dBase = 0;
    let dHit = 0;
    for (const e of fresh) {
      appliedRef.current.add(e.id);
      dReq += 1;
      dSav += e.savings_usd;
      dBase += e.baseline_cost_usd;
      if (e.cache_hit) dHit += 1;
    }
    hitsRef.current += dHit;

    setTotals((prev) => {
      const requests = prev.requests + dReq;
      const savings_usd = prev.savings_usd + dSav;
      const baseline_usd = prev.baseline_usd + dBase;
      return {
        requests,
        savings_usd,
        baseline_usd,
        savings_pct: baseline_usd ? (savings_usd / baseline_usd) * 100 : 0,
        cache_hit_rate: requests ? (hitsRef.current / requests) * 100 : 0,
        actual_spend: 0,
      };
    });
  }, [events]);

  // ── Initial + periodic reconcile with the authoritative server snapshot ────
  // Runs client-side (in the browser), so NEXT_PUBLIC_API_URL=localhost:8000
  // correctly reaches the gateway on the host. The server-component fetch in
  // page.tsx can't do this under Docker (localhost = the frontend container), so
  // the browser is where initial data is actually loaded.
  useEffect(() => {
    let cancelled = false;
    const reconcile = async () => {
      try {
        const fresh = await getStats();
        if (cancelled) return;
        hitsRef.current = fresh.cache_hit_vs_miss.hit;
        setStats(fresh);
        setTotals(fresh.totals); // server is source of truth; replace wholesale
      } catch {
        // transient failure — keep showing optimistic state until next tick
      }
    };
    reconcile(); // immediate on mount so KPIs populate right away
    const id = setInterval(reconcile, RECONCILE_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const isEmpty = totals.requests === 0 && events.length === 0;

  return (
    <main className="mx-auto max-w-7xl px-4 py-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">💸 EconRoute — Cost Analytics</h1>
        <p className="mt-1 text-sm text-slate-500">
          Routes every LLM request to the cheapest capable model.{" "}
          <span className="font-semibold text-tier-simple">Actual spend: $0.00.</span>
        </p>
      </header>

      <KpiRow totals={totals} />

      <div className="mt-6">
        {isEmpty ? (
          <EmptyState />
        ) : (
          <div className="columns-1 gap-4 md:columns-2 xl:columns-3">
            <Card title="Requests by tier">
              <TierDonut data={stats.tier_distribution} />
            </Card>
            <Card title="Cumulative savings over time">
              <CumulativeSavingsArea data={stats.cumulative_savings} />
            </Card>
            <Card title="Latency by tier (p50 / p95)">
              <LatencyBar data={stats.latency_percentiles} />
            </Card>
            <Card>
              <LiveFeed events={events} status={status} />
            </Card>
          </div>
        )}
      </div>

      <footer className="mt-8 text-center text-xs text-slate-400">
        Initial history: {initialRequests.length} recent request(s) · live updates via
        /ws/requests · reconcile every {RECONCILE_MS / 1000}s
      </footer>
    </main>
  );
}
