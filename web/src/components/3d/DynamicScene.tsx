"use client";

import dynamic from "next/dynamic";

/**
 * WebGL has no server-side representation, so the whole scene is loaded only
 * in the browser. Splitting it out of the initial bundle also keeps the first
 * paint of the command screen and Mission Control fast on slower connections.
 */
export const DynamicScene = dynamic(() => import("./Scene").then((m) => m.Scene), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center">
      <div className="h-1.5 w-1.5 animate-pulse-slow rounded-full bg-accent" />
    </div>
  ),
});
