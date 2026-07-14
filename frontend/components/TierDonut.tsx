"use client";

// components/TierDonut.tsx — request distribution across tiers.

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { tierColor } from "@/lib/colors";
import type { TierCount } from "@/lib/types";

export default function TierDonut({ data }: { data: TierCount[] }) {
  if (data.length === 0) {
    return <p className="text-sm text-slate-400">No data yet.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="count" nameKey="tier" innerRadius={60} outerRadius={90} paddingAngle={2}>
          {data.map((d) => (
            <Cell key={d.tier} fill={tierColor(d.tier)} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
