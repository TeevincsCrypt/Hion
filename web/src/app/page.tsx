"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createMission, getHealth, HionApiError } from "@/lib/api";
import type { CharacterId, CharacterStatus } from "@/lib/agents";
import { AgentRoster, IDLE_STATUSES } from "@/components/3d/AgentRoster";
import { DynamicScene } from "@/components/3d/DynamicScene";
import { StorySections } from "@/components/landing/StorySections";
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

  const focusInput = useCallback(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    // Wait for the scroll to settle before taking focus, so the browser
    // doesn't fight the smooth scroll by jumping to the field.
    window.setTimeout(() => textareaRef.current?.focus(), 420);
  }, []);

  return (
    <main className="relative w-full bg-paper">
      {/* Hero: the command surface. The canvas lives inside this section
          rather than behind the whole document, so scrolling to the story
          below moves it off screen instead of rendering under the text. */}
      <section className="relative h-dvh w-full overflow-hidden">
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
              <label htmlFor="mission-goal" className="sr-only">
                Mission goal
              </label>
              <textarea
                id="mission-goal"
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
              <div className="mt-3 flex flex-col items-center gap-3 sm:mt-5">
                <button
                  type="button"
                  onClick={() => void submit()}
                  disabled={goal.trim().length < 8 || launching}
                  className="group inline-flex items-center gap-2.5 rounded-full bg-ink-900 px-7 py-2.5 text-xs font-semibold uppercase tracking-wide2 text-paper transition hover:bg-ink-600 disabled:cursor-not-allowed disabled:bg-ink-200 disabled:text-ink-500 sm:py-3"
                >
                  {launching ? "Launching…" : "Start Mission"}
                  <span className="transition group-hover:translate-x-0.5">&rarr;</span>
                </button>
                <a
                  href="#how-it-works"
                  className="text-[10px] font-medium uppercase tracking-wide2 text-ink-300 transition hover:text-ink-600"
                >
                  How it works &darr;
                </a>
              </div>
            </div>
            {error && (
              <p role="alert" className="mt-4 text-center text-xs text-risk-high">
                {error}
              </p>
            )}
          </div>
        </div>
      </section>

      <div id="how-it-works">
        <StorySections />
      </div>

      <section className="border-t border-line px-6 py-24 text-center sm:px-10 sm:py-32">
        <h2 className="text-2xl font-semibold tracking-tight text-ink-900 sm:text-[34px]">
          Give Hion a goal.
        </h2>
        <p className="mx-auto mt-4 max-w-md text-[15px] leading-relaxed text-ink-500">
          Describe the outcome you need. The crew handles the rest, and stops to ask when it should.
        </p>
        <button
          type="button"
          onClick={focusInput}
          className="mt-8 inline-flex items-center gap-2.5 rounded-full bg-ink-900 px-7 py-3 text-xs font-semibold uppercase tracking-wide2 text-paper transition hover:bg-ink-600"
        >
          Start a mission
          <span aria-hidden>&uarr;</span>
        </button>
      </section>

      <footer className="border-t border-line px-6 py-8 sm:px-10">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4">
          <StrandsMark />
          <p className="text-[10px] font-medium uppercase tracking-widest2 text-ink-300">
            Hion &middot; Autonomous Work System
          </p>
        </div>
      </footer>
    </main>
  );
}
