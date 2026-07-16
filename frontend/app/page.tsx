// app/page.tsx — SERVER component. Fetches initial data (best-effort: falls back
// to empty payloads so the page always renders) and renders:
//   SECTION 1: HeroDemo (interactive demo)
//   SECTION 2: ConsoleDashboard (cost analytics)

import HeroDemo from "@/components/HeroDemo";
import ConsoleDashboard from "@/components/ConsoleDashboard";
import { getRequests, getStats } from "@/lib/api";
import { EMPTY_STATS, type RequestRow, type StatsResponse } from "@/lib/types";

export const dynamic = "force-dynamic"; // always fetch fresh on the server

export default async function Page() {
  let stats: StatsResponse = EMPTY_STATS;
  let requests: RequestRow[] = [];

  const [statsRes, reqRes] = await Promise.allSettled([getStats(), getRequests(5)]);
  if (statsRes.status === "fulfilled") stats = statsRes.value;
  if (reqRes.status === "fulfilled") requests = reqRes.value.requests;

  return (
    <>
      {/* Section 1 — Hero interactive demo */}
      <HeroDemo />

      {/* Section 2 — Cost console dashboard */}
      <ConsoleDashboard initialStats={stats} initialRequests={requests} />
    </>
  );
}
