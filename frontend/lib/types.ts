// lib/types.ts — TypeScript mirrors of the FastAPI payloads.
// NOTE: the WS live event uses `timestamp`; the REST request rows use `created_at`.
// They are kept as distinct types on purpose (see lib/format.ts::relativeTime which
// accepts either).

export interface StatsTotals {
  requests: number;
  savings_usd: number;
  baseline_usd: number;
  savings_pct: number;
  cache_hit_rate: number;
  actual_spend: number;
}

export interface TierCount {
  tier: string;
  count: number;
}

export interface LatencyPercentile {
  tier: string;
  p50: number;
  p95: number;
  count: number;
}

export interface CumulativePoint {
  timestamp: string;
  cumulative_savings: number;
}

export interface CacheHitMiss {
  hit: number;
  miss: number;
}

export interface StatsResponse {
  totals: StatsTotals;
  tier_distribution: TierCount[];
  latency_percentiles: LatencyPercentile[];
  cumulative_savings: CumulativePoint[];
  cache_hit_vs_miss: CacheHitMiss;
}

export interface RequestRow {
  created_at: string;
  tier: string;
  model_used: string;
  query_id: string;
  cache_hit: boolean;
  fallback_used: boolean;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  theoretical_cost_usd: number;
  baseline_cost_usd: number;
  savings_usd: number;
  savings_source: string;
}

export interface RequestsResponse {
  requests: RequestRow[];
}

export interface HealthResponse {
  status: string;
  cache: string;
  db: string;
  groq: string;
}

// The WebSocket /ws/requests event (broadcast by gateway/router.py).
export interface LiveEvent {
  type: "request";
  id: string;
  query_id: string;
  tier: string;
  model_used: string;
  cache_hit: boolean;
  fallback_used: boolean;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  actual_cost_usd: number;
  theoretical_cost_usd: number;
  baseline_cost_usd: number;
  savings_usd: number;
  savings_source: string;
  timestamp: string;
}

export const EMPTY_STATS: StatsResponse = {
  totals: {
    requests: 0,
    savings_usd: 0,
    baseline_usd: 0,
    savings_pct: 0,
    cache_hit_rate: 0,
    actual_spend: 0,
  },
  tier_distribution: [],
  latency_percentiles: [],
  cumulative_savings: [],
  cache_hit_vs_miss: { hit: 0, miss: 0 },
};
