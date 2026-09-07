"use client";

import { CHARACTER_IDS, ROSTER, type CharacterId, type CharacterStatus } from "@/lib/agents";
import type { Mission } from "@/lib/types";

const STATUS_WORD: Record<CharacterStatus, string> = {
  IDLE: "idle",
  WORKING: "working",
  REVIEWING: "reviewing",
  WAITING: "waiting",
  COMPLETED: "completed",
  FAILED: "failed",
};

/**
 * Mission state for people who are not looking at the 3D scene.
 *
 * Two jobs. A polite live region narrates status changes and the latest real
 * event, so a screen reader follows the mission without the canvas. And the
 * roster below is a genuine keyboard path into the Agent Inspector - the 3D
 * characters are pointer targets, which on their own would make the inspector
 * mouse-only. The controls are visually hidden until focused, so keyboard and
 * screen-reader users get a real route in without adding furniture to a
 * deliberately spare interface.
 */
export function AccessibleMissionState({
  mission,
  statuses,
  latestEventText,
  onSelect,
}: {
  mission: Mission;
  statuses: Record<CharacterId, CharacterStatus>;
  latestEventText: string | null;
  onSelect: (id: CharacterId) => void;
}) {
  return (
    <>
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {`Mission ${mission.status.toLowerCase().replace(/_/g, " ")}.`}
        {latestEventText ? ` Latest: ${latestEventText}.` : ""}
      </div>

      <nav aria-label="Agents" className="absolute left-0 top-0 z-40">
        <ul className="flex">
          {CHARACTER_IDS.map((id) => (
            <li key={id}>
              <button
                type="button"
                onClick={() => onSelect(id)}
                className="sr-only focus:not-sr-only focus:m-2 focus:inline-block focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-xs focus:text-ink-900 focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-ink-900"
              >
                {`${ROSTER[id].label}: ${STATUS_WORD[statuses[id]]}. Open inspector`}
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}
