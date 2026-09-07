"use client";

import { useThree } from "@react-three/fiber";
import * as THREE from "three";

/**
 * How much to compress the roster's horizontal spread so all seven characters
 * stay in frame on a narrow/portrait canvas, without touching the camera or
 * the placeholder geometry itself. 1 = full desktop spread.
 */
export function useLayoutScale(): number {
  const size = useThree((s) => s.size);
  const aspect = size.width / Math.max(size.height, 1);
  // Comfortably wide (desktop-ish) aspects need no compression; a phone in
  // portrait (aspect ~0.45) compresses down to well under half the spread so
  // the outermost characters (Executor, Guardian) stay in frame.
  return THREE.MathUtils.clamp(THREE.MathUtils.mapLinear(aspect, 0.4, 1.3, 0.32, 1), 0.32, 1);
}
