"use client";

// components/PipelineFlow.tsx — Enterprise-grade pipeline visualization.
// Single flat flex row: all cards + arrows are siblings at the same level,
// ensuring perfect vertical alignment, equal spacing, and no wrapping.
//
// Flow: request → semantic cache → classifier → [models]

import { useMemo, Fragment } from "react";
import type { LiveEvent, StatsResponse } from "@/lib/types";
import { TIER_COLORS, TIER_BG, TIER_BORDER, type TierKey } from "@/lib/colors";

interface PipelineNode {
  id: string;
  label: string;
  subtitle: string;
  icon: string;
  tier?: string;
}

const PIPELINE_NODES: PipelineNode[] = [
  { id: "request",   label: "Incoming Request",           subtitle: "POST /v1/chat/completions", icon: "📨" },
  { id: "cache",     label: "Semantic Cache",             subtitle: "Redis · cosine ≥ 0.92",     icon: "💾", tier: "cache" },
  { id: "classify",  label: "Complexity Classifier",      subtitle: "semantic-router · 3 routes", icon: "🔍" },
  { id: "groq-oss-20b",   label: "groq/openai/gpt-oss-20b",      subtitle: "~150ms · simplest queries", icon: "⚡", tier: "simple" },
  { id: "groq-llama-70b", label: "groq/llama-3.3-70b-versatile", subtitle: "~400ms · explanations",     icon: "⚡", tier: "medium" },
  { id: "groq-oss-120b",  label: "groq/openai/gpt-oss-120b",     subtitle: "~800ms · reasoning",        icon: "⚡", tier: "complex" },
  { id: "ollama",    label: "Ollama Fallback",             subtitle: "qwen2.5 / llama3.2",        icon: "🖥", tier: "fallback" },
];

const CARD_W = 130;
const ARROW_W = 24;

function getTierStyle(tier?: string) {
  const key = (tier as TierKey) || "fallback";
  return { color: TIER_COLORS[key], bg: TIER_BG[key], border: TIER_BORDER[key] };
}

export default function PipelineFlow({
  stats,
  events,
}: {
  stats: StatsResponse;
  events: LiveEvent[];
}) {
  const lastEvent = events.length > 0 ? events[0] : null;
  const lastModel = lastEvent?.model_used ?? null;

  const nodePcts = useMemo(() => {
    const cachePct = stats.totals.cache_hit_rate;
    const md = stats.model_distribution;
    const f = (s: string) => { const m = md.find(d => d.model.includes(s)); return m ? m.pct : 0; };
    return {
      request:   "--",
      cache:     `${cachePct.toFixed(0)}% hit`,
      classify:  `${(100 - cachePct).toFixed(0)}% routed`,
      "groq-oss-20b":   `${f("20b").toFixed(0)}%`,
      "groq-llama-70b": `${f("70b").toFixed(0)}%`,
      "groq-oss-120b":  `${f("120b").toFixed(0)}%`,
      ollama:    `${f("ollama").toFixed(0)}%`,
    };
  }, [stats]);

  const nodeStates = useMemo(() => {
    return PIPELINE_NODES.map((node) => {
      let active = false;
      if (node.id === "request") active = true;
      else if (node.id === "cache") active = lastEvent?.cache_hit === true;
      else if (node.id === "classify") active = lastEvent !== null && !lastEvent.cache_hit;
      else if (node.id === "groq-oss-20b") active = lastModel?.includes("20b") ?? false;
      else if (node.id === "groq-llama-70b") active = lastModel?.includes("70b") ?? false;
      else if (node.id === "groq-oss-120b") active = lastModel?.includes("120b") ?? false;
      else if (node.id === "ollama") active = lastModel?.includes("ollama") ?? false;

      const style = node.tier ? getTierStyle(node.tier) : null;
      return {
        ...node,
        metric: nodePcts[node.id as keyof typeof nodePcts] ?? "",
        active,
        borderColor: active && style ? style.border : "#1B2129",
        bgColor: active && style ? style.bg : "transparent",
        labelColor: active && style ? style.color : "#E8EDF2",
        arrowActive: active,
      };
    });
  }, [lastEvent, lastModel, nodePcts]);

  return (
    <div className="rounded-xl border border-bg-border bg-bg-card p-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Pipeline Flow
        </h3>
        {lastEvent && (
          <span className="text-[10px] text-text-muted">
            last: {lastEvent.tier}{lastEvent.cache_hit ? " (cached)" : ""}
            {lastEvent.fallback_used ? " (fallback)" : ""}
          </span>
        )}
      </div>

      {/* ── Single flat flex row: cards + arrows are all siblings ── */}
      <div className="flex items-center overflow-x-auto">
        {nodeStates.map((n, i) => (
          <Fragment key={n.id}>
            {/* Node card — uniform width/height */}
            <div
              className="relative flex shrink-0 flex-col items-center justify-center rounded-lg border text-center transition-all duration-300"
              style={{
                width: CARD_W,
                height: 80,
                borderColor: n.borderColor,
                backgroundColor: n.bgColor,
                opacity: n.active ? 1 : 0.55,
              }}
            >
              {/* Flow dot */}
              {n.active && (
                <span
                  className="absolute -right-1 -top-1 h-2.5 w-2.5 animate-flow rounded-full shadow-sm"
                  style={{ backgroundColor: n.labelColor }}
                />
              )}

              {/* Icon */}
              <span className="mb-0.5 block text-sm leading-none">{n.icon}</span>

              {/* Label */}
              <p
                className="w-full truncate px-1 text-[10px] font-semibold leading-tight"
                style={{ color: n.labelColor }}
                title={n.label}
              >
                {n.label}
              </p>

              {/* Subtitle */}
              <p className="mt-0.5 w-full truncate px-1 text-[8px] leading-tight text-text-muted" title={n.subtitle}>
                {n.subtitle}
              </p>

              {/* Metric badge */}
              {n.metric && (
                <span
                  className="mt-1 inline-block rounded px-1.5 py-0.5 text-[8px] font-mono leading-none"
                  style={{
                    color: n.active ? n.labelColor : "#8B96A3",
                    backgroundColor: n.active ? "rgba(255,255,255,0.08)" : "transparent",
                  }}
                >
                  {n.metric}
                </span>
              )}
            </div>

            {/* Arrow (between cards, not after the last one) */}
            {i < nodeStates.length - 1 && (
              <div className="flex shrink-0 items-center justify-center" style={{ width: ARROW_W }}>
                <svg width="16" height="14" viewBox="0 0 16 14" fill="none">
                  <line x1="0" y1="7" x2="12" y2="7" stroke={n.arrowActive ? "#5DCAA5" : "#1B2129"} strokeWidth="1.5" strokeLinecap="round" />
                  <path d="M6 1l6 6-6 6" stroke={n.arrowActive ? "#5DCAA5" : "#1B2129"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            )}
          </Fragment>
        ))}
      </div>

      {/* Live request highlight bar */}
      {lastEvent && (
        <div className="mt-4 flex items-center gap-2 rounded-lg bg-bg-page p-2">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-tier-simple animate-flow" />
          <span className="truncate font-mono text-[10px] text-text-secondary">
            live: {lastEvent.model_used}{lastEvent.cache_hit ? " (cache)" : ""}
            {lastEvent.fallback_used ? " (ollama fallback)" : ""}
            {" · "}{lastEvent.latency_ms.toFixed(0)}ms
            {" · "}saved ${lastEvent.savings_usd.toFixed(6)}
          </span>
        </div>
      )}
    </div>
  );
}
