import type { MissionStatus } from "@/lib/types";

// Routine progress stays monochrome; the accent marks the one state that
// needs a human, and risk red marks only failure - color is reserved for
// what actually matters, nowhere else.
const STYLES: Record<MissionStatus, string> = {
  PLANNING: "text-ink-500 border-line",
  RUNNING: "text-ink-600 border-line",
  WAITING_FOR_APPROVAL: "text-accent border-accent/40",
  COMPLETED: "text-ink-900 border-ink-900/25",
  FAILED: "text-risk-high border-risk-high/40",
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
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide2 ${STYLES[status]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {LABELS[status]}
    </span>
  );
}
