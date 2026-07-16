// lib/api.ts — typed fetchers for the gateway's read endpoints.
// Base URL is browser-exposed (NEXT_PUBLIC_API_URL). `cache: "no-store"` so the
// App Router never statically caches live analytics.

import type { HealthResponse, RequestsResponse, StatsResponse } from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return (await res.json()) as T;
}

export function getStats(): Promise<StatsResponse> {
  return getJson<StatsResponse>("/v1/stats");
}

export function getRequests(limit = 50): Promise<RequestsResponse> {
  return getJson<RequestsResponse>(`/v1/requests?limit=${limit}`);
}

export function getHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health");
}

export function getRequestHistory(
  page = 1,
  pageSize = 5,
  filter?: string,
): Promise<RequestsResponse> {
  const params = new URLSearchParams({ limit: String(pageSize), page: String(page) });
  if (filter === "cache") params.set("cache_hits_only", "true");
  else if (filter === "fallback") params.set("fallback_only", "true");
  else if (filter && filter !== "all") params.set("tier", filter);
  return getJson<RequestsResponse>(`/v1/requests?${params}`);
}
