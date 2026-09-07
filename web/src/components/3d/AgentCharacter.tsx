"use client";

import { Suspense, useEffect, useRef, useState, type RefObject } from "react";
import { useFrame } from "@react-three/fiber";
import { Edges, Float, Html } from "@react-three/drei";
import * as THREE from "three";
import { CharacterGeometry } from "./CharacterForm";
import { GLTFCharacter } from "./GLTFCharacter";
import { ThreeErrorBoundary } from "./ErrorBoundary";
import type { CharacterId, CharacterStatus, RosterEntry } from "@/lib/agents";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { ActivityLabel } from "@/lib/deriveAgentState";

export interface AgentCharacterProps {
  entry: RosterEntry;
  status: CharacterStatus;
  /** Real, short observable activity - a present-tense phrase, never chain-of-thought. */
  activity?: ActivityLabel | null;
  /** The character the Guardian moment (or a user click) is drawing attention to. */
  focused?: boolean;
  /** True while something else has focus, so the rest of the roster recedes. */
  dimmed?: boolean;
  /** Optional path to a real GLTF/GLB asset. Falls back to the placeholder form if unset or if it fails to load. */
  modelUrl?: string;
  onSelect?: (id: CharacterId) => void;
}

// Monochrome + one accent: color is never a per-agent brand, only a signal.
// Idle/waiting characters read as quiet architectural forms; the accent marks
// whichever one is currently active or requires attention; risk red is used
// nowhere else. Identity comes from geometric form and label, not hue.
const IDLE_COLOR = new THREE.Color("#A0A0A0");
const ACCENT_COLOR = new THREE.Color("#B8814A");
const SETTLED_COLOR = new THREE.Color("#111111");
const FAILED_COLOR = new THREE.Color("#B23B3B");
const CORE_TINT = "#EAE7E1";

const STATUS_COLOR: Record<CharacterStatus, THREE.Color> = {
  IDLE: IDLE_COLOR,
  WORKING: ACCENT_COLOR,
  REVIEWING: ACCENT_COLOR,
  WAITING: IDLE_COLOR,
  COMPLETED: SETTLED_COLOR,
  FAILED: FAILED_COLOR,
};

const STATUS_EMISSIVE: Record<CharacterStatus, number> = {
  IDLE: 0.12,
  WORKING: 0.55,
  REVIEWING: 0.42,
  WAITING: 0.06,
  COMPLETED: 0.16,
  FAILED: 0.4,
};

const STATUS_CORE_OPACITY: Record<CharacterStatus, number> = {
  IDLE: 0.5,
  WORKING: 0.68,
  REVIEWING: 0.62,
  WAITING: 0.32,
  COMPLETED: 0.6,
  FAILED: 0.55,
};

const COMPLETED_FLASH_SECONDS = 1.4;
const FAILED_GLITCH_SECONDS = 0.9;

/**
 * One agent, rendered as a reusable, status-driven 3D character.
 *
 * The visual is a swappable placeholder by design: a pale, translucent
 * physical-material core plus a wireframe edge overlay - like a machined
 * study model, not a neon hologram. `modelUrl` lets a real GLTF character
 * replace it later without changing how status, layout, or the inspector
 * hook-in work.
 */
export function AgentCharacter({
  entry,
  status,
  activity,
  focused,
  dimmed,
  modelUrl,
  onSelect,
}: AgentCharacterProps) {
  const group = useRef<THREE.Group>(null);
  const coreMaterial = useRef<THREE.MeshPhysicalMaterial>(null);
  const completedPulse = useRef(0);
  const failGlitch = useRef(0);
  const [hovered, setHovered] = useState(false);
  const reducedMotion = useReducedMotion();

  // Arms the one-shot flash refs when a status transition happens. The
  // refs themselves are only ever read/decayed inside useFrame, outside
  // React's render cycle - this effect is just where the transition is
  // detected, since ref writes are not allowed during render.
  useEffect(() => {
    if (status === "COMPLETED") completedPulse.current = COMPLETED_FLASH_SECONDS;
    if (status === "FAILED") failGlitch.current = FAILED_GLITCH_SECONDS;
  }, [status]);

  useEffect(() => {
    if (!onSelect) return;
    document.body.style.cursor = hovered ? "pointer" : "auto";
    return () => {
      document.body.style.cursor = "auto";
    };
  }, [hovered, onSelect]);

  useFrame((state, delta) => {
    const g = group.current;
    if (!g) return;
    const t = state.clock.elapsedTime;

    const activityLevel = status === "WORKING" || status === "REVIEWING" ? 1 : status === "WAITING" ? 0.2 : 0.4;
    // Under reduced motion the crew holds still: rotation, bob, breathing and
    // the failure jitter all stop. Status still reads clearly, because status
    // is carried by colour, emissive intensity and opacity - handled below and
    // deliberately left running.
    if (!reducedMotion) g.rotation.y += delta * 0.12 * activityLevel;

    let bobAmplitude = 0.05;
    let bobSpeed = 0.55;
    if (status === "WORKING") {
      bobAmplitude = 0.09;
      bobSpeed = 1.05;
    } else if (status === "REVIEWING") {
      bobAmplitude = 0.025;
      bobSpeed = 0.4;
    } else if (status === "WAITING") {
      bobAmplitude = 0.015;
      bobSpeed = 0.3;
    }
    const yOffset = reducedMotion ? 0 : Math.sin(t * bobSpeed + entry.position[0]) * bobAmplitude;

    let scale = entry.baseScale;
    if (status === "WORKING" && !reducedMotion) scale *= 1 + Math.sin(t * 2.2) * 0.025;
    if (dimmed && !focused) scale *= 0.94;
    if (focused || hovered) scale *= 1.07;
    if (completedPulse.current > 0) {
      completedPulse.current = Math.max(0, completedPulse.current - delta);
      // The pulse still decays (the emissive flash below reads from it), but
      // it stops throwing the geometry around.
      if (!reducedMotion) scale *= 1 + (completedPulse.current / COMPLETED_FLASH_SECONDS) * 0.3;
    }

    if (failGlitch.current > 0 && !reducedMotion) {
      failGlitch.current = Math.max(0, failGlitch.current - delta);
      const jitter = (failGlitch.current / FAILED_GLITCH_SECONDS) * 0.035;
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
      const inCompletionFlash = status === "COMPLETED" && completedPulse.current > 0;
      const targetEmissive =
        STATUS_EMISSIVE[status] + (inCompletionFlash ? completedPulse.current * 0.9 : 0) + (hovered ? 0.15 : 0);
      material.emissiveIntensity = THREE.MathUtils.damp(material.emissiveIntensity, targetEmissive, 4, delta);
      const baseOpacity = STATUS_CORE_OPACITY[status];
      const targetOpacity = dimmed && !focused ? baseOpacity * 0.45 : baseOpacity;
      material.opacity = THREE.MathUtils.damp(material.opacity, targetOpacity, 4, delta);
      const targetColor = inCompletionFlash ? ACCENT_COLOR : STATUS_COLOR[status];
      material.emissive.lerp(targetColor, delta * 3);
    }
  });

  const edgeColor = `#${STATUS_COLOR[status].getHexString()}`;

  return (
    <group
      ref={group}
      position={entry.position}
      onClick={
        onSelect
          ? (event) => {
              event.stopPropagation();
              onSelect(entry.id);
            }
          : undefined
      }
      onPointerOver={onSelect ? () => setHovered(true) : undefined}
      onPointerOut={onSelect ? () => setHovered(false) : undefined}
    >
      <Float
        speed={reducedMotion ? 0 : status === "WORKING" ? 2.1 : status === "WAITING" ? 0.55 : 1.1}
        floatIntensity={reducedMotion ? 0 : status === "WAITING" ? 0.12 : 0.45}
        rotationIntensity={reducedMotion ? 0 : status === "REVIEWING" ? 0.08 : 0.3}
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
        {/* Larger, invisible hit target - the wireframe forms are too thin to click reliably. */}
        {onSelect && (
          <mesh visible={false}>
            <sphereGeometry args={[entry.baseScale * 0.95, 8, 8]} />
            <meshBasicMaterial />
          </mesh>
        )}
      </Float>

      {/* zIndexRange keeps the floating label above the canvas but *below* the
          mission panels (z-10). drei defaults to ~16.7M, which puts labels on
          top of the Task Plan and Mission Log rails and makes both unreadable
          wherever an agent sits behind one. */}
      {activity && !dimmed && (
        <Html
          center
          distanceFactor={9}
          occlude={false}
          zIndexRange={[5, 0]}
          position={[0, entry.baseScale * 1.1 + 0.5, 0]}
        >
          <div className="pointer-events-none w-52 -translate-x-1/2 select-none text-center">
            <div className="text-[10px] font-semibold uppercase tracking-wide2 text-ink-900">{entry.label}</div>
            <div className="mt-0.5 text-[11px] leading-snug text-ink-500">{activity.headline}</div>
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
        color={CORE_TINT}
        emissive={IDLE_COLOR}
        emissiveIntensity={0.12}
        transparent
        opacity={0.5}
        roughness={0.35}
        metalness={0.05}
        clearcoat={0.6}
        clearcoatRoughness={0.25}
      />
      <Edges scale={1.001} threshold={15} color={edgeColor} />
    </mesh>
  );
}
