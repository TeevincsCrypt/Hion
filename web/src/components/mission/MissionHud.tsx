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

/** The minimal command-center readout, integrated as a thin band rather than a dashboard. */
export function MissionHud({ mission, progress }: MissionHudProps) {
  const endedAt =
    mission.status === "COMPLETED" || mission.status === "FAILED" ? mission.updated_at : null;
  const elapsed = useElapsedSeconds(mission.created_at, endedAt);

  return (
    <div className="animate-fade-in panel rounded-2xl px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm text-white/85" title={mission.goal}>
            {mission.goal}
          </p>
          <p className="mt-1 font-mono text-[11px] text-white/35">{mission.id}</p>
        </div>
        <StatusBadge status={mission.status} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3 border-t border-white/[0.06] pt-3 sm:grid-cols-4">
        <Metric label="Tasks" value={`${progress.completedTasks}/${progress.totalTasks}`} />
        <Metric label="Failed" value={String(progress.failedTasks)} tone={progress.failedTasks > 0 ? "danger" : undefined} />
        <Metric label="Elapsed" value={formatDuration(elapsed)} />
        <Metric label="Active" value={activeLabel(progress.activeAgents)} className="col-span-3 sm:col-span-1" />
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
  className,
}: {
  label: string;
  value: string;
  tone?: "danger";
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="text-[10px] font-medium uppercase tracking-widest2 text-white/30">{label}</p>
      <p className={`mt-0.5 truncate text-sm font-medium ${tone === "danger" ? "text-danger" : "text-white/85"}`}>
        {value}
      </p>
    </div>
  );
}
