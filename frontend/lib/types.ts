// lib/types.ts — TypeScript mirrors of the FastAPI payloads.
// NOTE: the WS live event uses `timestamp`; REST rows use `created_at`.

export interface StatsTotals {
  requests: number;
  savings_usd: number;
  baseline_usd: number;
  savings_pct: number;
  cache_hit_rate: number;
  fallback_rate: number;
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

export interface ModelCount {
  model: string;
  count: number;
  pct: number;
}

export interface SavingsSplit {
  cache_usd: number;
  routing_usd: number;
  cache_pct: number;
  routing_pct: number;
}

export interface StatsResponse {
  totals: StatsTotals;
  tier_distribution: TierCount[];
  latency_percentiles: LatencyPercentile[];
  cumulative_savings: CumulativePoint[];
  cache_hit_vs_miss: CacheHitMiss;
  model_distribution: ModelCount[];
  savings_split: SavingsSplit;
}

export interface RequestRow {
  created_at: string;
  tier: string;
  model_used: string;
  query_id: string;
  cache_hit: boolean;
  fallback_used: boolean;
  routing_reason: string;
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
  total: number;
  page: number;
  page_size: number;
}

export interface HealthResponse {
  status: string;
  cache: string;
  db: string;
  groq: string;
}

// POST /v1/chat/completions response (used by the hero demo).
export interface ChatResponse {
  id: string;
  choices: { index: number; message: { role: string; content: string }; finish_reason: string }[];
  model_used: string;
  tier: string;
  cache_hit: boolean;
  latency_ms: number;
  routing_reason: string;
  classifier_confidence: number;
  actual_cost_usd: number;
  theoretical_cost_usd: number;
  baseline_cost_usd: number;
  savings_usd: number;
  savings_source: string;
  input_tokens: number;
  output_tokens: number;
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
  routing_reason: string;
  classifier_confidence: number;
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

// Fixed held-out eval numbers (evals/run_eval.py) — NOT live-computed.
export const EVAL = {
  overall: 88.3,
  simpleRecall: 95.0,
  simpleTier: 95.0,
} as const;

export const EMPTY_STATS: StatsResponse = {
  totals: {
    requests: 0,
    savings_usd: 0,
    baseline_usd: 0,
    savings_pct: 0,
    cache_hit_rate: 0,
    fallback_rate: 0,
    actual_spend: 0,
  },
  tier_distribution: [],
  latency_percentiles: [],
  cumulative_savings: [],
  cache_hit_vs_miss: { hit: 0, miss: 0 },
  model_distribution: [],
  savings_split: { cache_usd: 0, routing_usd: 0, cache_pct: 0, routing_pct: 0 },
};
