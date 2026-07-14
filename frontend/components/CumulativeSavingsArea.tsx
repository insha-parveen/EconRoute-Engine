"use client";

// components/CumulativeSavingsArea.tsx — running theoretical savings over time.

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TIER_COLORS } from "@/lib/colors";
import { clock, money } from "@/lib/format";
import type { CumulativePoint } from "@/lib/types";

export default function CumulativeSavingsArea({ data }: { data: CumulativePoint[] }) {
  if (data.length === 0) {
    return <p className="text-sm text-slate-400">No data yet.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="timestamp" tickFormatter={clock} fontSize={11} minTickGap={40} />
        <YAxis tickFormatter={(v) => money(Number(v), 3)} fontSize={11} width={64} />
        <Tooltip
          labelFormatter={(l) => clock(String(l))}
          formatter={(v) => [money(Number(v), 5), "Cumulative savings"]}
        />
        <Area
          type="monotone"
          dataKey="cumulative_savings"
          stroke={TIER_COLORS.simple}
          fill={TIER_COLORS.simple}
          fillOpacity={0.2}
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
