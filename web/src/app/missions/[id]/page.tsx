"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AgentRoster } from "@/components/3d/AgentRoster";
import { DynamicScene } from "@/components/3d/DynamicScene";
import { AccessibleMissionState } from "@/components/mission/AccessibleMissionState";
import { AgentInspector } from "@/components/mission/AgentInspector";
import { CompletionPanel } from "@/components/mission/CompletionPanel";
import { GuardianOverlay } from "@/components/mission/GuardianOverlay";
import { MissionHud } from "@/components/mission/MissionHud";
import { MissionInterrupted } from "@/components/mission/MissionInterrupted";
import { MissionTimeline } from "@/components/mission/MissionTimeline";
import { ReplayControls } from "@/components/mission/ReplayControls";
import { StrandsMark } from "@/components/mission/StrandsMark";
import { TaskPanel } from "@/components/mission/TaskPanel";
import type { CharacterId } from "@/lib/agents";
import {
  computeActivityLabels,
  computeAgentInspector,
  computeAllStatuses,
  computeConnections,
  computeProgress,
} from "@/lib/deriveAgentState";
import { useMissionEvents } from "@/lib/useMissionEvents";
import { useMissionStore, type ConnectionState } from "@/store/missionStore";

export default function MissionControlPage() {
  const { id } = useParams<{ id: string }>();
  const [retryToken, setRetryToken] = useState(0);
  useMissionEvents(id, retryToken);

  const mission = useMissionStore((s) => s.mission);
  const events = useMissionStore((s) => s.events);
  const mode = useMissionStore((s) => s.mode);
  const connection = useMissionStore((s) => s.connection);
  const enterReplay = useMissionStore((s) => s.enterReplay);
  const exitReplay = useMissionStore((s) => s.exitReplay);
  const [inspecting, setInspecting] = useState<CharacterId | null>(null);

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

  // An error before the first event means the stream never opened - the
  // backend is unreachable or the mission does not exist. An error *after*
  // we have a mission is a transient reconnect, which the header indicator
  // reports without tearing the whole interface down.
  if (!mission && connection === "error") {
    return <MissionInterrupted missionId={id} onRetry={() => setRetryToken((t) => t + 1)} />;
  }

  if (!mission || !derived) {
    return (
      <main className="flex h-dvh items-center justify-center bg-paper">
        <div className="flex flex-col items-center gap-3 text-ink-500" role="status">
          <ConnectionIndicator state={connection} />
          <p className="text-xs">Initializing autonomous workforce…</p>
        </div>
      </main>
    );
  }

  const pendingApproval = mission.approvals.find((a) => a.status === "PENDING") ?? null;
  const showCompletion = mission.status === "COMPLETED" || mission.status === "FAILED";
  const inspectorData = inspecting ? computeAgentInspector(inspecting, mission, events, derived.statuses) : null;

  const latestEvent = events.length > 0 ? events[events.length - 1] : null;

  return (
    <main className="relative h-dvh w-full overflow-hidden bg-paper">
      <AccessibleMissionState
        mission={mission}
        statuses={derived.statuses}
        latestEventText={latestEvent?.message ?? null}
        onSelect={setInspecting}
      />

      <div className="absolute inset-0">
        <DynamicScene pulledBack={!!pendingApproval} dimmed={!!pendingApproval}>
          <AgentRoster
            statuses={derived.statuses}
            activity={derived.activity}
            edges={derived.edges}
            focusedId={pendingApproval ? "guardian" : inspecting}
            dimAll={!!pendingApproval}
            onSelect={mode === "live" ? setInspecting : undefined}
          />
        </DynamicScene>
      </div>

      <header className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-center justify-between p-4 sm:p-6">
        <Link
          href="/"
          className="pointer-events-auto text-xs font-semibold tracking-wide2 text-ink-500 transition hover:text-ink-900"
        >
          &larr; Hion
        </Link>
        <div className="pointer-events-auto">
          <ConnectionIndicator state={connection} compact />
        </div>
      </header>

      <div className="pointer-events-none absolute inset-x-0 top-14 z-10 flex flex-col items-center gap-3 px-4 sm:top-16">
        <div className="pointer-events-auto w-full max-w-xl">
          <MissionHud mission={mission} progress={derived.progress} />
        </div>
        {/* On phones and tablets the plan and log stack under the HUD,
            collapsed by default; at desktop widths they move to the fixed
            side rails below instead - a real layout change, not just shrunk
            sidebars. */}
        <div className="pointer-events-auto w-full max-w-xl space-y-2 lg:hidden">
          <TaskPanel tasks={mission.tasks} defaultCollapsed />
          <MissionTimeline events={events} defaultCollapsed />
        </div>
      </div>

      {/* Desktop: the plan on the left, the record on the right, the agents
          themselves between them. */}
      {/* Both rails hang below the centred HUD strip rather than beside it, so
          the three never collide at the narrow end of `lg`. */}
      <div className="pointer-events-none absolute left-4 top-44 z-10 hidden max-h-[58vh] w-80 lg:block">
        <div className="pointer-events-auto h-full">
          <TaskPanel tasks={mission.tasks} />
        </div>
      </div>

      <div className="pointer-events-none absolute right-4 top-44 z-10 hidden max-h-[58vh] w-80 lg:block">
        <div className="pointer-events-auto h-full">
          <MissionTimeline events={events} />
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-6 left-6 z-10 hidden sm:block">
        <StrandsMark />
      </div>

      {showCompletion && (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-4 pb-16 pt-24">
          <div className="pointer-events-auto max-h-full overflow-y-auto">
            <CompletionPanel
              mission={mission}
              mode={mode}
              agentsInvolved={new Set(events.map((e) => e.agent).filter(Boolean)).size}
              onReplay={enterReplay}
            />
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

      {inspectorData && (
        <div className="absolute inset-y-0 right-0 z-30 animate-fade-in">
          <AgentInspector data={inspectorData} onClose={() => setInspecting(null)} />
        </div>
      )}
    </main>
  );
}

const CONNECTION_STYLES: Record<ConnectionState, { color: string; label: string }> = {
  connecting: { color: "bg-ink-300 animate-pulse-slow", label: "Connecting" },
  open: { color: "bg-ok", label: "Live" },
  closed: { color: "bg-ink-300", label: "Closed" },
  error: { color: "bg-risk-high", label: "Reconnecting" },
};

function ConnectionIndicator({ state, compact }: { state: ConnectionState; compact?: boolean }) {
  const { color, label } = CONNECTION_STYLES[state];
  return (
    <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest2 text-ink-500">
      <span className={`h-1.5 w-1.5 rounded-full ${color}`} />
      {!compact && label}
    </div>
  );
}
