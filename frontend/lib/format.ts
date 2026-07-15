// lib/format.ts — display formatters shared across cards, charts, and the feed.

export function money(value: number, dp = 4): string {
  return `$${value.toFixed(dp)}`;
}

export function pct(value: number, dp = 1): string {
  return `${value.toFixed(dp)}%`;
}

export function commas(value: number): string {
  return value.toLocaleString("en-US");
}

/** Short clock label (HH:MM) for chart axes. Accepts an ISO string. */
export function clock(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}

/**
 * Relative time like "3s ago" / "5m ago". Accepts either the WS `timestamp` or a
 * REST row `created_at` — both are ISO strings.
 */
export function relativeTime(iso: string, nowMs: number = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.max(0, Math.round((nowMs - then) / 1000));
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}
