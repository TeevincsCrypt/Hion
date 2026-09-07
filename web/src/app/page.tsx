"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createMission, HionApiError } from "@/lib/api";
import type { CharacterId, CharacterStatus } from "@/lib/agents";
import { AgentRoster, IDLE_STATUSES } from "@/components/3d/AgentRoster";
import { DynamicScene } from "@/components/3d/DynamicScene";

const EXAMPLE_GOAL =
  "Research the top competitors in the AI meeting assistant market and prepare a concise competitive brief.";

export default function HomePage() {
  const router = useRouter();
  const [goal, setGoal] = useState("");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const statuses: Record<CharacterId, CharacterStatus> = launching
    ? { ...IDLE_STATUSES, commander: "WORKING" }
    : IDLE_STATUSES;

  const submit = useCallback(async () => {
    const trimmed = goal.trim();
    if (trimmed.length < 8 || launching) return;
    setError(null);
    setLaunching(true);
    try {
      const mission = await createMission(trimmed);
      // Hold the "commander is now working" beat for a moment before the
      // route change - the environment stays on screen throughout rather
      // than snapping straight to a dashboard.
      await new Promise((resolve) => setTimeout(resolve, 550));
      router.push(`/missions/${mission.id}`);
    } catch (err) {
      setLaunching(false);
      setError(err instanceof HionApiError ? err.message : "Could not reach Hion. Try again.");
    }
  }, [goal, launching, router]);

  return (
    <main className="relative h-dvh w-full overflow-hidden">
      <div className="absolute inset-0">
        <DynamicScene>
          <AgentRoster statuses={statuses} />
        </DynamicScene>
      </div>
      <div className="noise-overlay pointer-events-none absolute inset-0" />
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-700"
        style={{ opacity: launching ? 1 : 0 }}
      >
        <div className="absolute inset-0 bg-void-950/70" />
      </div>

      <header className="pointer-events-none absolute inset-x-0 top-0 flex flex-col items-center pt-10 sm:pt-14">
        <h1 className="animate-fade-in text-2xl font-semibold tracking-widest2 text-white/95 sm:text-3xl">
          HION
        </h1>
        <p className="animate-fade-in mt-3 text-[11px] font-medium tracking-widest2 text-white/40 sm:text-xs">
          AUTONOMOUS WORK SYSTEM
        </p>
      </header>

      <div
        className="absolute inset-x-0 bottom-0 flex flex-col items-center px-4 pb-8 transition-all duration-700 sm:pb-12"
        style={{
          opacity: launching ? 0 : 1,
          transform: launching ? "translateY(12px)" : "translateY(0)",
        }}
      >
        <div className="animate-fade-up w-full max-w-2xl">
          <p className="mb-3 text-center text-sm text-white/50">What do you need Hion to accomplish?</p>
          <div className="panel rounded-2xl p-3 shadow-glow shadow-white/[0.02]">
            <textarea
              ref={textareaRef}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void submit();
                }
              }}
              placeholder={EXAMPLE_GOAL}
              rows={2}
              disabled={launching}
              className="max-h-40 min-h-[4rem] w-full resize-none bg-transparent px-3 py-2 text-base text-white/90 placeholder:text-white/25 focus:outline-none disabled:opacity-60"
            />
            <div className="flex items-center justify-between px-2 pb-1 pt-1">
              <span className="text-[11px] text-white/25">
                {goal.trim().length > 0 ? `${goal.trim().length} characters` : "Enter to launch"}
              </span>
              <button
                type="button"
                onClick={() => void submit()}
                disabled={goal.trim().length < 8 || launching}
                className="group inline-flex items-center gap-2 rounded-full bg-white/95 px-5 py-2 text-xs font-semibold uppercase tracking-widest2 text-void-950 transition hover:bg-white disabled:cursor-not-allowed disabled:bg-white/15 disabled:text-white/40"
              >
                {launching ? "Launching" : "Start Mission"}
                <span className="transition group-hover:translate-x-0.5">→</span>
              </button>
            </div>
          </div>
          {error && <p className="mt-3 text-center text-xs text-danger">{error}</p>}
        </div>
      </div>
    </main>
  );
}
