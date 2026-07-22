"use client";

// components/HeroSavings.tsx — Hero savings number (Space Grotesk, 36-42px)
// + sparkline + cache-vs-routing split bar. Top of the console section.

import { useMemo } from "react";
import type { StatsResponse } from "@/lib/types";

export default function HeroSavings({ stats }: { stats: StatsResponse }) {
  const savings = stats.totals.savings_usd;
  const cachePct = stats.savings_split.cache_pct;
  const routingPct = stats.savings_split.routing_pct;

  // Sparkline from cumulative_savings points
  const sparkPoints = useMemo(() => {
    return stats.cumulative_savings.map((p) => p.cumulative_savings);
  }, [stats.cumulative_savings]);

  const maxSpark = Math.max(...sparkPoints, 0.000001);
  const minSpark = Math.min(...sparkPoints, 0);

  // Build SVG path
  const sparkPath = useMemo(() => {
    if (sparkPoints.length < 2) return "";
    const w = 200;
    const h = 40;
    const range = maxSpark - minSpark || 1;
    return sparkPoints
      .map((v, i) => {
        const x = (i / (sparkPoints.length - 1)) * w;
        const y = h - ((v - minSpark) / range) * h;
        return `${i === 0 ? "M" : "L"}${x.toFixed(0)},${y.toFixed(0)}`;
      })
      .join(" ");
  }, [sparkPoints, maxSpark, minSpark]);

  return (
    <div className="rounded-xl border border-bg-border bg-bg-card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Total theoretical savings
          </p>
          <p
            className="mt-1 font-display text-4xl font-bold text-tier-simple"
            style={{ fontSize: "clamp(36px, 5vw, 42px)" }}
          >
            ${savings.toFixed(4)}
          </p>
          <p className="mt-1 text-[11px] text-text-secondary">
            vs GPT-4o baseline &middot; <span className="text-tier-simple">$0.00 actual spend</span>
          </p>
        </div>
        {/* Sparkline */}
        {sparkPath && (
          <svg width="120" height="40" className="flex-shrink-0">
            <path d={sparkPath} fill="none" stroke="#5DCAA5" strokeWidth="1.5" />
          </svg>
        )}
      </div>

      {/* Cache vs routing split bar */}
      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-[10px] text-text-muted">
          <span>Cache savings: {cachePct.toFixed(1)}%</span>
          <span>Routing savings: {routingPct.toFixed(1)}%</span>
        </div>
        <div className="flex h-2 overflow-hidden rounded-full bg-bg-page">
          <div
            className="h-full rounded-l-full"
            style={{
              width: `${cachePct}%`,
              backgroundColor: "#5DCAA5",
            }}
          />
          <div
            className="h-full rounded-r-full"
            style={{
              width: `${routingPct}%`,
              backgroundColor: "#AFA9EC",
            }}
          />
        </div>
      </div>
    </div>
  );
}
