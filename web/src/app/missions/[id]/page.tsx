"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AgentRoster } from "@/components/3d/AgentRoster";
import { DynamicScene } from "@/components/3d/DynamicScene";
import { ActivityPanel } from "@/components/mission/ActivityPanel";
import { CompletionPanel } from "@/components/mission/CompletionPanel";
import { GuardianOverlay } from "@/components/mission/GuardianOverlay";
import { MissionHud } from "@/components/mission/MissionHud";
import { ReplayControls } from "@/components/mission/ReplayControls";
import {
  computeActivityLabels,
  computeAllStatuses,
  computeConnections,
  computeProgress,
} from "@/lib/deriveAgentState";
import { useMissionEvents } from "@/lib/useMissionEvents";
import { useMissionStore, type ConnectionState } from "@/store/missionStore";

export default function MissionControlPage() {
  const { id } = useParams<{ id: string }>();
  useMissionEvents(id);

  const mission = useMissionStore((s) => s.mission);
  const events = useMissionStore((s) => s.events);
  const mode = useMissionStore((s) => s.mode);
  const connection = useMissionStore((s) => s.connection);
  const enterReplay = useMissionStore((s) => s.enterReplay);
  const exitReplay = useMissionStore((s) => s.exitReplay);

  const derived = useMemo(() => {
    if (!mission) return null;
    const statuses = computeAllStatuses(mission, events);
    return {
      statuses,
      edges: computeConnections(mission, events),
      activity: computeActivityLabels(mission, events, statuses),
      progress: computeProgress(mission, statuses),
    };
  }, [mission, events]);

  if (!mission || !derived) {
    return (
      <main className="flex h-dvh items-center justify-center bg-void-950">
        <div className="flex flex-col items-center gap-3 text-white/40">
          <ConnectionIndicator state={connection} />
          <p className="text-xs">Connecting to mission…</p>
        </div>
      </main>
    );
  }

  const pendingApproval = mission.approvals.find((a) => a.status === "PENDING") ?? null;
  const showCompletion = mission.status === "COMPLETED" || mission.status === "FAILED";

  return (
    <main className="relative h-dvh w-full overflow-hidden">
      <div className="absolute inset-0">
        <DynamicScene pulledBack={!!pendingApproval} dimmed={!!pendingApproval}>
          <AgentRoster
            statuses={derived.statuses}
            activity={derived.activity}
            edges={derived.edges}
            focusedId={pendingApproval ? "guardian" : null}
            dimAll={!!pendingApproval}
          />
        </DynamicScene>
      </div>
      <div className="noise-overlay pointer-events-none absolute inset-0 z-10" />

      <header className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-center justify-between p-4 sm:p-6">
        <Link
          href="/"
          className="pointer-events-auto text-xs font-semibold tracking-widest2 text-white/50 transition hover:text-white/85"
        >
          ← HION
        </Link>
        <div className="pointer-events-auto">
          <ConnectionIndicator state={connection} compact />
        </div>
      </header>

      <div className="pointer-events-none absolute inset-x-0 top-14 z-10 flex justify-center px-4 sm:top-16">
        <div className="pointer-events-auto w-full max-w-xl">
          <MissionHud mission={mission} progress={derived.progress} />
        </div>
      </div>

      <div className="pointer-events-none absolute right-4 top-14 z-10 hidden max-h-[55vh] w-80 lg:block lg:top-16">
        <div className="pointer-events-auto h-full">
          <ActivityPanel events={events} />
        </div>
      </div>

      {showCompletion && (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-4 pb-16 pt-24">
          <div className="pointer-events-auto max-h-full overflow-y-auto">
            <CompletionPanel mission={mission} mode={mode} onReplay={enterReplay} />
          </div>
        </div>
      )}

      {mode === "replay" && (
        <div className="pointer-events-none absolute inset-x-0 bottom-6 z-20 flex justify-center px-4">
          <div className="pointer-events-auto w-full max-w-3xl">
            <ReplayControls onExit={exitReplay} />
          </div>
        </div>
      )}

      {mode === "live" && pendingApproval && (
        <GuardianOverlay key={pendingApproval.id} mission={mission} approval={pendingApproval} />
      )}
    </main>
  );
}

const CONNECTION_STYLES: Record<ConnectionState, { color: string; label: string }> = {
  connecting: { color: "bg-white/40", label: "Connecting" },
  open: { color: "bg-ok", label: "Live" },
  closed: { color: "bg-white/25", label: "Closed" },
  error: { color: "bg-danger", label: "Reconnecting" },
};

function ConnectionIndicator({ state, compact }: { state: ConnectionState; compact?: boolean }) {
  const { color, label } = CONNECTION_STYLES[state];
  return (
    <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest2 text-white/40">
      <span className={`h-1.5 w-1.5 rounded-full ${color} ${state === "connecting" ? "animate-pulse-slow" : ""}`} />
      {!compact && label}
    </div>
  );
}
