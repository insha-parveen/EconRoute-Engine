"use client";

// components/PipelineFlow.tsx — Enterprise-grade pipeline visualization.
// Single horizontal row, uniform cards, perfectly centered arrows.
// Flow: request → semantic cache → classifier → [models]
// All nodes have equal dimensions with text truncation.

import { useMemo } from "react";
import type { LiveEvent, StatsResponse } from "@/lib/types";
import { TIER_COLORS, TIER_BG, TIER_BORDER, type TierKey } from "@/lib/colors";

interface PipelineNode {
  id: string;
  label: string;
  subtitle: string;
  icon: string;
  tier?: string;
  isTerminal?: boolean;
}

const PIPELINE_NODES: PipelineNode[] = [
  {
    id: "request",
    label: "Incoming Request",
    subtitle: "POST /v1/chat/completions",
    icon: "📨",
  },
  {
    id: "cache",
    label: "Semantic Cache",
    subtitle: "Redis · cosine ≥ 0.92",
    icon: "💾",
    tier: "cache",
  },
  {
    id: "classify",
    label: "Complexity Classifier",
    subtitle: "semantic-router · 3 routes",
    icon: "🔍",
  },
  {
    id: "groq-oss-20b",
    label: "groq/openai/gpt-oss-20b",
    subtitle: "~150ms · simplest queries",
    icon: "⚡",
    tier: "simple",
    isTerminal: true,
  },
  {
    id: "groq-llama-70b",
    label: "groq/llama-3.3-70b-versatile",
    subtitle: "~400ms · explanations",
    icon: "⚡",
    tier: "medium",
    isTerminal: true,
  },
  {
    id: "groq-oss-120b",
    label: "groq/openai/gpt-oss-120b",
    subtitle: "~800ms · reasoning & code",
    icon: "⚡",
    tier: "complex",
    isTerminal: true,
  },
  {
    id: "ollama",
    label: "Ollama Fallback",
    subtitle: "qwen2.5 / llama3.2 / llama3.1",
    icon: "🖥",
    tier: "fallback",
    isTerminal: true,
  },
];

const ARROW_WIDTH = 28;
const STATUS_MAP: Record<string, string> = {
  cache: "cache",
  simple: "groq-oss-20b",
  medium: "groq-llama-70b",
  complex: "groq-oss-120b",
  fallback: "ollama",
};

function getTierStyle(tier?: string) {
  const key = (tier as TierKey) || "fallback";
  return {
    color: TIER_COLORS[key],
    bg: TIER_BG[key],
    border: TIER_BORDER[key],
  };
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
    const modelDist = stats.model_distribution;

    const getModelPct = (partial: string) => {
      const m = modelDist.find((d) => d.model.includes(partial) || partial.includes(d.model));
      return m ? m.pct : 0;
    };

    return {
      request: "--",
      cache: `${cachePct.toFixed(0)}% hit`,
      classify: `${(100 - cachePct).toFixed(0)}% routed`,
      "groq-oss-20b": `${getModelPct("gpt-oss-20b").toFixed(0)}%`,
      "groq-llama-70b": `${getModelPct("70b").toFixed(0)}%`,
      "groq-oss-120b": `${getModelPct("120b").toFixed(0)}%`,
      ollama: `${getModelPct("ollama").toFixed(0)}%`,
    };
  }, [stats]);

  const isActive = (nodeId: string): boolean => {
    if (nodeId === "request") return true;
    if (nodeId === "cache") return lastEvent?.cache_hit === true;
    if (nodeId === "classify") return lastEvent !== null && !lastEvent?.cache_hit;
    if (nodeId === "groq-oss-20b") return lastModel?.includes("20b") ?? false;
    if (nodeId === "groq-llama-70b") return lastModel?.includes("70b") ?? false;
    if (nodeId === "groq-oss-120b") return lastModel?.includes("120b") ?? false;
    if (nodeId === "ollama") return lastModel?.includes("ollama") ?? false;
    return false;
  };

  const activeStyle = (nodeId: string) => {
    const active = isActive(nodeId);
    const node = PIPELINE_NODES.find((n) => n.id === nodeId);
    const style = node?.tier ? getTierStyle(node.tier) : null;
    return {
      active,
      borderColor: active && style ? style.border : "#1B2129",
      bgColor: active && style ? style.bg : "transparent",
      labelColor: active && style ? style.color : "#E8EDF2",
    };
  };

  const Arrow = ({ isActive: a }: { isActive: boolean }) => (
    <div
      className="flex shrink-0 items-center justify-center"
      style={{ width: ARROW_WIDTH }}
    >
      <svg
        width="18"
        height="14"
        viewBox="0 0 18 14"
        fill="none"
        className="block"
      >
        <line
          x1="0"
          y1="7"
          x2="14"
          y2="7"
          stroke={a ? "#5DCAA5" : "#1B2129"}
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <path
          d="M8 1l6 6-6 6"
          stroke={a ? "#5DCAA5" : "#1B2129"}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );

  return (
    <div className="rounded-xl border border-bg-border bg-bg-card p-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Pipeline Flow
        </h3>
        {lastEvent && (
          <span className="text-[10px] text-text-muted">
            last: {lastEvent.tier}
            {lastEvent.cache_hit ? " (cached)" : ""}
            {lastEvent.fallback_used ? " (fallback)" : ""}
          </span>
        )}
      </div>

      {/* Pipeline row — single line, no wrap */}
      <div className="flex items-center justify-between overflow-x-auto">
        {PIPELINE_NODES.map((node, i) => {
          const a = activeStyle(node.id);
          const metric = nodePcts[node.id as keyof typeof nodePcts] ?? "";

          return (
            <div key={node.id} className="flex items-center gap-0">
              {/* Node card — uniform width/height with truncation */}
              <div
                className={`relative flex w-[118px] shrink-0 flex-col items-center justify-center rounded-lg border px-2.5 py-3 text-center transition-all duration-300 ${
                  a.active ? "shadow-md" : "opacity-65"
                }`}
                style={{
                  borderColor: a.borderColor,
                  backgroundColor: a.bgColor,
                  height: 80,
                }}
              >
                {/* Flow dot */}
                {a.active && (
                  <span
                    className="absolute -right-1 -top-1 h-2.5 w-2.5 animate-flow rounded-full shadow-sm"
                    style={{ backgroundColor: a.labelColor }}
                  />
                )}

                {/* Icon */}
                <span className="mb-1 block text-sm leading-none">{node.icon}</span>

                {/* Label — truncate with ellipsis */}
                <p
                  className="w-full truncate text-[10px] font-semibold leading-tight"
                  style={{ color: a.labelColor }}
                  title={node.label}
                >
                  {node.label}
                </p>

                {/* Subtitle */}
                <p className="mt-0.5 w-full truncate text-[8px] leading-tight text-text-muted" title={node.subtitle}>
                  {node.subtitle}
                </p>

                {/* Metric badge */}
                {metric && (
                  <span className="mt-1 inline-block rounded px-1.5 py-0.5 text-[8px] font-mono leading-none"
                    style={{
                      color: a.active ? a.labelColor : "#8B96A3",
                      backgroundColor: a.active ? "rgba(255,255,255,0.08)" : "transparent",
                    }}
                  >
                    {metric}
                  </span>
                )}
              </div>

              {/* Arrow between nodes */}
              {i < PIPELINE_NODES.length - 1 && <Arrow isActive={a.active} />}
            </div>
          );
        })}
      </div>

      {/* Live request highlight bar */}
      {lastEvent && (
        <div className="mt-4 flex items-center gap-2 rounded-lg bg-bg-page p-2">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-tier-simple animate-flow" />
          <span className="truncate font-mono text-[10px] text-text-secondary">
            live: {lastEvent.model_used}
            {lastEvent.cache_hit ? " (cache)" : ""}
            {lastEvent.fallback_used ? " (ollama fallback)" : ""}
            {" · "}
            {lastEvent.latency_ms.toFixed(0)}ms
            {" · "}
            saved ${lastEvent.savings_usd.toFixed(6)}
          </span>
        </div>
      )}
    </div>
  );
}
