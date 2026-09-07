import type { MissionStatus } from "@/lib/types";

const STYLES: Record<MissionStatus, string> = {
  PLANNING: "text-white/60 border-white/15",
  RUNNING: "text-signal-research border-signal-research/40",
  WAITING_FOR_APPROVAL: "text-signal-guardian border-signal-guardian/40",
  COMPLETED: "text-ok border-ok/40",
  FAILED: "text-danger border-danger/40",
};

const LABELS: Record<MissionStatus, string> = {
  PLANNING: "Planning",
  RUNNING: "Running",
  WAITING_FOR_APPROVAL: "Awaiting approval",
  COMPLETED: "Complete",
  FAILED: "Failed",
};

export function StatusBadge({ status }: { status: MissionStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-widest2 ${STYLES[status]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {LABELS[status]}
    </span>
  );
}
