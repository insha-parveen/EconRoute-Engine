// components/KpiRow.tsx — the top row of stat tiles.

import KpiCard from "@/components/KpiCard";
import { TIER_COLORS } from "@/lib/colors";
import { commas, money, pct } from "@/lib/format";
import type { StatsTotals } from "@/lib/types";

export default function KpiRow({ totals }: { totals: StatsTotals }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
      <KpiCard label="Total requests" value={commas(totals.requests)} />
      <KpiCard
        label="Theoretical savings"
        value={money(totals.savings_usd)}
        sublabel="vs GPT-4o baseline"
        accent={TIER_COLORS.simple}
      />
      <KpiCard
        label="Savings vs GPT-4o"
        value={pct(totals.savings_pct)}
        accent={TIER_COLORS.medium}
      />
      <KpiCard
        label="Cache-hit rate"
        value={pct(totals.cache_hit_rate)}
        accent={TIER_COLORS.cache}
      />
      <KpiCard label="Actual spend" value={money(totals.actual_spend, 2)} sublabel="always free" />
    </div>
  );
}
