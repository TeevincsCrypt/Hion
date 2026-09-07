"use client";

import { useGLTF } from "@react-three/drei";

/**
 * Loads a real character asset. Kept isolated in its own component so
 * `AgentCharacter` can wrap only this in Suspense + an error boundary - a
 * missing or malformed GLTF never reaches the placeholder geometry path.
 */
export function GLTFCharacter({ url, scale }: { url: string; scale: number }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} scale={scale} />;
}
