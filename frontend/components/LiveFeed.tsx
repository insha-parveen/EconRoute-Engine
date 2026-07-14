"use client";

// components/LiveFeed.tsx — streaming list of the most recent routed requests.

import { tierColor } from "@/lib/colors";
import { money, relativeTime } from "@/lib/format";
import type { FeedStatus } from "@/lib/useLiveFeed";
import type { LiveEvent } from "@/lib/types";

const STATUS_DOT: Record<FeedStatus, string> = {
  open: "#22c55e",
  connecting: "#f59e0b",
  closed: "#94a3b8",
};

export default function LiveFeed({
  events,
  status,
}: {
  events: LiveEvent[];
  status: FeedStatus;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Live feed
        </h2>
        <span className="flex items-center gap-1.5 text-xs text-slate-400">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: STATUS_DOT[status] }}
          />
          {status}
        </span>
      </div>

      {events.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-400">
          Waiting for requests…
        </p>
      ) : (
        <ul className="space-y-2">
          {events.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2 overflow-hidden">
                <span
                  className="rounded px-2 py-0.5 text-xs font-semibold text-white"
                  style={{ backgroundColor: tierColor(e.tier) }}
                >
                  {e.tier}
                </span>
                <span className="truncate text-slate-600">{e.model_used}</span>
                {e.cache_hit ? (
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                    cache
                  </span>
                ) : null}
                {e.fallback_used ? (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700">
                    fallback
                  </span>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-3 text-xs text-slate-400">
                <span className="font-medium text-tier-simple">
                  +{money(e.savings_usd, 5)}
                </span>
                <span>{e.latency_ms.toFixed(0)}ms</span>
                <span>{relativeTime(e.timestamp)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
