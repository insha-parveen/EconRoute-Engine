"use client";

// components/RequestHistoryTable.tsx — Server-paginated, sortable, filterable
// request history table with row click → right-side detail drawer.
// Default: 5 most recent requests ("at a glance").

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { tierColor, tierBg, tierBorder, type TierKey } from "@/lib/colors";
import type { RequestRow, RequestsResponse } from "@/lib/types";
import { getRequestHistory } from "@/lib/api";

type SortField = "created_at" | "tier" | "model_used" | "latency_ms" | "savings_usd";
type FilterKey = "all" | "cache" | "fallback" | "simple" | "medium" | "complex";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "cache", label: "Cache hits" },
  { key: "fallback", label: "Fallback only" },
  { key: "simple", label: "Simple" },
  { key: "medium", label: "Medium" },
  { key: "complex", label: "Complex" },
];

function sortRows(rows: RequestRow[], field: SortField, dir: "asc" | "desc"): RequestRow[] {
  return [...rows].sort((a, b) => {
    let cmp: number;
    switch (field) {
      case "created_at": cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime(); break;
      case "model_used": cmp = a.model_used.localeCompare(b.model_used); break;
      case "latency_ms": cmp = a.latency_ms - b.latency_ms; break;
      case "savings_usd": cmp = a.savings_usd - b.savings_usd; break;
      case "tier": cmp = a.tier.localeCompare(b.tier); break;
      default: cmp = 0;
    }
    return dir === "asc" ? cmp : -cmp;
  });
}

export default function RequestHistoryTable({
  initialRequests,
  total: initialTotal,
}: {
  initialRequests: RequestRow[];
  total: number;
}) {
  const [rows, setRows] = useState<RequestRow[]>(initialRequests);
  const [totalRows, setTotalRows] = useState(initialTotal);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selectedRow, setSelectedRow] = useState<RequestRow | null>(null);
  const [loading, setLoading] = useState(false);
  const pageSize = 5;

  const fetchData = useCallback(async () => {
    setLoading(true);
    const data = await getRequestHistory(page, pageSize, filter);
    const sorted = sortRows(data.requests, sortField, sortDir);
    setRows(sorted);
    setTotalRows(data.total);
    setLoading(false);
  }, [page, filter, sortField, sortDir]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
    setPage(1);
  };

  const SortArrow = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="ml-1 text-text-muted">↕</span>;
    return <span className="ml-1 text-tier-simple">{sortDir === "desc" ? "↓" : "↑"}</span>;
  };

  const routingPill = (reason: string) => {
    const tier = reason.includes("cache") ? "cache"
      : reason.includes("simple") ? "simple"
      : reason.includes("medium") ? "medium"
      : reason.includes("complex") ? "complex"
      : "fallback";
    return (
      <span
        className="inline-block rounded-full px-2 py-0.5 text-[10px] font-mono"
        style={{
          color: tierColor(tier),
          backgroundColor: tierBg(tier),
          border: `1px solid ${tierBorder(tier)}`,
        }}
      >
        {reason}
      </span>
    );
  };

  return (
    <div className="rounded-xl border border-bg-border bg-bg-card">
      {/* Filters */}
      <div className="flex flex-wrap gap-2 border-b border-bg-border px-4 py-3">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => { setFilter(f.key); setPage(1); }}
            className={`rounded-md px-3 py-1 text-[11px] font-semibold uppercase tracking-wider transition ${
              filter === f.key
                ? "bg-tier-simple text-black"
                : "bg-bg-page text-text-secondary hover:text-text-primary"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-bg-border text-text-muted">
              <Th onClick={() => handleSort("created_at")}>
                Time <SortArrow field="created_at" />
              </Th>
              <Th onClick={() => handleSort("model_used")}>
                Model <SortArrow field="model_used" />
              </Th>
              <Th>Tokens</Th>
              <Th onClick={() => handleSort("latency_ms")}>
                Latency <SortArrow field="latency_ms" />
              </Th>
              <Th onClick={() => handleSort("savings_usd")}>
                Savings <SortArrow field="savings_usd" />
              </Th>
              <Th>Routing</Th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-text-muted">
                  Loading...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-text-muted">
                  No requests match this filter.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr
                  key={r.created_at + r.query_id}
                  onClick={() => setSelectedRow(r)}
                  className="cursor-pointer border-b border-bg-border/50 transition hover:bg-white/5 animate-rowin"
                >
                  <td className="px-4 py-3 font-mono text-[10px] text-text-secondary">
                    {new Date(r.created_at).toLocaleTimeString("en-US", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                      hour12: false,
                    })}
                  </td>
                  <td className="px-4 py-3 font-mono text-[10px] text-text-primary">
                    {r.model_used}
                  </td>
                  <td className="px-4 py-3 font-mono text-[10px] text-text-secondary">
                    {r.input_tokens}→{r.output_tokens}
                  </td>
                  <td className="px-4 py-3 font-mono text-[10px] text-text-secondary">
                    {r.latency_ms.toFixed(0)}ms
                  </td>
                  <td className="px-4 py-3 font-mono text-[10px] text-tier-simple">
                    ${r.savings_usd.toFixed(6)}
                  </td>
                  <td className="px-4 py-3">{routingPill(r.routing_reason)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-bg-border px-4 py-3">
        <span className="text-[10px] text-text-muted">
          {totalRows.toLocaleString("en-US")} total requests
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded px-2 py-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-30"
          >
            ← Prev
          </button>
          <span className="font-mono text-[10px] text-text-secondary">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded px-2 py-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-30"
          >
            Next →
          </button>
        </div>
      </div>

      {/* Detail drawer */}
      {selectedRow && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40"
            onClick={() => setSelectedRow(null)}
          />
          <div className="fixed right-0 top-0 z-50 h-full w-96 overflow-y-auto border-l border-bg-border bg-bg-card p-6 shadow-2xl">
            <button
              onClick={() => setSelectedRow(null)}
              className="mb-4 text-sm text-text-muted hover:text-text-primary"
            >
              ✕ Close
            </button>
            <h3 className="mb-4 text-sm font-semibold text-text-primary">
              Request detail
            </h3>

            <div className="space-y-4">
              <DetailSection label="Routing Decision">
                <DetailRow label="Tier" value={selectedRow.tier} />
                <DetailRow label="Model" value={selectedRow.model_used} />
                <DetailRow label="Reason" value={selectedRow.routing_reason} />
                <DetailRow label="Cache hit" value={String(selectedRow.cache_hit)} />
                <DetailRow label="Fallback" value={String(selectedRow.fallback_used)} />
              </DetailSection>

              <DetailSection label="Cost Breakdown">
                <DetailRow label="Actual cost" value="$0.00000" />
                <DetailRow label="Theoretical cost" value={`$${selectedRow.theoretical_cost_usd.toFixed(6)}`} />
                <DetailRow label="Baseline (GPT-4o)" value={`$${selectedRow.baseline_cost_usd.toFixed(6)}`} />
                <DetailRow label="Savings" value={`$${selectedRow.savings_usd.toFixed(6)}`} accent />
                <DetailRow label="Source" value={selectedRow.savings_source} />
              </DetailSection>

              <DetailSection label="Performance">
                <DetailRow label="Latency" value={`${selectedRow.latency_ms.toFixed(0)}ms`} />
                <DetailRow label="Input tokens" value={String(selectedRow.input_tokens)} />
                <DetailRow label="Output tokens" value={String(selectedRow.output_tokens)} />
              </DetailSection>

              {/* Dimmed pipeline copy */}
              <div className="mt-6 rounded-lg border border-bg-border bg-bg-page p-4 opacity-60">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Request Path
                </p>
                <p className="font-mono text-[10px] text-text-secondary">
                  {selectedRow.cache_hit
                    ? "request → semantic cache"
                    : `request → classifier → ${selectedRow.model_used}${selectedRow.fallback_used ? " (via Ollama fallback)" : ""}`
                  }
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function Th({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <th
      className={`px-4 py-3 text-[10px] font-semibold uppercase tracking-wider ${
        onClick ? "cursor-pointer hover:text-text-primary" : ""
      }`}
      onClick={onClick}
    >
      {children}
    </th>
  );
}

function DetailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        {label}
      </p>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function DetailRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-text-muted">{label}</span>
      <span
        className={`font-mono text-[11px] ${
          accent ? "text-tier-simple" : "text-text-primary"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
