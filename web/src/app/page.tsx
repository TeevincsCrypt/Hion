"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createMission, getHealth, HionApiError } from "@/lib/api";
import type { CharacterId, CharacterStatus } from "@/lib/agents";
import { AgentRoster, IDLE_STATUSES } from "@/components/3d/AgentRoster";
import { DynamicScene } from "@/components/3d/DynamicScene";
import { StrandsMark } from "@/components/mission/StrandsMark";
import { SystemStatus } from "@/components/mission/SystemStatus";

const EXAMPLE_GOAL =
  "Research the AI meeting assistant market and prepare a competitive brief.";

export default function HomePage() {
  const router = useRouter();
  const [goal, setGoal] = useState("");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [systemReady, setSystemReady] = useState<boolean | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then(() => !cancelled && setSystemReady(true))
      .catch(() => !cancelled && setSystemReady(false));
    return () => {
      cancelled = true;
    };
  }, []);

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
    <main className="relative h-dvh w-full overflow-hidden bg-paper">
      <div className="absolute inset-0">
        <DynamicScene>
          <AgentRoster statuses={statuses} />
        </DynamicScene>
      </div>

      <header className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between p-6 sm:p-10">
        <div className="animate-fade-in">
          <h1 className="text-[22px] font-semibold leading-none tracking-tight text-ink-900 sm:text-2xl">
            Hion
          </h1>
          <p className="mt-2 text-[10px] font-medium uppercase tracking-widest2 text-ink-500">
            Autonomous Work System
          </p>
        </div>
        <div className="pointer-events-auto animate-fade-in">
          <SystemStatus ready={systemReady} />
        </div>
      </header>

      <div className="pointer-events-none absolute bottom-6 left-6 z-10 hidden sm:block">
        <StrandsMark />
      </div>

      <div
        className="absolute inset-x-0 bottom-0 flex flex-col items-center px-5 pb-6 transition-all duration-700 sm:pb-16"
        style={{
          opacity: launching ? 0 : 1,
          transform: launching ? "translateY(14px)" : "translateY(0)",
        }}
      >
        <div className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-t from-paper via-paper/85 to-transparent sm:h-56" />

        <div className="animate-fade-up w-full max-w-2xl">
          <p className="mb-2 text-center text-[13px] text-ink-500 sm:mb-4 sm:text-[15px]">
            What do you need Hion to accomplish?
          </p>
          <div className="pointer-events-auto">
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
              className="w-full resize-none border-0 border-b border-line bg-transparent px-1 pb-2 text-center font-display text-base leading-snug text-ink-900 placeholder:text-ink-300 focus:border-ink-900 focus:outline-none disabled:opacity-50 sm:pb-3 sm:text-2xl"
            />
            <div className="mt-3 flex items-center justify-center sm:mt-5">
              <button
                type="button"
                onClick={() => void submit()}
                disabled={goal.trim().length < 8 || launching}
                className="group inline-flex items-center gap-2.5 rounded-full bg-ink-900 px-7 py-2.5 text-xs font-semibold uppercase tracking-wide2 text-paper transition hover:bg-ink-600 disabled:cursor-not-allowed disabled:bg-ink-200 disabled:text-ink-500 sm:py-3"
              >
                {launching ? "Launching…" : "Start Mission"}
                <span className="transition group-hover:translate-x-0.5">&rarr;</span>
              </button>
            </div>
          </div>
          {error && <p className="mt-4 text-center text-xs text-risk-high">{error}</p>}
        </div>
      </div>
    </main>
  );
}
