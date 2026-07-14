// lib/colors.ts — tier palette, kept identical to dashboard/app.py TIER_COLORS
// so the Next.js dashboard and the Streamlit dashboard read as one product.

export const TIER_COLORS = {
  cache: "#4E79A7",
  simple: "#59A14F",
  medium: "#F28E2B",
  complex: "#E15759",
} as const;

export function tierColor(tier: string): string {
  return TIER_COLORS[tier as keyof typeof TIER_COLORS] ?? "#9CA3AF";
}
