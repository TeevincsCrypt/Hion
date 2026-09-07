"use client";

import { Component, type ReactNode } from "react";

interface Props {
  fallback: ReactNode;
  children: ReactNode;
}

interface State {
  failed: boolean;
}

/**
 * Catches a failed asset load (e.g. a GLTF character model that 404s or is
 * malformed) so one agent's visual never takes down the rest of the scene.
 * React error boundaries must be class components; this is the smallest one
 * that does the job.
 */
export class ThreeErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.warn("[hion] 3D asset failed to load, using placeholder character.", error);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
