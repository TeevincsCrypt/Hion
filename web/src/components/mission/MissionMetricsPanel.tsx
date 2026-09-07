"use client";

import type { MissionMetrics } from "@/lib/types";
import { formatDuration } from "@/lib/useElapsed";

/**
 * The mission's real `MissionMetrics`, as returned by
 * `GET /api/missions/{id}/metrics` (and carried on the terminal event).
 * Presented as typography rather than charts - a chart of "1 approval" tells
 * a reader less than the number does.
 *
 * Rows are omitted when the backend reports zero for an optional counter, so
 * the panel stays honest about what actually happened during this mission
 * instead of padding itself out with empty statistics.
 */
export function MissionMetricsPanel({ metrics }: { metrics: MissionMetrics }) {
  const groups: { label: string; stats: [string, string][] }[] = [
    {
      label: "Work",
      stats: [
        ["Tasks", String(metrics.total_tasks)],
        ["Completed", String(metrics.completed_tasks)],
        ...ifPositive("Failed", metrics.failed_tasks),
        ...ifPositive("Retries", metrics.retries),
      ],
    },
    {
      label: "Execution",
      stats: [
        ["Agent invocations", String(metrics.agent_invocations)],
        ["Tool calls", String(metrics.tool_calls)],
        ...ifPositive("Tool calls blocked", metrics.tool_calls_blocked),
        ...ifPositive("Revisions requested", metrics.revisions_requested),
      ],
    },
    {
      label: "Oversight",
      stats: [
        ...ifPositive("Approvals requested", metrics.approvals_requested),
        ...ifPositive("Granted", metrics.approvals_granted),
        ...ifPositive("Rejected", metrics.approvals_rejected),
        ...ifPositive("Timed out", metrics.approvals_timed_out),
        ...(metrics.average_critic_score !== null
          ? ([["Average critic score", `${Math.round(metrics.average_critic_score)}/100`]] as [
              string,
              string,
            ][])
          : []),
      ],
    },
    {
      label: "Cost",
      stats: [
        ["Duration", formatDuration(Math.round(metrics.duration_seconds))],
        ...ifPositive("Input tokens", metrics.input_tokens, formatCount),
        ...ifPositive("Output tokens", metrics.output_tokens, formatCount),
      ],
    },
  ];

  return (
    <dl className="grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
      {groups
        .filter((g) => g.stats.length > 0)
        .map((group) => (
          <div key={group.label}>
            <p className="mb-2 text-[10px] font-medium uppercase tracking-widest2 text-ink-300">
              {group.label}
            </p>
            <div className="space-y-1.5">
              {group.stats.map(([label, value]) => (
                <div key={label} className="flex items-baseline justify-between gap-3">
                  <dt className="text-[11px] text-ink-500">{label}</dt>
                  <dd className="font-mono text-[12px] tabular-nums text-ink-900">{value}</dd>
                </div>
              ))}
            </div>
          </div>
        ))}
    </dl>
  );
}

function ifPositive(
  label: string,
  value: number,
  format: (n: number) => string = String,
): [string, string][] {
  return value > 0 ? [[label, format(value)]] : [];
}

function formatCount(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}
