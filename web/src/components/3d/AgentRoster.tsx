"use client";

import { useMemo } from "react";
import { CHARACTER_IDS, ROSTER, type CharacterId, type CharacterStatus, type RosterEntry } from "@/lib/agents";
import type { ActivityLabel, ConnectionEdge } from "@/lib/deriveAgentState";
import { AgentCharacter } from "./AgentCharacter";
import { ConnectionLines } from "./ConnectionLines";
import { useLayoutScale } from "./useResponsiveLayout";

interface AgentRosterProps {
  statuses: Record<CharacterId, CharacterStatus>;
  activity?: Partial<Record<CharacterId, ActivityLabel>>;
  edges?: ConnectionEdge[];
  focusedId?: CharacterId | null;
  dimAll?: boolean;
}

/**
 * The full crew, laid out with the Commander upstage-center and the rest
 * arranged around it. This is a pure presentational composition: every prop
 * it takes is already-derived data (see `deriveAgentState.ts`), so it never
 * decides for itself what an agent is doing.
 *
 * Horizontal spread compresses on narrow/portrait canvases (see
 * `useLayoutScale`) so the same seven characters stay in frame instead of
 * clipping off a wide desktop arc - only positions scale, not the characters
 * themselves, so nothing looks stretched.
 */
export function AgentRoster({ statuses, activity, edges, focusedId, dimAll }: AgentRosterProps) {
  const dimmed = dimAll || !!focusedId;
  const layoutScale = useLayoutScale();

  const roster = useMemo(() => {
    if (layoutScale === 1) return ROSTER;
    const scaled = {} as Record<CharacterId, RosterEntry>;
    for (const id of CHARACTER_IDS) {
      const entry = ROSTER[id];
      scaled[id] = { ...entry, position: [entry.position[0] * layoutScale, entry.position[1], entry.position[2]] };
    }
    return scaled;
  }, [layoutScale]);

  return (
    <group>
      {edges && edges.length > 0 && <ConnectionLines edges={edges} roster={roster} />}
      {CHARACTER_IDS.map((id) => (
        <AgentCharacter
          key={id}
          entry={roster[id]}
          status={statuses[id]}
          activity={activity?.[id]}
          focused={focusedId === id}
          dimmed={dimmed}
        />
      ))}
    </group>
  );
}

export const IDLE_STATUSES: Record<CharacterId, CharacterStatus> = CHARACTER_IDS.reduce(
  (acc, id) => {
    acc[id] = "IDLE";
    return acc;
  },
  {} as Record<CharacterId, CharacterStatus>,
);
