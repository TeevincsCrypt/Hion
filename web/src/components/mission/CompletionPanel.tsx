"use client";

import type { Mission } from "@/lib/types";
import { formatDuration } from "@/lib/useElapsed";

interface CompletionPanelProps {
  mission: Mission;
  mode: "live" | "replay";
  onReplay: () => void;
}

/**
 * The mission's outcome, using only what the backend actually reported:
 * `mission.final_result` and the `MissionMetrics` computed server-side at
 * `GET /api/missions/{id}/metrics` (mirrored here via the same field the
 * mission.completed / mission.failed event carries). Nothing is estimated.
 */
export function CompletionPanel({ mission, mode, onReplay }: CompletionPanelProps) {
  const failed = mission.status === "FAILED";

  return (
    <div className="animate-fade-up panel w-full max-w-2xl rounded-2xl p-7">
      <p
        className={`text-center text-[11px] font-semibold uppercase tracking-widest2 ${failed ? "text-danger" : "text-ok"}`}
      >
        {failed ? "Mission Failed" : "Mission Complete"}
      </p>

      {mission.metrics && (
        <div className="mt-5 grid grid-cols-3 gap-4 border-y border-white/[0.06] py-4 sm:grid-cols-4">
          <Stat label="Tasks" value={String(mission.metrics.total_tasks)} />
          <Stat label="Completed" value={String(mission.metrics.completed_tasks)} />
          <Stat label="Retries" value={String(mission.metrics.retries)} />
          <Stat label="Agent calls" value={String(mission.metrics.agent_invocations)} />
          <Stat label="Tool calls" value={String(mission.metrics.tool_calls)} />
          <Stat label="Human decisions" value={String(mission.metrics.approvals_requested)} />
          <Stat label="Duration" value={formatDuration(Math.round(mission.metrics.duration_seconds))} />
          <Stat
            label="Critic avg"
            value={mission.metrics.average_critic_score != null ? `${mission.metrics.average_critic_score}` : "—"}
          />
        </div>
      )}

      {mission.final_result && (
        <div className="mt-5 max-h-64 overflow-y-auto rounded-xl bg-white/[0.03] px-4 py-3">
          <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-white/70">{mission.final_result}</p>
        </div>
      )}
      {failed && mission.error && (
        <p className="mt-5 rounded-xl bg-danger/10 px-4 py-3 text-[13px] leading-relaxed text-danger/90">
          {mission.error}
        </p>
      )}

      {mode === "live" && (
        <div className="mt-6 flex justify-center">
          <button
            type="button"
            onClick={onReplay}
            className="rounded-full border border-white/15 px-5 py-2 text-xs font-semibold uppercase tracking-widest2 text-white/75 transition hover:border-white/30 hover:text-white"
          >
            Replay Mission
          </button>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <p className="truncate text-lg font-medium text-white/90">{value}</p>
      <p className="mt-0.5 text-[10px] uppercase tracking-widest2 text-white/35">{label}</p>
    </div>
  );
}
