"use client";

/**
 * Live mission hydration, entirely from SSE.
 *
 * The backend's stream endpoint always replays the mission's full historical
 * event log (starting at sequence 1) before switching to live delivery - see
 * `GET /api/missions/{id}/events/stream` in hion/api/routes.py. That means a
 * single EventSource connection is enough to reconstruct the whole mission,
 * whether this is the tab that just created it or a fresh page load of one
 * already in progress: the first frame received is always `mission.created`,
 * which seeds the skeleton the rest of the log is folded onto (see
 * `missionReducer.ts`). No separate REST fetch is needed for the common path.
 */
import { useEffect, useRef } from "react";
import { missionEventStreamUrl } from "./api";
import { emptyMissionSkeleton } from "./missionReducer";
import type { EventType, MissionEvent } from "./types";
import { useMissionStore } from "@/store/missionStore";

/**
 * Every named SSE event the backend can dispatch, kept in lockstep with
 * `hion.domain.enums.EventType`. `stream.heartbeat` is sent as a comment line,
 * not a named event, so it needs no listener.
 */
const EVENT_TYPES: readonly EventType[] = [
  "mission.created",
  "mission.planned",
  "plan.warning",
  "mission.completed",
  "mission.failed",
  "task.created",
  "task.started",
  "task.completed",
  "task.failed",
  "task.retrying",
  "agent.started",
  "agent.completed",
  "agent.failed",
  "tool.started",
  "tool.completed",
  "tool.blocked",
  "critic.started",
  "critic.completed",
  "revision.requested",
  "revision.exhausted",
  "guardian.review",
  "approval.required",
  "approval.granted",
  "approval.rejected",
  "approval.timed_out",
];

/**
 * @param missionId  mission to stream.
 * @param retryToken change this to tear down the current EventSource and open
 *   a fresh one. The effect cleanup closes the previous connection first, so
 *   retrying can never leave two competing streams open.
 */
export function useMissionEvents(missionId: string, retryToken = 0): void {
  const hydrate = useMissionStore((s) => s.hydrate);
  const applyEvent = useMissionStore((s) => s.applyEvent);
  const setConnection = useMissionStore((s) => s.setConnection);
  const reset = useMissionStore((s) => s.reset);
  const bootstrapped = useRef(false);

  useEffect(() => {
    reset();
    bootstrapped.current = false;
    setConnection("connecting");

    const source = new EventSource(missionEventStreamUrl(missionId));

    const onEvent = (raw: MessageEvent<string>) => {
      let event: MissionEvent;
      try {
        event = JSON.parse(raw.data) as MissionEvent;
      } catch {
        return;
      }
      if (!bootstrapped.current) {
        hydrate(emptyMissionSkeleton(missionId, "", event.created_at), []);
        bootstrapped.current = true;
      }
      applyEvent(event);

      // The backend ends the stream once a terminal event is delivered and
      // its own queue is empty. A server-closed SSE response still makes the
      // browser retry by spec, which would just replay the same finished log
      // forever - close our end deliberately once we know the mission is done.
      if (event.type === "mission.completed" || event.type === "mission.failed") {
        source.close();
        setConnection("closed");
      }
    };

    for (const type of EVENT_TYPES) {
      source.addEventListener(type, onEvent);
    }
    source.onopen = () => setConnection("open");
    source.onerror = () => setConnection("error");

    return () => {
      for (const type of EVENT_TYPES) {
        source.removeEventListener(type, onEvent);
      }
      source.close();
    };
  }, [missionId, retryToken, hydrate, applyEvent, setConnection, reset]);
}
