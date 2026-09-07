"use client";

import type { RosterEntry } from "@/lib/agents";

/**
 * The placeholder geometry for one character form. These are deliberately
 * simple stylized primitives - not decoration standing in for "a real 3D
 * character," but a coherent, replaceable visual language: each role reads as
 * a distinct silhouette at a glance, and any of them can be swapped for a real
 * GLTF character later (see `AgentCharacter`'s `modelUrl` prop) without
 * touching how status or layout works.
 */
export function CharacterGeometry({ form }: { form: RosterEntry["form"] }) {
  switch (form) {
    case "core":
      return <icosahedronGeometry args={[0.62, 1]} />;
    case "shard":
      return <octahedronGeometry args={[0.6, 0]} />;
    case "prism":
      return <tetrahedronGeometry args={[0.68, 0]} />;
    case "lattice":
      return <boxGeometry args={[0.78, 0.78, 0.78]} />;
    case "flare":
      return <coneGeometry args={[0.5, 0.9, 5]} />;
    case "ring":
      return <torusGeometry args={[0.5, 0.16, 8, 24]} />;
    case "spark":
      return <dodecahedronGeometry args={[0.34, 0]} />;
  }
}
