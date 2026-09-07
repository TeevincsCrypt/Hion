/**
 * Pure functions turning real mission data into what each 3D character should
 * show right now.
 *
 * This is the seam the architecture depends on: everything below reads only
 * `Mission` (tasks, statuses, approvals) and the raw `MissionEvent` log the
 * backend actually emitted. Nothing here invents activity - a status this
 * module reports is always traceable to a specific task field or event type.
 * The 3D layer is a consumer of these functions; it is never the source of
 * truth for what an agent is doing.
 */
import { CHARACTER_IDS, SPECIALIST_IDS, type CharacterId, type CharacterStatus } from "./agents";
import type { AgentName, Mission, MissionEvent, Task, TaskStatus } from "./types";

/**
 * Agents with an open agent.started...agent.completed/failed bracket, keyed by
 * agent name, valued by the set of task ids that agent is currently active on
 * (an empty-string entry means a mission-level call with no task, e.g. the
 * Commander's plan/synthesis calls or the Guardian's per-task risk check
 * before a task exists in RUNNING state).
 */
export type ActiveInvocations = Partial<Record<AgentName, Set<string>>>;

const NO_TASK = "";

/** Replays the event log to find which agents are mid-invocation right now. */
export function computeActiveInvocations(events: readonly MissionEvent[]): ActiveInvocations {
  const active: ActiveInvocations = {};

  const open = (agent: AgentName, taskId: string) => {
    (active[agent] ??= new Set()).add(taskId);
  };
  const close = (agent: AgentName, taskId: string) => {
    active[agent]?.delete(taskId);
  };

  for (const event of events) {
    if (!event.agent) continue;
    const taskId = event.task_id ?? NO_TASK;
    if (event.type === "agent.started") open(event.agent, taskId);
    if (event.type === "agent.completed" || event.type === "agent.failed") close(event.agent, taskId);
  }
  return active;
}

function isActive(active: ActiveInvocations, agent: AgentName): boolean {
  const set = active[agent];
  return !!set && set.size > 0;
}

/** Priority used to pick the single most relevant task when an agent owns several. */
const TASK_STATUS_PRIORITY: Record<TaskStatus, number> = {
  RUNNING: 6,
  REVISION_REQUIRED: 6,
  WAITING_FOR_APPROVAL: 5,
  REVIEWING: 4,
  FAILED: 2,
  PENDING: 1,
  COMPLETED: 1,
};

function mostRelevantTask(tasks: readonly Task[]): Task | undefined {
  return tasks.reduce<Task | undefined>((best, task) => {
    if (!best) return task;
    return TASK_STATUS_PRIORITY[task.status] > TASK_STATUS_PRIORITY[best.status] ? task : best;
  }, undefined);
}

function specialistStatus(agent: AgentName, mission: Mission): CharacterStatus {
  const tasks = mission.tasks.filter((t) => t.assigned_agent === agent);
  const task = mostRelevantTask(tasks);
  if (!task) return "IDLE";
  switch (task.status) {
    case "RUNNING":
    case "REVISION_REQUIRED":
      return "WORKING";
    case "REVIEWING":
      return "WAITING"; // the Critic is acting; this agent is paused, not idle
    case "WAITING_FOR_APPROVAL":
      return "WAITING";
    case "COMPLETED":
      return "COMPLETED";
    case "FAILED":
      return "FAILED";
    case "PENDING":
    default:
      return "IDLE";
  }
}

function commanderStatus(mission: Mission, active: ActiveInvocations): CharacterStatus {
  if (isActive(active, "commander")) return "WORKING";
  if (mission.status === "PLANNING") return "WORKING";
  if (mission.status === "COMPLETED") return "COMPLETED";
  if (mission.status === "FAILED") return "FAILED";
  return "IDLE";
}

function criticStatus(active: ActiveInvocations): CharacterStatus {
  return isActive(active, "critic") ? "REVIEWING" : "IDLE";
}

function guardianStatus(mission: Mission, active: ActiveInvocations): CharacterStatus {
  if (isActive(active, "guardian")) return "WORKING";
  const waiting = mission.tasks.some((t) => t.status === "WAITING_FOR_APPROVAL");
  if (waiting || mission.status === "WAITING_FOR_APPROVAL") return "WAITING";
  return "IDLE";
}

function executorStatus(events: readonly MissionEvent[]): CharacterStatus {
  const open = new Set<string>();
  for (const event of events) {
    const id = typeof event.data.tool_use_id === "string" ? event.data.tool_use_id : null;
    if (event.type === "tool.started" && id) open.add(id);
    if (event.type === "tool.completed" && id) open.delete(id);
  }
  return open.size > 0 ? "WORKING" : "IDLE";
}

/** The single source of visual truth for one backend agent, this instant. */
function agentCharacterStatus(
  id: AgentName,
  mission: Mission,
  active: ActiveInvocations,
): CharacterStatus {
  switch (id) {
    case "commander":
      return commanderStatus(mission, active);
    case "critic":
      return criticStatus(active);
    case "guardian":
      return guardianStatus(mission, active);
    default:
      return specialistStatus(id, mission);
  }
}

/** Status for every roster slot, including the synthetic "executor" node. */
export function computeAllStatuses(
  mission: Mission,
  events: readonly MissionEvent[],
): Record<CharacterId, CharacterStatus> {
  const active = computeActiveInvocations(events);
  const statuses = {} as Record<CharacterId, CharacterStatus>;
  for (const id of CHARACTER_IDS) {
    statuses[id] = id === "executor" ? executorStatus(events) : agentCharacterStatus(id, mission, active);
  }
  return statuses;
}

export interface ConnectionEdge {
  from: CharacterId;
  to: CharacterId;
  /** Structural edges are the plan's task graph; active edges pulse right now. */
  kind: "structural" | "active";
  taskId?: string;
}

/**
 * Agent-level connections derived from the mission's real task graph, plus the
 * transient edges that reflect what is happening this instant (a task being
 * reviewed, awaiting approval, or mid-tool-call). Nothing here assumes a fixed
 * commander -> research -> analyst -> creator chain; a different plan produces
 * a different graph.
 */
export function computeConnections(
  mission: Mission,
  events: readonly MissionEvent[],
): ConnectionEdge[] {
  const edges: ConnectionEdge[] = [];
  const seen = new Set<string>();
  const addStructural = (from: CharacterId, to: CharacterId) => {
    const key = `s:${from}->${to}`;
    if (seen.has(key)) return;
    seen.add(key);
    edges.push({ from, to, kind: "structural" });
  };

  const taskById = new Map(mission.tasks.map((t) => [t.id, t]));
  for (const task of mission.tasks) {
    if (task.dependencies.length === 0) {
      addStructural("commander", task.assigned_agent);
      continue;
    }
    for (const depId of task.dependencies) {
      const dep = taskById.get(depId);
      if (dep) addStructural(dep.assigned_agent, task.assigned_agent);
    }
  }

  const active = computeActiveInvocations(events);
  for (const task of mission.tasks) {
    if (task.status === "REVIEWING") {
      edges.push({ from: task.assigned_agent, to: "critic", kind: "active", taskId: task.id });
    }
    if (task.status === "WAITING_FOR_APPROVAL") {
      edges.push({ from: task.assigned_agent, to: "guardian", kind: "active", taskId: task.id });
    }
  }
  for (const agent of SPECIALIST_IDS) {
    if (isActive(active, agent)) {
      edges.push({ from: agent, to: "executor", kind: "active" });
    }
  }

  return edges;
}

export interface MissionProgress {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  activeAgents: CharacterId[];
}

export function computeProgress(
  mission: Mission,
  statuses: Record<CharacterId, CharacterStatus>,
): MissionProgress {
  return {
    totalTasks: mission.tasks.length,
    completedTasks: mission.tasks.filter((t) => t.status === "COMPLETED").length,
    failedTasks: mission.tasks.filter((t) => t.status === "FAILED").length,
    activeAgents: CHARACTER_IDS.filter(
      (id) => statuses[id] === "WORKING" || statuses[id] === "REVIEWING",
    ),
  };
}

export interface ActivityLabel {
  /** Short present-tense caption, e.g. "RESEARCHING". */
  headline: string;
  /** A real task title or the most recent event's own message. Never reasoning. */
  detail: string | null;
}

const WORKING_VERB: Record<AgentName, string> = {
  commander: "PLANNING",
  research: "RESEARCHING",
  analyst: "ANALYZING",
  creator: "WRITING",
  critic: "REVIEWING",
  guardian: "ASSESSING RISK",
};

function isTerminalTask(task: Task): boolean {
  return task.status === "COMPLETED" || task.status === "FAILED";
}

function lastEventForAgent(events: readonly MissionEvent[], agent: AgentName): MissionEvent | undefined {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i]?.agent === agent) return events[i];
  }
  return undefined;
}

function lastToolMessage(events: readonly MissionEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const event = events[i];
    if (event?.type === "tool.started" || event?.type === "tool.completed") return event.message;
  }
  return null;
}

/**
 * A short, real caption for every character currently doing something, built
 * only from the task it owns and the most recent event naming it - the same
 * two sources a person watching the raw event log would have.
 */
export function computeActivityLabels(
  mission: Mission,
  events: readonly MissionEvent[],
  statuses: Record<CharacterId, CharacterStatus>,
): Partial<Record<CharacterId, ActivityLabel>> {
  const labels: Partial<Record<CharacterId, ActivityLabel>> = {};

  for (const id of CHARACTER_IDS) {
    const status = statuses[id];
    if (status === "IDLE" || status === "COMPLETED" || status === "FAILED") continue;

    if (id === "executor") {
      labels.executor = { headline: "EXECUTING", detail: lastToolMessage(events) };
      continue;
    }

    const agent = id as AgentName;
    let headline = WORKING_VERB[agent];
    if (agent === "commander" && mission.tasks.length > 0 && mission.tasks.every(isTerminalTask)) {
      headline = "SYNTHESIZING";
    }
    if (status === "WAITING") {
      headline = agent === "guardian" ? "AWAITING APPROVAL" : "WAITING";
    }

    const task = mostRelevantTask(mission.tasks.filter((t) => t.assigned_agent === agent));
    const lastEvent = lastEventForAgent(events, agent);
    const detail = lastEvent?.message || task?.title || null;
    labels[id] = { headline, detail };
  }

  return labels;
}
