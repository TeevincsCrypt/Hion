"use client";

import { useEffect, useRef } from "react";
import { useMissionStore } from "@/store/missionStore";

const SPEEDS = [1, 2, 4, 8];

/**
 * Steps through the mission's own stored event log on a timer. This never
 * touches the backend - no agent is re-invoked, no mission is re-run. It is
 * purely a client-side replay of history already recorded.
 */
export function ReplayControls({ onExit }: { onExit: () => void }) {
  const fullEventLog = useMissionStore((s) => s.fullEventLog);
  const replayIndex = useMissionStore((s) => s.replayIndex);
  const replayPlaying = useMissionStore((s) => s.replayPlaying);
  const replaySpeed = useMissionStore((s) => s.replaySpeed);
  const setReplayIndex = useMissionStore((s) => s.setReplayIndex);
  const setReplayPlaying = useMissionStore((s) => s.setReplayPlaying);
  const setReplaySpeed = useMissionStore((s) => s.setReplaySpeed);

  const total = fullEventLog.length;
  const indexRef = useRef(replayIndex);

  useEffect(() => {
    indexRef.current = replayIndex;
  }, [replayIndex]);

  useEffect(() => {
    if (!replayPlaying) return;
    if (indexRef.current >= total) {
      setReplayPlaying(false);
      return;
    }
    const stepMs = Math.max(45, 260 / replaySpeed);
    const id = setInterval(() => {
      const next = indexRef.current + 1;
      setReplayIndex(next);
      if (next >= total) setReplayPlaying(false);
    }, stepMs);
    return () => clearInterval(id);
  }, [replayPlaying, replaySpeed, total, setReplayIndex, setReplayPlaying]);

  const restart = () => {
    setReplayIndex(0);
    setReplayPlaying(true);
  };

  return (
    <div className="panel animate-fade-in flex items-center gap-3 rounded-2xl px-4 py-3">
      <span className="text-[10px] font-semibold uppercase tracking-widest2 text-white/40">Replay</span>

      <button
        type="button"
        onClick={restart}
        aria-label="Restart"
        className="rounded-full border border-white/15 px-3 py-1.5 text-[11px] text-white/70 transition hover:border-white/30 hover:text-white"
      >
        ⟲
      </button>
      <button
        type="button"
        onClick={() => setReplayPlaying(!replayPlaying)}
        aria-label={replayPlaying ? "Pause" : "Play"}
        className="rounded-full bg-white/90 px-4 py-1.5 text-[11px] font-semibold text-void-950 transition hover:bg-white"
      >
        {replayPlaying ? "Pause" : "Play"}
      </button>

      <input
        type="range"
        min={0}
        max={total}
        value={replayIndex}
        onChange={(e) => setReplayIndex(Number(e.target.value))}
        className="mx-1 h-1 flex-1 cursor-pointer accent-white/80"
      />
      <span className="w-14 shrink-0 text-right font-mono text-[11px] text-white/40">
        {replayIndex}/{total}
      </span>

      <div className="flex items-center gap-1 border-l border-white/10 pl-3">
        {SPEEDS.map((speed) => (
          <button
            key={speed}
            type="button"
            onClick={() => setReplaySpeed(speed)}
            className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium transition ${
              replaySpeed === speed ? "bg-white/15 text-white" : "text-white/35 hover:text-white/60"
            }`}
          >
            {speed}×
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={onExit}
        className="ml-1 shrink-0 rounded-full border border-white/15 px-3 py-1.5 text-[11px] text-white/60 transition hover:border-white/30 hover:text-white"
      >
        Exit replay
      </button>
    </div>
  );
}
