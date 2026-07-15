// components/Card.tsx — masonry card wrapper. break-inside-avoid keeps a card from
// splitting across CSS columns; mb-4 provides the vertical gap columns need.

export default function Card({
  title,
  className = "",
  children,
}: {
  title?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`mb-4 break-inside-avoid rounded-xl bg-panel p-4 shadow-card ${className}`}
    >
      {title ? (
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          {title}
        </h2>
      ) : null}
      {children}
    </div>
  );
}
