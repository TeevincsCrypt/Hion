/**
 * A real liveness indicator, not a decorative one: `ready` reflects an
 * actual `GET /api/health` call (see app/page.tsx). `null` while that
 * request is in flight.
 */
export function SystemStatus({ ready }: { ready: boolean | null }) {
  const label = ready === null ? "Connecting" : ready ? "System Ready" : "System Offline";
  const dotClass = ready === null ? "bg-ink-300 animate-pulse-slow" : ready ? "bg-accent" : "bg-risk-high";

  return (
    <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-widest2 text-ink-500">
      <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
      {label}
    </div>
  );
}
