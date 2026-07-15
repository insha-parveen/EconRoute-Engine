// components/KpiCard.tsx — a single stat tile.

export default function KpiCard({
  label,
  value,
  sublabel,
  accent = "#0f172a",
}: {
  label: string;
  value: string;
  sublabel?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl bg-panel p-4 shadow-card">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold" style={{ color: accent }}>
        {value}
      </div>
      {sublabel ? <div className="mt-1 text-xs text-slate-400">{sublabel}</div> : null}
    </div>
  );
}
