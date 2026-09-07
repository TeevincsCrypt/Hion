"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import { ROSTER, type CharacterId, type RosterEntry } from "@/lib/agents";
import type { ConnectionEdge } from "@/lib/deriveAgentState";

interface ConnectionLinesProps {
  edges: ConnectionEdge[];
  /** The (possibly layout-scaled) roster positions to connect - see `useLayoutScale`. */
  roster?: Record<CharacterId, RosterEntry>;
}

/**
 * Visual connections between agents, derived entirely from the mission's own
 * task graph and current activity (see `deriveAgentState.computeConnections`).
 * Structural edges are the plan's dependencies; active edges are a brief,
 * moving pulse showing which task is in flight right now.
 */
export function ConnectionLines({ edges, roster = ROSTER }: ConnectionLinesProps) {
  const structural = edges.filter((e) => e.kind === "structural");
  const active = edges.filter((e) => e.kind === "active");

  return (
    <group>
      {structural.map((edge) => (
        <StructuralEdge key={`${edge.from}-${edge.to}`} edge={edge} roster={roster} />
      ))}
      {active.map((edge) => (
        <ActiveEdge key={`${edge.from}-${edge.to}-${edge.taskId ?? ""}`} edge={edge} roster={roster} />
      ))}
    </group>
  );
}

function curveFor(edge: ConnectionEdge, roster: Record<CharacterId, RosterEntry>): THREE.CatmullRomCurve3 {
  const from = new THREE.Vector3(...roster[edge.from].position);
  const to = new THREE.Vector3(...roster[edge.to].position);
  const mid = from.clone().lerp(to, 0.5);
  mid.y += 0.9;
  return new THREE.CatmullRomCurve3([from, mid, to]);
}

function StructuralEdge({ edge, roster }: { edge: ConnectionEdge; roster: Record<CharacterId, RosterEntry> }) {
  const points = useMemo(() => curveFor(edge, roster).getPoints(24), [edge, roster]);
  return <Line points={points} color="#3a4051" lineWidth={1} transparent opacity={0.35} />;
}

const PULSE_COLOR = "#e7e9ee";

function ActiveEdge({ edge, roster }: { edge: ConnectionEdge; roster: Record<CharacterId, RosterEntry> }) {
  const curve = useMemo(() => curveFor(edge, roster), [edge, roster]);
  const points = useMemo(() => curve.getPoints(32), [curve]);
  const pulseRef = useRef<THREE.Mesh>(null);
  const glowColor = roster[edge.to].hex;

  useFrame((state) => {
    const mesh = pulseRef.current;
    if (!mesh) return;
    const progress = (state.clock.elapsedTime * 0.5) % 1;
    const point = curve.getPointAt(progress);
    mesh.position.copy(point);
  });

  return (
    <group>
      <Line points={points} color={glowColor} lineWidth={1.5} transparent opacity={0.55} />
      <mesh ref={pulseRef}>
        <sphereGeometry args={[0.045, 8, 8]} />
        <meshBasicMaterial color={PULSE_COLOR} />
      </mesh>
    </group>
  );
}
