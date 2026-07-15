"use client";

// components/LatencyBar.tsx — p50/p95 latency per tier.

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TIER_COLORS } from "@/lib/colors";
import type { LatencyPercentile } from "@/lib/types";

export default function LatencyBar({ data }: { data: LatencyPercentile[] }) {
  if (data.length === 0) {
    return <p className="text-sm text-slate-400">No data yet.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="tier" fontSize={11} />
        <YAxis fontSize={11} width={48} unit="ms" />
        <Tooltip formatter={(v, n) => [`${Number(v).toFixed(1)} ms`, String(n).toUpperCase()]} />
        <Legend />
        <Bar dataKey="p50" name="p50" fill={TIER_COLORS.cache} radius={[3, 3, 0, 0]} />
        <Bar dataKey="p95" name="p95" fill={TIER_COLORS.complex} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
