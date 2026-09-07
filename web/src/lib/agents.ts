/**
 * Static visual roster for the Hion crew.
 *
 * This is metadata only - names, roles, colors, base layout. It never carries
 * mission state; see `deriveAgentState.ts` for the pure functions that turn
 * real mission data into what each character should look like right now.
 */
import type { AgentName } from "./types";

/** The backend's six agents, plus a synthetic slot for the tool-execution layer. */
export type CharacterId = AgentName | "executor";

export const CHARACTER_IDS: readonly CharacterId[] = [
  "commander",
  "research",
  "analyst",
  "creator",
  "critic",
  "guardian",
  "executor",
];

export type CharacterStatus =
  | "IDLE"
  | "WORKING"
  | "REVIEWING"
  | "WAITING"
  | "COMPLETED"
  | "FAILED";

export interface RosterEntry {
  id: CharacterId;
  label: string;
  role: string;
  /** Tailwind color token suffix, e.g. "research" -> signal-research. */
  colorToken: CharacterId;
  hex: string;
  /** Base position in the 3D scene, world units. Commander sits centered upstage. */
  position: readonly [number, number, number];
  baseScale: number;
  /** Geometry family used by the placeholder character (see AgentCharacter). */
  form: "core" | "shard" | "prism" | "lattice" | "flare" | "ring" | "spark";
}

// All six specialist/oversight agents sit on the same forward plane (z=1.8,
// y=0) so perspective can't make a "behind" character's silhouette land on
// top of a "front" one - only the Commander breaks that plane, alone,
// upstage-center, which is what makes it read as central. Executor keeps the
// same z but sits slightly lower and smaller, reading as the layer beneath
// the agents rather than a peer competing for the same visual weight.
export const ROSTER: Record<CharacterId, RosterEntry> = {
  commander: {
    id: "commander",
    label: "Commander",
    role: "Mission planning & synthesis",
    colorToken: "commander",
    hex: "#f2e6c9",
    position: [0, 0.95, -1.7],
    baseScale: 1.25,
    form: "core",
  },
  executor: {
    id: "executor",
    label: "Executor",
    role: "Tool execution layer",
    colorToken: "executor",
    hex: "#93a0b8",
    position: [-3.6, -0.35, 1.9],
    baseScale: 0.7,
    form: "spark",
  },
  research: {
    id: "research",
    label: "Researcher",
    role: "Web research & evidence gathering",
    colorToken: "research",
    hex: "#5eead4",
    position: [-2.15, 0, 1.85],
    baseScale: 1,
    form: "shard",
  },
  analyst: {
    id: "analyst",
    label: "Analyst",
    role: "Comparison, risk, recommendation",
    colorToken: "analyst",
    hex: "#a78bfa",
    position: [-0.72, 0, 1.8],
    baseScale: 1,
    form: "prism",
  },
  creator: {
    id: "creator",
    label: "Creator",
    role: "Drafting the deliverable",
    colorToken: "creator",
    hex: "#34d399",
    position: [0.72, 0, 1.8],
    baseScale: 1,
    form: "lattice",
  },
  critic: {
    id: "critic",
    label: "Critic",
    role: "Quality review & critique",
    colorToken: "critic",
    hex: "#fbbf24",
    position: [2.15, 0, 1.85],
    baseScale: 0.95,
    form: "flare",
  },
  guardian: {
    id: "guardian",
    label: "Guardian",
    role: "Risk assessment & human approval",
    colorToken: "guardian",
    hex: "#fb7185",
    position: [3.6, 0, 1.9],
    baseScale: 0.95,
    form: "ring",
  },
};

export const SPECIALIST_IDS: readonly AgentName[] = [
  "research",
  "analyst",
  "creator",
];

export function rosterEntry(id: CharacterId): RosterEntry {
  return ROSTER[id];
}
