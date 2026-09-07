"use client";

import { useState } from "react";
import { ROSTER } from "@/lib/agents";
import type { AgentName, EventType, MissionEvent } from "@/lib/types";

const EVENT_LABELS: Record<EventType, string> = {
  "mission.created": "Mission created",
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

function agentLabel(agent: AgentName | null): string | null {
  return agent ? ROSTER[agent].label : null;
}

function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour12: false });
}

export function ActivityPanel({ events }: { events: MissionEvent[] }) {
  const [collapsed, setCollapsed] = useState(false);
  const ordered = [...events].sort((a, b) => b.sequence - a.sequence);

  return (
    <div className="panel flex max-h-full flex-col rounded-2xl">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-[11px] font-semibold uppercase tracking-widest2 text-white/60">
          Activity ({events.length})
        </span>
        <span className="text-white/40">{collapsed ? "+" : "–"}</span>
      </button>
      {!collapsed && (
        <ol className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
          {ordered.map((event) => (
            <li key={event.id} className="rounded-lg px-2.5 py-1.5 hover:bg-white/[0.03]">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[10px] text-white/30">{formatClock(event.created_at)}</span>
                <span className="text-[11px] font-medium text-white/75">
                  {EVENT_LABELS[event.type] ?? event.type}
                </span>
                {agentLabel(event.agent) && (
                  <span className="text-[10px] text-white/35">· {agentLabel(event.agent)}</span>
                )}
              </div>
              {event.message && <p className="mt-0.5 truncate text-[11px] text-white/45">{event.message}</p>}
            </li>
          ))}
          {ordered.length === 0 && <p className="px-2.5 py-4 text-xs text-white/30">Waiting for activity…</p>}
        </ol>
      )}
    </div>
  );
}
