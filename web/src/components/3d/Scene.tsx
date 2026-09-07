"use client";

import { Canvas } from "@react-three/fiber";
import { PerformanceMonitor } from "@react-three/drei";
import { Suspense, useState, type ReactNode } from "react";
import * as THREE from "three";
import { CameraRig } from "./CameraRig";
import { ParticleField } from "./ParticleField";

interface SceneProps {
  children: ReactNode;
  pulledBack?: boolean;
  dimmed?: boolean;
}

/**
 * The one Canvas in the app: shared lighting, fog and camera rig, with a
 * degraded-performance step-down and a capped device pixel ratio so the UI
 * stays responsive while agents are actually running.
 */
export function Scene({ children, pulledBack, dimmed }: SceneProps) {
  const [dpr, setDpr] = useState<[number, number]>([1, 1.75]);

  return (
    <Canvas
      dpr={dpr}
      gl={{ antialias: true, powerPreference: "high-performance", toneMapping: THREE.ACESFilmicToneMapping }}
      camera={{ fov: 42, near: 0.1, far: 40, position: [0, 2.1, 9] }}
    >
      <PerformanceMonitor onDecline={() => setDpr([1, 1])} onIncline={() => setDpr([1, 1.75])} />
      <color attach="background" args={["#050609"]} />
      <fog attach="fog" args={["#050609", 8, 24]} />

      <hemisphereLight args={["#3a4560", "#050609", 0.55]} />
      <directionalLight position={[4, 6, 4]} intensity={0.5} color="#dfe6ff" />
      <ambientLight intensity={dimmed ? 0.08 : 0.16} />

      <CameraRig pulledBack={pulledBack} />
      <ParticleField count={dimmed ? 140 : 260} />

      <Suspense fallback={null}>{children}</Suspense>
    </Canvas>
  );
}
