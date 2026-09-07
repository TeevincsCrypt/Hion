"use client";

import { ROSTER, type CharacterId } from "@/lib/agents";
import type { MissionProgress } from "@/lib/deriveAgentState";
import { formatDuration, useElapsedSeconds } from "@/lib/useElapsed";
import type { Mission } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

interface MissionHudProps {
  mission: Mission;
  progress: MissionProgress;
}

/** The minimal command-center readout: one editorial strip, not a dashboard. */
export function MissionHud({ mission, progress }: MissionHudProps) {
  const endedAt =
    mission.status === "COMPLETED" || mission.status === "FAILED" ? mission.updated_at : null;
  const elapsed = useElapsedSeconds(mission.created_at, endedAt);

  return (
    <div className="animate-fade-in surface-panel rounded-lg px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="min-w-0 flex-1 truncate text-[15px] text-ink-900" title={mission.goal}>
          {mission.goal}
        </p>
        <StatusBadge status={mission.status} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line pt-3">
        <Metric label="Tasks" value={`${progress.completedTasks}/${progress.totalTasks}`} />
        {progress.failedTasks > 0 && <Metric label="Failed" value={String(progress.failedTasks)} tone="risk" />}
        <Metric label="Elapsed" value={formatDuration(elapsed)} />
        <Metric label="Active" value={activeLabel(progress.activeAgents)} grow />
      </div>
    </div>
  );
}

function activeLabel(active: CharacterId[]): string {
  if (active.length === 0) return "—";
  return active.map((id) => ROSTER[id].label).join(", ");
}

function Metric({
  label,
  value,
  tone,
  grow,
}: {
  label: string;
  value: string;
  tone?: "risk";
  grow?: boolean;
}) {
  return (
    <div className={`flex items-baseline gap-1.5 ${grow ? "min-w-0" : ""}`}>
      <span className="text-[10px] font-medium uppercase tracking-widest2 text-ink-300">{label}</span>
      <span
        className={`truncate text-[13px] font-medium ${tone === "risk" ? "text-risk-high" : "text-ink-600"}`}
      >
        {value}
      </span>
    </div>
  );
}
