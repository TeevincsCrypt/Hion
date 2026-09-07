"use client";

import type { AgentInspectorData } from "@/lib/deriveAgentState";
import type { CharacterStatus } from "@/lib/agents";
import type { RiskLevel } from "@/lib/types";
import { formatDuration } from "@/lib/useElapsed";

const STATUS_STYLES: Record<CharacterStatus, string> = {
  IDLE: "text-ink-500 border-line",
  WORKING: "text-accent border-accent/40",
  REVIEWING: "text-accent border-accent/40",
  WAITING: "text-ink-500 border-line",
  COMPLETED: "text-ink-900 border-ink-900/25",
  FAILED: "text-risk-high border-risk-high/40",
};

const RISK_STYLES: Record<RiskLevel, string> = {
  LOW: "text-ink-500 border-line",
  MEDIUM: "text-accent border-accent/40",
  HIGH: "text-risk-high border-risk-high/40",
};

/**
 * The full, real detail behind one character - opened by clicking it in the
 * 3D scene. Every field is `data`, computed in `deriveAgentState.ts` from the
 * mission's own tasks and events; this component only lays it out.
 */
export function AgentInspector({ data, onClose }: { data: AgentInspectorData; onClose: () => void }) {
  return (
    <aside className="pointer-events-auto flex h-full w-full max-w-sm flex-col border-l border-line bg-surface">
      <div className="flex items-start justify-between border-b border-line px-6 py-5">
        <div>
          <h2 className="text-lg font-semibold text-ink-900">{data.label}</h2>
          <p className="mt-1 text-[13px] text-ink-500">{data.role}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close inspector"
          className="-mr-1 -mt-1 rounded-full p-1.5 text-ink-500 transition hover:bg-paper-dim hover:text-ink-900"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide2 ${STATUS_STYLES[data.status]}`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {data.status.replace("_", " ")}
        </span>

        <dl className="mt-6 space-y-5">
          <Field label="Current task" value={data.currentTask} />
          <Field
            label="Tools used"
            value={data.toolsUsed.length > 0 ? data.toolsUsed.join(", ") : null}
          />
          <div className="grid grid-cols-3 gap-4">
            <Stat label="Completed" value={String(data.completedTasks)} />
            <Stat label="Retries" value={data.retries != null ? String(data.retries) : "—"} />
            <Stat
              label="Duration"
              value={data.durationSeconds != null ? formatDuration(Math.round(data.durationSeconds)) : "—"}
            />
          </div>
          {data.riskLevel && (
            <div>
              <dt className="text-[10px] font-medium uppercase tracking-widest2 text-ink-300">Risk level</dt>
              <dd className="mt-1.5">
                <span
                  className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${RISK_STYLES[data.riskLevel]}`}
                >
                  {data.riskLevel}
                </span>
              </dd>
            </div>
          )}
          <Field label="Result summary" value={data.resultSummary} multiline />
        </dl>
      </div>

      <div className="border-t border-line px-6 py-4">
        <p className="font-mono text-[11px] text-ink-300">
          Runtime process <span className="text-ink-500">hion-{data.id}</span> · Strands Agent
        </p>
      </div>
    </aside>
  );
}

function Field({ label, value, multiline }: { label: string; value: string | null; multiline?: boolean }) {
  return (
    <div>
      <dt className="text-[10px] font-medium uppercase tracking-widest2 text-ink-300">{label}</dt>
      <dd
        className={`mt-1.5 text-[13px] leading-relaxed text-ink-600 ${multiline ? "" : "truncate"}`}
        title={value ?? undefined}
      >
        {value ?? <span className="text-ink-300">—</span>}
      </dd>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-medium uppercase tracking-widest2 text-ink-300">{label}</dt>
      <dd className="mt-1 text-[15px] font-medium text-ink-900">{value}</dd>
    </div>
  );
}
