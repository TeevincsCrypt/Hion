"use client";

import { Canvas } from "@react-three/fiber";
import { ContactShadows, PerformanceMonitor } from "@react-three/drei";
import { Suspense, useState, type ReactNode } from "react";
import * as THREE from "three";
import { CameraRig } from "./CameraRig";
import { ParticleField } from "./ParticleField";

interface SceneProps {
  children: ReactNode;
  pulledBack?: boolean;
  dimmed?: boolean;
}

const PAPER = "#F7F7F5";

/**
 * The one Canvas in the app: shared lighting, ground shadow and camera rig,
 * staged like a lit architectural maquette rather than a dark terminal - a
 * bright, airy volume the crew floats in, with a degraded-performance
 * step-down and a capped device pixel ratio so the UI stays responsive while
 * agents are actually running.
 */
export function Scene({ children, pulledBack, dimmed }: SceneProps) {
  const [dpr, setDpr] = useState<[number, number]>([1, 1.75]);

  return (
    <Canvas
      dpr={dpr}
      gl={{ antialias: true, powerPreference: "high-performance", toneMapping: THREE.ACESFilmicToneMapping }}
      camera={{ fov: 38, near: 0.1, far: 40, position: [0, 2.1, 9] }}
    >
      <PerformanceMonitor onDecline={() => setDpr([1, 1])} onIncline={() => setDpr([1, 1.75])} />
      <color attach="background" args={[PAPER]} />
      <fog attach="fog" args={[PAPER, 9, 25]} />

      {/* Soft studio lighting: a warm key light casts the only real shadow
          (via ContactShadows below), a cool-neutral hemisphere and a low
          ambient fill keep everything else legible without flattening it. */}
      <hemisphereLight args={["#ffffff", "#dedbd3", 0.85]} />
      <directionalLight position={[4.5, 7, 3]} intensity={0.9} color="#fff8ee" />
      <ambientLight intensity={dimmed ? 0.25 : 0.4} />

      <CameraRig pulledBack={pulledBack} />
      <ParticleField count={dimmed ? 90 : 160} />
      <ContactShadows
        position={[0, -1.05, 0]}
        opacity={dimmed ? 0.08 : 0.14}
        scale={16}
        blur={3.2}
        far={3.5}
        color="#111111"
        frames={1}
      />

      <Suspense fallback={null}>{children}</Suspense>
    </Canvas>
  );
}
