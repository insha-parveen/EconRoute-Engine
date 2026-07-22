"use client";

// components/MetricCards.tsx — Metric strip: cache hit rate, fallback rate,
// classifier accuracy (88.0%), total requests. Left-accent-border cards.

import { EVAL } from "@/lib/types";
import type { StatsTotals } from "@/lib/types";

export default function MetricCards({ totals }: { totals: StatsTotals }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <MetricCard
        label="cache hit rate"
        value={`${totals.cache_hit_rate.toFixed(1)}%`}
        accent="#5DCAA5"
      />
      <MetricCard
        label="fallback rate"
        value={`${totals.fallback_rate.toFixed(1)}%`}
        accent="#8B96A3"
      />
      <MetricCard
        label="classifier accuracy"
        value={`${EVAL.overall}%`}
        accent="#AFA9EC"
      />
      <MetricCard
        label="total requests"
        value={totals.requests.toLocaleString("en-US")}
        accent="#EF9F27"
      />
    </div>
  );
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div
      className="rounded-xl border border-bg-border bg-bg-card p-4"
      style={{ borderLeft: `3px solid ${accent}` }}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        {label}
      </p>
      <p className="mt-1 font-mono text-lg font-bold text-text-primary">
        {value}
      </p>
    </div>
  );
}
