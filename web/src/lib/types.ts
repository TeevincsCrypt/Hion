/**
 * TypeScript mirror of hion's API schemas (hion/api/schemas.py,
 * hion/domain/models.py, hion/domain/enums.py).
 *
 * This file has no behavior - it is the contract the rest of the frontend is
 * built against. Keep it in lockstep with the backend; do not invent fields.
 */

export type MissionStatus =
  | "PLANNING"
  | "RUNNING"
  | "WAITING_FOR_APPROVAL"
  | "COMPLETED"
  | "FAILED";

export type TaskStatus =
  | "PENDING"
  | "RUNNING"
  | "REVIEWING"
  | "REVISION_REQUIRED"
  | "WAITING_FOR_APPROVAL"
  | "COMPLETED"
  | "FAILED";

/** The six specialist/oversight roles Strands agents run as. */
export type AgentName =
  | "commander"
  | "research"
  | "analyst"
  | "creator"
  | "critic"
  | "guardian";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type EventType =
  | "mission.created"
  | "mission.planned"
  | "plan.warning"
  | "mission.completed"
  | "mission.failed"
  | "task.created"
  | "task.started"
  | "task.completed"
  | "task.failed"
  | "task.retrying"
  | "agent.started"
  | "agent.completed"
  | "agent.failed"
  | "tool.started"
  | "tool.completed"
  | "tool.blocked"
  | "critic.started"
  | "critic.completed"
  | "revision.requested"
  | "revision.exhausted"
  | "guardian.review"
  | "approval.required"
  | "approval.granted"
  | "approval.rejected"
  | "approval.timed_out"
  | "stream.heartbeat";

export interface CritiqueDimensions {
  factual_support: number;
  completeness: number;
  consistency: number;
  task_compliance: number;
  source_quality: number;
  actionable_usefulness: number;
}

export interface Critique {
  approved: boolean;
  score: number;
  dimensions: CritiqueDimensions | null;
  issues: string[];
  required_changes: string[];
  reasoning: string;
}

export interface GuardianVerdict {
  risk_level: RiskLevel;
  requires_human_approval: boolean;
  rationale: string;
  irreversible: boolean;
  external_side_effects: boolean;
}

export interface Task {
  id: string;
  key: string;
  title: string;
  description: string;
  assigned_agent: AgentName;
  status: TaskStatus;
  dependencies: string[];
  acceptance_criteria: string[];
  result: string | null;
  critique: Critique | null;
  guardian_verdict: GuardianVerdict | null;
  retry_count: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface MissionEvent {
  id: string;
  mission_id: string;
  sequence: number;
  type: EventType;
  task_id: string | null;
  agent: AgentName | null;
  message: string;
  status: string | null;
  duration_ms: number | null;
  retry_count: number | null;
  tool_name: string | null;
  risk_level: RiskLevel | null;
  error: string | null;
  result_summary: string | null;
  data: Record<string, unknown>;
  created_at: string;
}

export interface ApprovalRequest {
  id: string;
  mission_id: string;
  task_id: string | null;
  action: string;
  risk_level: RiskLevel;
  rationale: string;
  status: "PENDING" | "GRANTED" | "REJECTED" | "TIMED_OUT";
  requested_at: string;
  resolved_at: string | null;
  decided_by: string | null;
  note: string | null;
}

export interface MissionMetrics {
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  tasks_accepted_with_open_critique: number;
  retries: number;
  agent_invocations: number;
  tool_calls: number;
  tool_calls_blocked: number;
  approvals_requested: number;
  approvals_granted: number;
  approvals_rejected: number;
  approvals_timed_out: number;
  revisions_requested: number;
  events_recorded: number;
  duration_seconds: number;
  started_at: string | null;
  finished_at: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  average_critic_score: number | null;
}

export interface Mission {
  id: string;
  goal: string;
  status: MissionStatus;
  objective: string | null;
  success_criteria: string[];
  tasks: Task[];
  results: Record<string, string>;
  approvals: ApprovalRequest[];
  final_result: string | null;
  error: string | null;
  metrics: MissionMetrics | null;
  event_count: number;
  created_at: string;
  updated_at: string;
}

export interface MissionSummary {
  id: string;
  goal: string;
  status: MissionStatus;
  task_count: number;
  created_at: string;
  updated_at: string;
}

export const TERMINAL_MISSION_STATUSES: readonly MissionStatus[] = [
  "COMPLETED",
  "FAILED",
];

export function isTerminalMissionStatus(status: MissionStatus): boolean {
  return TERMINAL_MISSION_STATUSES.includes(status);
}

/** GET /api/health - liveness plus the configuration the backend is actually running with. */
export interface HealthResponse {
  status: "ok" | "misconfigured";
  model_provider: string;
  model_id: string | null;
  provider_configured: boolean;
  detail: string;
  max_revisions: number;
  on_revisions_exhausted: string;
  auto_approve_max_risk: RiskLevel;
  critic_approval_threshold: number;
  critic_min_dimension_score: number;
  event_types: string[];
}
