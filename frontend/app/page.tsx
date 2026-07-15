// app/page.tsx — SERVER component. Fetches initial data (best-effort: falls back
// to empty payloads so the page always renders) and hands it to the client Dashboard.

import Dashboard from "@/components/Dashboard";
import { getRequests, getStats } from "@/lib/api";
import { EMPTY_STATS, type RequestRow, type StatsResponse } from "@/lib/types";

export const dynamic = "force-dynamic"; // always fetch fresh on the server

export default async function Page() {
  let stats: StatsResponse = EMPTY_STATS;
  let requests: RequestRow[] = [];

  const [statsRes, reqRes] = await Promise.allSettled([getStats(), getRequests(50)]);
  if (statsRes.status === "fulfilled") stats = statsRes.value;
  if (reqRes.status === "fulfilled") requests = reqRes.value.requests;

  return <Dashboard initialStats={stats} initialRequests={requests} />;
}
