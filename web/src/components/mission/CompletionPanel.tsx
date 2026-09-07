"use client";

import { useEffect, useState } from "react";
import { getMissionMetrics } from "@/lib/api";
import type { Mission, MissionMetrics } from "@/lib/types";
import { formatDuration } from "@/lib/useElapsed";
import { MissionMetricsPanel } from "./MissionMetricsPanel";

interface CompletionPanelProps {
  mission: Mission;
  mode: "live" | "replay";
  /** Distinct agents that actually ran, from the real event log - see the mission page. */
  agentsInvolved: number;
  onReplay: () => void;
}

/**
 * The mission's outcome, using only what the backend actually reported:
 * `mission.final_result` and the metrics carried on the mission.completed /
 * mission.failed event (the same values `GET /api/missions/{id}/metrics`
 * returns). Nothing here is estimated.
 */
export function CompletionPanel({ mission, mode, agentsInvolved, onReplay }: CompletionPanelProps) {
  const failed = mission.status === "FAILED";
  const [showAll, setShowAll] = useState(false);
  // `mission.metrics` arrives on the terminal event and is cast from an
  // untyped payload; GET /api/missions/{id}/metrics is the typed, authoritative
  // source, so prefer it and fall back to the event copy if the call fails.
  const [fetched, setFetched] = useState<MissionMetrics | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMissionMetrics(mission.id)
      .then((m) => !cancelled && setFetched(m))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [mission.id]);

  const metrics = fetched ?? mission.metrics;

  return (
    <div className="animate-fade-up surface-panel w-full max-w-xl rounded-lg p-8">
      <p className="text-center text-xl font-semibold text-ink-900">
        {failed ? "Mission Failed" : "Mission Complete"}
      </p>

      {metrics && (
        <div className="mt-6 flex flex-wrap items-baseline justify-center gap-x-6 gap-y-2 border-y border-line py-4">
          <Stat value={metrics.total_tasks} label="task" />
          <Stat value={agentsInvolved} label="agent" />
          <Stat value={metrics.retries} label="retry" plural="retries" />
          <Stat value={metrics.approvals_requested} label="approval" />
          <p className="text-[15px] text-ink-900">
            <span className="font-semibold">{formatDuration(Math.round(metrics.duration_seconds))}</span>{" "}
            <span className="text-ink-500">elapsed</span>
          </p>
        </div>
      )}

      {metrics && (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => setShowAll((s) => !s)}
            aria-expanded={showAll}
            className="mx-auto block text-[10px] font-medium uppercase tracking-wide2 text-ink-300 transition hover:text-ink-600"
          >
            {showAll ? "Hide full metrics" : "Full metrics"}
          </button>
          {showAll && (
            <div className="animate-fade-in mt-4 border-b border-line pb-5">
              <MissionMetricsPanel metrics={metrics} />
            </div>
          )}
        </div>
      )}

      {mission.final_result && (
        <div className="mt-6 max-h-64 overflow-y-auto rounded-md bg-paper-dim px-4 py-3.5">
          <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink-600">{mission.final_result}</p>
        </div>
      )}
      {failed && mission.error && (
        <p className="mt-5 rounded-md border border-risk-high/25 bg-risk-highSoft/40 px-4 py-3 text-[13px] leading-relaxed text-risk-high">
          {mission.error}
        </p>
      )}

      {mode === "live" && (
        <div className="mt-7 flex justify-center">
          <button
            type="button"
            onClick={onReplay}
            className="rounded-full border border-ink-900/15 px-5 py-2 text-xs font-semibold uppercase tracking-wide2 text-ink-900 transition hover:border-ink-900/35"
          >
            Replay Mission
          </button>
        </div>
      )}
    </div>
  );
}

function Stat({ value, label, plural }: { value: number; label: string; plural?: string }) {
  const word = value === 1 ? label : (plural ?? `${label}s`);
  return (
    <p className="text-[15px] text-ink-900">
      <span className="font-semibold">{value}</span> <span className="text-ink-500">{word}</span>
    </p>
  );
}
