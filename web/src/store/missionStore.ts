/**
 * The mission store is the one place mission data, agent state and the event
 * stream meet.
 *
 *   - `mission`  live mode: the canonical Mission, seeded from a REST GET and
 *                patched event-by-event via `applyEventToMission`.
 *                replay mode: recomputed from scratch each tick by folding
 *                `fullEventLog[0..replayIndex]` onto an empty skeleton -
 *                the backend is never called during replay.
 *   - `events`   the event log visible right now (full log live, a prefix
 *                during replay) - what the activity feed and the 3D layer
 *                derive agent state from.
 *
 * Components only ever read this store through selectors; nothing in
 * `components/3d` writes to it or invents state.
 */
import { create } from "zustand";
import { applyEventToMission, emptyMissionSkeleton, reduceMissionFromEvents } from "@/lib/missionReducer";
import type { ApprovalRequest, Mission, MissionEvent } from "@/lib/types";

export type ConnectionState = "connecting" | "open" | "closed" | "error";
export type ViewMode = "live" | "replay";

interface MissionStoreState {
  mission: Mission | null;
  events: MissionEvent[];
  fullEventLog: MissionEvent[];
  connection: ConnectionState;
  mode: ViewMode;
  replayIndex: number;
  replayPlaying: boolean;
  replaySpeed: number;

  hydrate: (mission: Mission, events: MissionEvent[]) => void;
  applyEvent: (event: MissionEvent) => void;
  setConnection: (state: ConnectionState) => void;
  patchApproval: (approval: ApprovalRequest) => void;
  reset: () => void;

  enterReplay: () => void;
  exitReplay: () => void;
  setReplayIndex: (index: number) => void;
  setReplayPlaying: (playing: boolean) => void;
  setReplaySpeed: (speed: number) => void;
}

function missionAtReplayIndex(fullEventLog: MissionEvent[], index: number, seed: Mission): Mission {
  const skeleton = emptyMissionSkeleton(seed.id, seed.goal, seed.created_at);
  return reduceMissionFromEvents(skeleton, fullEventLog.slice(0, index));
}

export const useMissionStore = create<MissionStoreState>((set, get) => ({
  mission: null,
  events: [],
  fullEventLog: [],
  connection: "connecting",
  mode: "live",
  replayIndex: 0,
  replayPlaying: false,
  replaySpeed: 1,

  hydrate: (mission, events) => {
    set({ mission, events, fullEventLog: events, mode: "live" });
  },

  applyEvent: (event) => {
    const { mission, events, mode, fullEventLog } = get();
    if (!mission) return;
    if (events.some((e) => e.id === event.id)) return; // dedupe SSE reconnect replays

    const nextEvents = [...events, event].sort((a, b) => a.sequence - b.sequence);
    const nextFullLog = fullEventLog.some((e) => e.id === event.id)
      ? fullEventLog
      : [...fullEventLog, event].sort((a, b) => a.sequence - b.sequence);

    if (mode === "live") {
      set({
        mission: applyEventToMission(mission, event),
        events: nextEvents,
        fullEventLog: nextFullLog,
      });
    } else {
      // Still record it for replay's log, but don't let a live event mutate
      // the mission snapshot a paused/playing replay is currently showing.
      set({ fullEventLog: nextFullLog });
    }
  },

  setConnection: (state) => set({ connection: state }),

  patchApproval: (approval) => {
    const { mission } = get();
    if (!mission) return;
    const exists = mission.approvals.some((a) => a.id === approval.id);
    const approvals = exists
      ? mission.approvals.map((a) => (a.id === approval.id ? approval : a))
      : [...mission.approvals, approval];
    set({ mission: { ...mission, approvals } });
  },

  reset: () =>
    set({
      mission: null,
      events: [],
      fullEventLog: [],
      connection: "connecting",
      mode: "live",
      replayIndex: 0,
      replayPlaying: false,
      replaySpeed: 1,
    }),

  enterReplay: () => {
    const { fullEventLog, mission } = get();
    if (!mission) return;
    set({
      mode: "replay",
      replayIndex: 0,
      replayPlaying: false,
      events: [],
      mission: missionAtReplayIndex(fullEventLog, 0, mission),
    });
  },

  exitReplay: () => {
    const { fullEventLog, mission } = get();
    if (!mission) return;
    set({
      mode: "live",
      replayPlaying: false,
      events: fullEventLog,
      mission: missionAtReplayIndex(fullEventLog, fullEventLog.length, mission),
    });
  },

  setReplayIndex: (index) => {
    const { fullEventLog, mission } = get();
    if (!mission) return;
    const clamped = Math.max(0, Math.min(index, fullEventLog.length));
    set({
      replayIndex: clamped,
      events: fullEventLog.slice(0, clamped),
      mission: missionAtReplayIndex(fullEventLog, clamped, mission),
    });
  },
  setReplayPlaying: (playing) => set({ replayPlaying: playing }),
  setReplaySpeed: (speed) => set({ replaySpeed: speed }),
}));
