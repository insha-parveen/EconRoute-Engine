// lib/colors.ts — tier palette matching the dark console spec.
// Used by both the hero demo and the cost dashboard.

export const TIER_COLORS = {
  cache: "#5DCAA5",
  simple: "#5DCAA5",
  medium: "#AFA9EC",
  complex: "#EF9F27",
  fallback: "#8B96A3",
} as const;

export const TIER_BG = {
  cache: "#04342C",
  simple: "#04342C",
  medium: "#26215C",
  complex: "#412402",
  fallback: "#1B222B",
} as const;

export const TIER_BORDER = {
  cache: "#1D9E75",
  simple: "#1D9E75",
  medium: "#7F77DD",
  complex: "#BA7517",
  fallback: "#5F6A76",
} as const;

export type TierKey = keyof typeof TIER_COLORS;

export function tierColor(tier: string): string {
  return TIER_COLORS[tier as TierKey] ?? TIER_COLORS.fallback;
}

export function tierBg(tier: string): string {
  return TIER_BG[tier as TierKey] ?? TIER_BG.fallback;
}

export function tierBorder(tier: string): string {
  return TIER_BORDER[tier as TierKey] ?? TIER_BORDER.fallback;
}
