"use client";

import { Suspense, useEffect, useMemo, useRef, type RefObject } from "react";
import { useFrame } from "@react-three/fiber";
import { Edges, Float, Html } from "@react-three/drei";
import * as THREE from "three";
import { CharacterGeometry } from "./CharacterForm";
import { GLTFCharacter } from "./GLTFCharacter";
import { ThreeErrorBoundary } from "./ErrorBoundary";
import type { CharacterStatus, RosterEntry } from "@/lib/agents";
import type { ActivityLabel } from "@/lib/deriveAgentState";

export interface AgentCharacterProps {
  entry: RosterEntry;
  status: CharacterStatus;
  /** Real, short observable activity - a present-tense verb plus a task title or event message. Never chain-of-thought. */
  activity?: ActivityLabel | null;
  /** The character the Guardian moment (or a user click) is drawing attention to. */
  focused?: boolean;
  /** True while something else has focus, so the rest of the roster recedes. */
  dimmed?: boolean;
  /** Optional path to a real GLTF/GLB asset. Falls back to the placeholder form if unset or if it fails to load. */
  modelUrl?: string;
}

const STATUS_EMISSIVE: Record<CharacterStatus, number> = {
  IDLE: 0.35,
  WORKING: 1.1,
  REVIEWING: 0.85,
  WAITING: 0.18,
  COMPLETED: 1.4,
  FAILED: 0.9,
};

const STATUS_CORE_OPACITY: Record<CharacterStatus, number> = {
  IDLE: 0.14,
  WORKING: 0.22,
  REVIEWING: 0.2,
  WAITING: 0.08,
  COMPLETED: 0.26,
  FAILED: 0.18,
};

const FAILED_COLOR = new THREE.Color("#f0555a");
const COMPLETED_FLASH_SECONDS = 1.6;
const FAILED_GLITCH_SECONDS = 0.9;

/**
 * One agent, rendered as a reusable, status-driven 3D character.
 *
 * The visual is a swappable placeholder by design: a translucent physical-
 * material core plus a bright wireframe edge overlay in the agent's signal
 * color. `modelUrl` lets a real GLTF character replace it later without
 * changing how status, layout, or the info panel work.
 */
export function AgentCharacter({
  entry,
  status,
  activity,
  focused,
  dimmed,
  modelUrl,
}: AgentCharacterProps) {
  const group = useRef<THREE.Group>(null);
  const coreMaterial = useRef<THREE.MeshPhysicalMaterial>(null);
  const baseColor = useMemo(() => new THREE.Color(entry.hex), [entry.hex]);
  const completedPulse = useRef(0);
  const failGlitch = useRef(0);

  // Arms the one-shot flash refs when a status transition happens. The
  // refs themselves are only ever read/decayed inside useFrame, outside
  // React's render cycle - this effect is just where the transition is
  // detected, since ref writes are not allowed during render.
  useEffect(() => {
    if (status === "COMPLETED") completedPulse.current = COMPLETED_FLASH_SECONDS;
    if (status === "FAILED") failGlitch.current = FAILED_GLITCH_SECONDS;
  }, [status]);

  useFrame((state, delta) => {
    const g = group.current;
    if (!g) return;
    const t = state.clock.elapsedTime;

    const activity = status === "WORKING" || status === "REVIEWING" ? 1 : status === "WAITING" ? 0.25 : 0.55;
    g.rotation.y += delta * 0.15 * activity;

    let bobAmplitude = 0.06;
    let bobSpeed = 0.6;
    if (status === "WORKING") {
      bobAmplitude = 0.1;
      bobSpeed = 1.1;
    } else if (status === "REVIEWING") {
      bobAmplitude = 0.03;
      bobSpeed = 0.4;
    } else if (status === "WAITING") {
      bobAmplitude = 0.02;
      bobSpeed = 0.3;
    }
    const yOffset = Math.sin(t * bobSpeed + entry.position[0]) * bobAmplitude;

    let scale = entry.baseScale;
    if (status === "WORKING") scale *= 1 + Math.sin(t * 2.2) * 0.03;
    if (dimmed && !focused) scale *= 0.94;
    if (focused) scale *= 1.08;
    if (completedPulse.current > 0) {
      completedPulse.current = Math.max(0, completedPulse.current - delta);
      scale *= 1 + (completedPulse.current / COMPLETED_FLASH_SECONDS) * 0.35;
    }

    if (failGlitch.current > 0) {
      failGlitch.current = Math.max(0, failGlitch.current - delta);
      const jitter = (failGlitch.current / FAILED_GLITCH_SECONDS) * 0.04;
      g.position.x = entry.position[0] + (Math.random() - 0.5) * jitter;
      g.position.z = entry.position[2] + (Math.random() - 0.5) * jitter;
    } else {
      g.position.x = entry.position[0];
      g.position.z = entry.position[2];
    }
    g.position.y = entry.position[1] + yOffset;
    g.scale.setScalar(scale);

    const material = coreMaterial.current;
    if (material) {
      const targetEmissive =
        STATUS_EMISSIVE[status] + (completedPulse.current > 0 ? completedPulse.current * 1.2 : 0);
      material.emissiveIntensity = THREE.MathUtils.damp(material.emissiveIntensity, targetEmissive, 4, delta);
      const baseOpacity = STATUS_CORE_OPACITY[status];
      const targetOpacity = dimmed && !focused ? baseOpacity * 0.4 : baseOpacity;
      material.opacity = THREE.MathUtils.damp(material.opacity, targetOpacity, 4, delta);
      const targetColor = status === "FAILED" ? FAILED_COLOR : baseColor;
      material.color.lerp(targetColor, delta * 3);
      material.emissive.lerp(targetColor, delta * 3);
    }
  });

  const edgeColor = status === "FAILED" ? "#f0555a" : entry.hex;

  return (
    <group ref={group} position={entry.position}>
      <Float
        speed={status === "WORKING" ? 2.2 : status === "WAITING" ? 0.6 : 1.2}
        floatIntensity={status === "WAITING" ? 0.15 : 0.5}
        rotationIntensity={status === "REVIEWING" ? 0.1 : 0.35}
      >
        {modelUrl ? (
          <ThreeErrorBoundary
            fallback={<PlaceholderMesh entry={entry} coreMaterial={coreMaterial} edgeColor={edgeColor} />}
          >
            <Suspense
              fallback={<PlaceholderMesh entry={entry} coreMaterial={coreMaterial} edgeColor={edgeColor} />}
            >
              <GLTFCharacter url={modelUrl} scale={entry.baseScale} />
            </Suspense>
          </ThreeErrorBoundary>
        ) : (
          <PlaceholderMesh entry={entry} coreMaterial={coreMaterial} edgeColor={edgeColor} />
        )}
      </Float>

      {activity && !dimmed && (
        <Html center distanceFactor={9} occlude={false} position={[0, entry.baseScale * 1.1 + 0.5, 0]}>
          <div className="pointer-events-none w-60 -translate-x-1/2 select-none text-center">
            <div className="text-[10px] font-semibold text-white/85">{entry.label}</div>
            <div
              className="mt-0.5 text-[10px] font-semibold uppercase tracking-widest2"
              style={{ color: entry.hex }}
            >
              {activity.headline}
            </div>
            {activity.detail && (
              <div className="mt-1 text-[11px] leading-snug text-white/60">&ldquo;{activity.detail}&rdquo;</div>
            )}
          </div>
        </Html>
      )}
    </group>
  );
}

function PlaceholderMesh({
  entry,
  coreMaterial,
  edgeColor,
}: {
  entry: RosterEntry;
  coreMaterial: RefObject<THREE.MeshPhysicalMaterial | null>;
  edgeColor: string;
}) {
  return (
    <mesh>
      <CharacterGeometry form={entry.form} />
      <meshPhysicalMaterial
        ref={coreMaterial}
        color={entry.hex}
        emissive={entry.hex}
        emissiveIntensity={0.4}
        transparent
        opacity={0.16}
        roughness={0.25}
        metalness={0.1}
        clearcoat={0.4}
      />
      <Edges scale={1.001} threshold={15} color={edgeColor} />
    </mesh>
  );
}
