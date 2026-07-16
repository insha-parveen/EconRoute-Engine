"use client";

// components/HeroDemo.tsx — SECTION 1: Interactive hero demo at the top of the page.
// Centered heading, text input + teal run button, side-by-side comparison cards.

import { useCallback, useState } from "react";
import { TIER_COLORS, TIER_BG, TIER_BORDER, type TierKey } from "@/lib/colors";
import { EVAL } from "@/lib/types";
import type { ChatResponse } from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function chatCompletion(prompt: string): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "auto",
      messages: [{ role: "user", content: prompt }],
    }),
  });
  if (!res.ok) throw new Error(`POST /v1/chat/completions → ${res.status}`);
  return (await res.json()) as ChatResponse;
}

export default function HeroDemo() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCards, setShowCards] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (!prompt.trim() || loading) return;
    setLoading(true);
    setError(null);
    setShowCards(false);
    try {
      const res = await chatCompletion(prompt);
      setResult(res);
      // Small delay for reveal animation
      setTimeout(() => setShowCards(true), 50);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, [prompt, loading]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <section className="w-full bg-bg-page py-16">
      <div className="mx-auto max-w-[480px] text-center">
        <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">
          Try it — type any question below
        </p>
        <div className="flex gap-2">
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Summarize the causes of WW1 in 3 bullet points"
            className="flex-1 rounded-lg border border-bg-border bg-bg-card px-4 py-2.5 text-sm text-text-primary placeholder-text-muted outline-none ring-0 transition focus:border-tier-simple focus:ring-1 focus:ring-tier-simple/30"
            disabled={loading}
          />
          <button
            onClick={handleSubmit}
            disabled={loading || !prompt.trim()}
            className="rounded-lg bg-tier-simple px-5 py-2.5 text-sm font-semibold text-black transition hover:brightness-110 disabled:opacity-40"
          >
            {loading ? "..." : "run"}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-xs text-red-400">{error}</p>
        )}
      </div>

      {/* Comparison cards */}
      {result && (
        <div
          className={`mx-auto mt-8 grid max-w-2xl gap-4 sm:grid-cols-2 ${
            showCards ? "animate-reveal" : "opacity-0"
          }`}
        >
          {/* Left card: GPT-4o baseline */}
          <div className="rounded-xl border border-bg-border bg-bg-card p-5">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-lg">🧠</span>
              <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                if this went to GPT-4o
              </span>
            </div>
            <div className="space-y-2">
              <Row label="Baseline cost" value={`$${result.baseline_cost_usd.toFixed(6)}`} mono />
              <Row label="Input tokens" value={String(result.input_tokens)} mono />
              <Row label="Output tokens" value={String(result.output_tokens)} mono />
            </div>
          </div>

          {/* Right card: EconRoute actual */}
          <div
            className="rounded-xl border-2 p-5"
            style={{
              borderColor: TIER_BORDER[result.tier as TierKey] ?? TIER_BORDER.fallback,
              backgroundColor: TIER_BG[result.tier as TierKey] ?? TIER_BG.fallback,
            }}
          >
            <div className="mb-3 flex items-center gap-2">
              <span className="text-lg">⚡</span>
              <span className="text-xs font-semibold uppercase tracking-wider"
                style={{ color: TIER_COLORS[result.tier as TierKey] ?? TIER_COLORS.fallback }}>
                what EconRoute actually did
              </span>
            </div>
            <div className="space-y-2">
              <Row label="Actual cost" value="$0.00000" mono />
              <Row label="Model used" value={result.model_used} mono small />
              <Row label="Tier" value={result.tier} />
              <Row label="Classifier confidence" value={`${(result.classifier_confidence * 100).toFixed(0)}%`} mono />
            </div>
          </div>
        </div>
      )}

      {/* Savings + eval stat strip */}
      {result && showCards && (
        <p className="mt-6 text-center text-sm text-text-secondary animate-reveal">
          saved{" "}
          <span className="font-display text-tier-simple">
            ${result.savings_usd.toFixed(6)}
          </span>{" "}
          on this request &middot; classifier: {EVAL.overall}% overall &middot;{" "}
          {EVAL.simpleTier}% simple tier
        </p>
      )}
    </section>
  );
}

function Row({
  label,
  value,
  mono,
  small,
}: {
  label: string;
  value: string;
  mono?: boolean;
  small?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-text-muted">{label}</span>
      <span
        className={`font-mono ${small ? "text-[10px]" : "text-xs"} text-text-primary`}
      >
        {value}
      </span>
    </div>
  );
}
