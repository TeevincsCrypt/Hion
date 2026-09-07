/**
 * Pure event-sourcing reducer: folds hion's real `MissionEvent` log onto a
 * `Mission` snapshot. Every field this touches is read directly off the event
 * (status, retry_count, error, result_summary, or a documented `data` key the
 * backend already emits) - this mirrors the transitions hion's own engine
 * performs, it never guesses at one.
 *
 * Used two ways:
 *   - live: patch the REST-seeded mission with each new SSE event.
 *   - replay: fold a prefix of the stored event log onto an empty skeleton to
 *     reconstruct exactly what the mission looked like at that point in time,
 *     with no backend call involved.
 */
import type {
  ApprovalRequest,
  Critique,
  GuardianVerdict,
  Mission,
  MissionEvent,
  RiskLevel,
  Task,
  TaskStatus,
} from "./types";

export function emptyMissionSkeleton(id: string, goal: string, createdAt: string): Mission {
  return {
    id,
    goal,
    status: "PLANNING",
    objective: null,
    success_criteria: [],
    tasks: [],
    results: {},
    approvals: [],
    final_result: null,
    error: null,
    metrics: null,
    event_count: 0,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function upsertTask(tasks: Task[], taskId: string, patch: Partial<Task>): Task[] {
  let found = false;
  const next = tasks.map((task) => {
    if (task.id !== taskId) return task;
    found = true;
    return { ...task, ...patch };
  });
  return found ? next : tasks;
}

function upsertApproval(
  approvals: ApprovalRequest[],
  id: string,
  build: () => ApprovalRequest,
  patch?: Partial<ApprovalRequest>,
): ApprovalRequest[] {
  const existing = approvals.find((a) => a.id === id);
  if (!existing) return [...approvals, build()];
  if (!patch) return approvals;
  return approvals.map((a) => (a.id === id ? { ...a, ...patch } : a));
}

function statusFromEvent(event: MissionEvent): TaskStatus | null {
  switch (event.type) {
    case "task.started":
    case "task.retrying":
      return "RUNNING";
    case "critic.started":
      return "REVIEWING";
    case "approval.required":
      return "WAITING_FOR_APPROVAL";
    case "task.completed":
      return "COMPLETED";
    case "task.failed":
      return "FAILED";
    default:
      return null;
  }
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function critiqueFromEventData(event: MissionEvent): Critique | undefined {
  if (typeof event.data.score !== "number") return undefined;
  return {
    approved: event.data.approved === true,
    score: event.data.score,
    dimensions:
      event.data.dimensions && typeof event.data.dimensions === "object"
        ? (event.data.dimensions as Critique["dimensions"])
        : null,
    issues: asStringArray(event.data.issues),
    required_changes: asStringArray(event.data.required_changes),
    reasoning: typeof event.data.reasoning === "string" ? event.data.reasoning : "",
  };
}

function guardianVerdictFromEvent(event: MissionEvent): GuardianVerdict | undefined {
  if (!event.risk_level) return undefined;
  return {
    risk_level: event.risk_level,
    requires_human_approval: event.data.requires_human_approval === true,
    rationale: typeof event.data.rationale === "string" ? event.data.rationale : "",
    irreversible: event.data.irreversible === true,
    external_side_effects: event.data.external_side_effects === true,
  };
}

/** Folds a single real event onto a mission snapshot. */
export function applyEventToMission(mission: Mission, event: MissionEvent): Mission {
  let tasks = mission.tasks;

  if (event.type === "task.created" && event.task_id && !tasks.some((t) => t.id === event.task_id)) {
    tasks = [
      ...tasks,
      {
        id: event.task_id,
        key: typeof event.data.key === "string" ? event.data.key : event.task_id,
        title: typeof event.data.title === "string" ? event.data.title : event.message,
        description: typeof event.data.description === "string" ? event.data.description : "",
        assigned_agent: event.agent ?? "commander",
        status: "PENDING",
        dependencies: asStringArray(event.data.dependencies),
        acceptance_criteria: asStringArray(event.data.acceptance_criteria),
        result: null,
        critique: null,
        guardian_verdict: null,
        retry_count: 0,
        error: null,
        created_at: event.created_at,
        updated_at: event.created_at,
      },
    ];
  }

  if (event.task_id) {
    const patch: Partial<Task> = { updated_at: event.created_at };
    const nextStatus = statusFromEvent(event);
    if (nextStatus) patch.status = nextStatus;
    if (event.retry_count != null) patch.retry_count = event.retry_count;
    if (event.type === "task.failed" && event.error) patch.error = event.error;
    if (event.type === "task.completed" && event.result_summary) patch.result = event.result_summary;
    if (event.type === "critic.completed") {
      const critique = critiqueFromEventData(event);
      if (critique) patch.critique = critique;
    }
    if (event.type === "guardian.review") {
      const verdict = guardianVerdictFromEvent(event);
      if (verdict) patch.guardian_verdict = verdict;
    }
    tasks = upsertTask(tasks, event.task_id, patch);
  }

  let approvals = mission.approvals;
  const approvalId = typeof event.data.approval_id === "string" ? event.data.approval_id : null;
  if (event.type === "approval.required" && approvalId) {
    approvals = upsertApproval(approvals, approvalId, () => ({
      id: approvalId,
      mission_id: mission.id,
      task_id: event.task_id,
      action: typeof event.data.action === "string" ? event.data.action : event.message,
      risk_level: (event.risk_level ?? "HIGH") as RiskLevel,
      rationale: typeof event.data.rationale === "string" ? event.data.rationale : "",
      status: "PENDING",
      requested_at: event.created_at,
      resolved_at: null,
      decided_by: null,
      note: null,
    }));
  }
  if (
    approvalId &&
    (event.type === "approval.granted" ||
      event.type === "approval.rejected" ||
      event.type === "approval.timed_out")
  ) {
    const status =
      event.type === "approval.granted"
        ? "GRANTED"
        : event.type === "approval.rejected"
          ? "REJECTED"
          : "TIMED_OUT";
    approvals = upsertApproval(
      approvals,
      approvalId,
      () => ({
        id: approvalId,
        mission_id: mission.id,
        task_id: event.task_id,
        action: "",
        risk_level: event.risk_level ?? "HIGH",
        rationale: "",
        status,
        requested_at: event.created_at,
        resolved_at: event.created_at,
        decided_by: typeof event.data.decided_by === "string" ? event.data.decided_by : null,
        note: typeof event.data.note === "string" ? event.data.note : null,
      }),
      {
        status,
        resolved_at: event.created_at,
        decided_by: typeof event.data.decided_by === "string" ? event.data.decided_by : null,
        note: typeof event.data.note === "string" ? event.data.note : null,
      },
    );
  }

  let status = mission.status;
  if (event.type === "mission.planned") status = "RUNNING";
  if (event.type === "approval.required") status = "WAITING_FOR_APPROVAL";
  if (event.type === "approval.granted" || event.type === "approval.rejected") {
    const stillWaiting = tasks.some((t) => t.status === "WAITING_FOR_APPROVAL");
    if (!stillWaiting) status = "RUNNING";
  }
  if (event.type === "mission.completed") status = "COMPLETED";
  if (event.type === "mission.failed") status = "FAILED";

  let objective = mission.objective;
  let successCriteria = mission.success_criteria;
  if (event.type === "mission.planned") {
    if (typeof event.data.objective === "string") objective = event.data.objective;
    successCriteria = asStringArray(event.data.success_criteria);
  }

  let finalResult = mission.final_result;
  let error = mission.error;
  let metrics = mission.metrics;
  if (event.type === "mission.completed" && event.result_summary) {
    finalResult = event.result_summary;
  }
  if (event.type === "mission.failed" && event.error) {
    error = event.error;
  }
  if (
    (event.type === "mission.completed" || event.type === "mission.failed") &&
    event.data.metrics &&
    typeof event.data.metrics === "object"
  ) {
    metrics = event.data.metrics as Mission["metrics"];
  }

  return {
    ...mission,
    tasks,
    approvals,
    status,
    objective,
    success_criteria: successCriteria,
    final_result: finalResult,
    error,
    metrics,
    event_count: event.sequence,
    updated_at: event.created_at,
  };
}

/** Reconstructs a full mission snapshot by folding an ordered event log. */
export function reduceMissionFromEvents(seed: Mission, events: readonly MissionEvent[]): Mission {
  return events.reduce(applyEventToMission, seed);
}
