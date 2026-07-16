"use client";

// components/ModelDistribution.tsx — One bar per ACTUAL model served.
// Always renders the ollama row even at 0% so the fallback path is visibly monitored.

import type { ModelCount } from "@/lib/types";
import { tierColor, tierBg } from "@/lib/colors";

export default function ModelDistribution({ data }: { data: ModelCount[] }) {
  const maxCount = Math.max(1, ...data.map((d) => d.count));

  return (
    <div className="rounded-xl border border-bg-border bg-bg-card p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-secondary">
        Model distribution
      </h3>
      <div className="space-y-3">
        {data.map((d) => {
          const pct = maxCount > 0 ? (d.count / maxCount) * 100 : 0;
          const isOllama = d.model.includes("ollama");
          return (
            <div key={d.model}>
              <div className="mb-1 flex items-center justify-between text-[11px]">
                <span
                  className={`font-mono ${isOllama ? "text-text-muted" : "text-text-primary"}`}
                >
                  {d.model.replace("groq/", "").replace("openai/", "")}
                </span>
                <span className="font-mono text-[10px] text-text-secondary">
                  {d.count.toLocaleString("en-US")} ({d.pct.toFixed(1)}%)
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-bg-page">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: isOllama ? "#5F6A76" : d.count > 0 ? "#5DCAA5" : "#1B2129",
                    opacity: d.count > 0 ? 1 : 0.3,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
