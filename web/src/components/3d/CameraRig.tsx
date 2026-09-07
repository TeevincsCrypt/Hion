"use client";

import { useFrame, useThree } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

const HOME = new THREE.Vector3(0, 2.1, 9);
const LOOK_AT = new THREE.Vector3(0, 0.6, 0);
const PARALLAX = 0.6;
const DRIFT_RADIUS = 0.35;

/**
 * A restrained, autonomous camera: a slow orbital drift plus a small amount of
 * pointer parallax, both heavily damped. There is no drag/orbit control -
 * the point is a living command center, not a 3D editor the user has to steer.
 */
export function CameraRig({ pulledBack }: { pulledBack?: boolean }) {
  const { camera, pointer } = useThree();
  const target = useRef(new THREE.Vector3().copy(LOOK_AT));

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const driftX = Math.sin(t * 0.06) * DRIFT_RADIUS;
    const driftY = Math.cos(t * 0.045) * (DRIFT_RADIUS * 0.4);
    const parallaxX = pointer.x * PARALLAX;
    const parallaxY = pointer.y * PARALLAX * 0.4;

    const distance = pulledBack ? 1.35 : 1;
    const desired = new THREE.Vector3(
      HOME.x + driftX + parallaxX,
      HOME.y + driftY + parallaxY,
      HOME.z * distance,
    );
    camera.position.lerp(desired, 1 - Math.pow(0.001, delta));
    camera.lookAt(target.current);
  });

  return null;
}
