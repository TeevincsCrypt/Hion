"use client";

import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useReducedMotion } from "@/lib/useReducedMotion";

/**
 * A restrained field of drifting motes for atmosphere. Capped low and reused
 * across the whole scene (one draw call) rather than per-character emitters,
 * which is both the cinematic choice (subtle, not snowy) and the cheap one.
 */
export function ParticleField({ count = 260 }: { count?: number }) {
  const reducedMotion = useReducedMotion();
  const points = useRef<THREE.Points>(null);
  const geometry = useRef<THREE.BufferGeometry>(null);

  // Procedural (random) positions are generated once, outside render, and
  // written directly onto the geometry - keeping the component body pure.
  useEffect(() => {
    const array = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      array[i * 3] = (Math.random() - 0.5) * 22;
      array[i * 3 + 1] = Math.random() * 7 - 1;
      array[i * 3 + 2] = (Math.random() - 0.5) * 18;
    }
    geometry.current?.setAttribute("position", new THREE.BufferAttribute(array, 3));
  }, [count]);

  useFrame((state) => {
    if (!points.current) return;
    // Purely atmospheric, so reduced motion parks it: the motes stay in the
    // scene at a fixed opacity instead of drifting and breathing.
    if (reducedMotion) return;
    points.current.rotation.y = state.clock.elapsedTime * 0.008;
    const material = points.current.material as THREE.PointsMaterial;
    material.opacity = 0.16 + Math.sin(state.clock.elapsedTime * 0.4) * 0.05;
  });

  return (
    <points ref={points}>
      <bufferGeometry ref={geometry} />
      <pointsMaterial
        size={0.018}
        color="#A0A0A0"
        transparent
        opacity={0.16}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}
