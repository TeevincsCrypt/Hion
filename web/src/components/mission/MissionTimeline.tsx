"use client";

import { useEffect, useRef, useState } from "react";
import { ROSTER } from "@/lib/agents";
import type { AgentName, EventType, MissionEvent } from "@/lib/types";

const EVENT_LABELS: Record<EventType, string> = {
  "mission.created": "Mission started",
  "mission.planned": "Plan created",
  "plan.warning": "Plan warning",
  "mission.completed": "Mission completed",
  "mission.failed": "Mission failed",
  "task.created": "Task created",
  "task.started": "Task started",
  "task.completed": "Task completed",
  "task.failed": "Task failed",
  "task.retrying": "Task retrying",
  "agent.started": "Agent started",
  "agent.completed": "Agent completed",
  "agent.failed": "Agent failed",
  "tool.started": "Tool call started",
  "tool.completed": "Tool call completed",
  "tool.blocked": "Tool call blocked",
  "critic.started": "Critic reviewing",
  "critic.completed": "Critic completed",
  "revision.requested": "Revision requested",
  "revision.exhausted": "Revisions exhausted",
  "guardian.review": "Guardian review",
  "approval.required": "Approval required",
  "approval.granted": "Approval granted",
  "approval.rejected": "Approval rejected",
  "approval.timed_out": "Approval timed out",
  "stream.heartbeat": "Heartbeat",
};

/** Event types significant enough to appear on the record. Everything else is
 * still counted in the header, keeping the log itself uncluttered. */
const NOTABLE: ReadonlySet<EventType> = new Set([
  "mission.created",
  "mission.planned",
  "mission.completed",
  "mission.failed",
  "task.started",
  "task.completed",
  "task.failed",
  "critic.started",
  "critic.completed",
  "revision.requested",
  "revision.exhausted",
  "guardian.review",
  "approval.required",
  "approval.granted",
  "approval.rejected",
  "approval.timed_out",
]);

function agentLabel(agent: AgentName | null): string | null {
  return agent ? ROSTER[agent].label : null;
}

function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour12: false });
}

/**
 * An elegant record of the mission, read top-to-bottom like a system log -
 * chronological, quiet, monospaced timestamps against a thin rail. Every
 * entry is a real event the backend emitted; nothing here is synthesized.
 */
export function MissionTimeline({
  events,
  defaultCollapsed,
}: {
  events: MissionEvent[];
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(!!defaultCollapsed);
  const [expanded, setExpanded] = useState(false);
  const listRef = useRef<HTMLOListElement>(null);
  const ordered = [...events].sort((a, b) => a.sequence - b.sequence);
  const notable = ordered.filter((e) => NOTABLE.has(e.type));

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [notable.length]);

  return (
    <div className="surface-panel flex max-h-full flex-col rounded-lg">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-[10px] font-medium uppercase tracking-widest2 text-ink-500">
          Mission Log · {events.length}
        </span>
        <span className="text-ink-300">{collapsed ? "+" : "–"}</span>
      </button>
      {!collapsed && (
        <ol
          ref={listRef}
          className={`min-h-0 flex-1 overflow-y-auto border-t border-line pl-5 pr-4 ${
            expanded ? "max-h-[60vh]" : "max-h-64"
          }`}
        >
          {notable.map((event, index) => (
            <li key={event.id} className="relative border-l border-line py-3 pl-5 last:border-transparent">
              <span className="absolute -left-[3.5px] top-[18px] h-[6px] w-[6px] rounded-full bg-ink-300" />
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[10px] tabular-nums text-ink-300">
                  {formatClock(event.created_at)}
                </span>
                <span className="text-[12px] font-medium text-ink-900">
                  {EVENT_LABELS[event.type] ?? event.type}
                </span>
                {agentLabel(event.agent) && (
                  <span className="text-[11px] text-ink-500">{agentLabel(event.agent)}</span>
                )}
              </div>
              {event.message && <p className="mt-1 text-[12px] leading-snug text-ink-500">{event.message}</p>}
              {index === notable.length - 1 && <span className="sr-only">Latest event</span>}
            </li>
          ))}
          {notable.length === 0 && <p className="py-4 text-xs text-ink-300">Waiting for activity…</p>}
        </ol>
      )}
      {!collapsed && notable.length > 4 && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="border-t border-line px-4 py-2 text-left text-[10px] font-medium uppercase tracking-wide2 text-ink-300 transition hover:text-ink-500"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}
