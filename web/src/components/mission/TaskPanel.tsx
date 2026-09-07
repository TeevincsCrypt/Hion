"use client";

import { useState } from "react";
import { ROSTER } from "@/lib/agents";
import type { Task, TaskStatus } from "@/lib/types";

/**
 * The mission's real task graph, straight from `mission.tasks` (the backend's
 * `TaskView`). Every field shown here - status, dependencies, retry count,
 * critique, guardian verdict, result - is one the backend already reported;
 * nothing is derived into a parallel status model, because the backend's own
 * `TaskStatus` already carries exactly the states this panel needs to show.
 */

const STATUS_LABEL: Record<TaskStatus, string> = {
  PENDING: "Pending",
  RUNNING: "Running",
  REVIEWING: "Reviewing",
  REVISION_REQUIRED: "Revision required",
  WAITING_FOR_APPROVAL: "Waiting for approval",
  COMPLETED: "Completed",
  FAILED: "Failed",
};

/** Colour carries state and nothing else - grey idle, accent active, green done, red failed. */
const STATUS_DOT: Record<TaskStatus, string> = {
  PENDING: "bg-ink-200",
  RUNNING: "bg-accent animate-pulse-slow",
  REVIEWING: "bg-accent animate-pulse-slow",
  REVISION_REQUIRED: "bg-accent",
  WAITING_FOR_APPROVAL: "bg-accent animate-pulse-slow",
  COMPLETED: "bg-ok",
  FAILED: "bg-risk-high",
};

const STATUS_TEXT: Record<TaskStatus, string> = {
  PENDING: "text-ink-300",
  RUNNING: "text-accent-dim",
  REVIEWING: "text-accent-dim",
  REVISION_REQUIRED: "text-accent-dim",
  WAITING_FOR_APPROVAL: "text-accent-dim",
  COMPLETED: "text-ok",
  FAILED: "text-risk-high",
};

export function TaskPanel({ tasks, defaultCollapsed }: { tasks: Task[]; defaultCollapsed?: boolean }) {
  const [collapsed, setCollapsed] = useState(!!defaultCollapsed);
  const [openId, setOpenId] = useState<string | null>(null);

  const done = tasks.filter((t) => t.status === "COMPLETED").length;

  return (
    <div className="surface-panel flex max-h-full flex-col rounded-lg">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
        className="flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-[10px] font-medium uppercase tracking-widest2 text-ink-500">
          Task Plan {tasks.length > 0 && `· ${done}/${tasks.length}`}
        </span>
        <span aria-hidden className="text-ink-300">
          {collapsed ? "+" : "–"}
        </span>
      </button>

      {!collapsed && (
        <div className="min-h-0 flex-1 overflow-y-auto border-t border-line">
          {tasks.length === 0 && (
            <p className="px-4 py-4 text-xs text-ink-300">Commander has not published a plan yet.</p>
          )}
          <ol>
            {tasks.map((task, index) => (
              <TaskRow
                key={task.id}
                task={task}
                index={index}
                allTasks={tasks}
                open={openId === task.id}
                onToggle={() => setOpenId(openId === task.id ? null : task.id)}
              />
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function TaskRow({
  task,
  index,
  allTasks,
  open,
  onToggle,
}: {
  task: Task;
  index: number;
  allTasks: Task[];
  open: boolean;
  onToggle: () => void;
}) {
  // `dependencies` holds task ids (the engine maps plan keys to ids), so
  // resolve them back to something a human can read.
  const deps = task.dependencies
    .map((id) => allTasks.find((t) => t.id === id))
    .filter((t): t is Task => !!t);

  return (
    <li className="border-b border-line last:border-transparent">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-start gap-2.5 px-4 py-3 text-left transition hover:bg-paper-dim"
      >
        <span className="mt-[5px] flex items-center gap-2">
          <span className="font-mono text-[10px] tabular-nums text-ink-200">
            {String(index + 1).padStart(2, "0")}
          </span>
          <span aria-hidden className={`h-1.5 w-1.5 shrink-0 rounded-full ${STATUS_DOT[task.status]}`} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12.5px] font-medium leading-snug text-ink-900">{task.title}</span>
          <span className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <span className="text-[11px] text-ink-500">{ROSTER[task.assigned_agent].label}</span>
            <span className={`text-[11px] ${STATUS_TEXT[task.status]}`}>{STATUS_LABEL[task.status]}</span>
            {task.retry_count > 0 && (
              <span className="text-[11px] text-ink-300">
                {task.retry_count} {task.retry_count === 1 ? "retry" : "retries"}
              </span>
            )}
            {task.critique && (
              <span className="text-[11px] text-ink-300">Critic {task.critique.score}/100</span>
            )}
          </span>
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-line bg-paper-dim/50 px-4 py-3">
          {task.description && (
            <Detail label="Description">
              <p className="leading-relaxed">{task.description}</p>
            </Detail>
          )}
          {deps.length > 0 && (
            <Detail label="Depends on">
              <p>{deps.map((d) => d.title).join(" · ")}</p>
            </Detail>
          )}
          {task.acceptance_criteria.length > 0 && (
            <Detail label="Acceptance criteria">
              <ul className="list-disc space-y-0.5 pl-4">
                {task.acceptance_criteria.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </Detail>
          )}
          {task.critique && (
            <Detail label={`Critique · ${task.critique.approved ? "approved" : "rejected"}`}>
              {task.critique.required_changes.length > 0 ? (
                <ul className="list-disc space-y-0.5 pl-4">
                  {task.critique.required_changes.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              ) : (
                <p>Score {task.critique.score}/100</p>
              )}
            </Detail>
          )}
          {task.guardian_verdict && (
            <Detail label={`Guardian · ${task.guardian_verdict.risk_level} risk`}>
              <p className="leading-relaxed">{task.guardian_verdict.rationale}</p>
            </Detail>
          )}
          {task.result && (
            <Detail label="Result">
              <p className="max-h-32 overflow-y-auto whitespace-pre-wrap leading-relaxed">{task.result}</p>
            </Detail>
          )}
          {task.error && (
            <Detail label="Error">
              <p className="leading-relaxed text-risk-high">{task.error}</p>
            </Detail>
          )}
        </div>
      )}
    </li>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[10px] font-medium uppercase tracking-wide2 text-ink-300">{label}</p>
      <div className="text-[12px] text-ink-600">{children}</div>
    </div>
  );
}
