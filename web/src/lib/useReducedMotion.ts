"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

let mediaQuery: MediaQueryList | null = null;

/** Lazily created so this module stays importable during server rendering. */
function query(): MediaQueryList {
  mediaQuery ??= window.matchMedia(QUERY);
  return mediaQuery;
}

function subscribe(onChange: () => void): () => void {
  const q = query();
  q.addEventListener("change", onChange);
  return () => q.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  return query().matches;
}

/** The server has no media queries; assume full motion and let the client correct it. */
function getServerSnapshot(): boolean {
  return false;
}

/**
 * Whether the viewer has asked their system for reduced motion.
 *
 * `globals.css` already damps CSS transitions and keyframes, but the 3D layer
 * animates inside `useFrame`, which no stylesheet can reach. Components read
 * this to drop *ambient* motion - camera drift, idle rotation, floating bob,
 * particle drift - while keeping everything that carries meaning: status
 * colour, scale, the agent's presence in the scene. The interface is
 * simplified, never broken or emptied.
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
