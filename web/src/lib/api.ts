/**
 * Thin REST client for the Hion backend. No business logic lives here - it
 * only shapes HTTP calls and parses JSON into the types in `./types`.
 */
import type { HealthResponse, Mission, MissionEvent, MissionMetrics } from "./types";

export function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_HION_API_URL ?? "http://localhost:8000";
}

export class HionApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "HionApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    let detail = body;
    try {
      detail = JSON.parse(body).detail ?? body;
    } catch {
      // body wasn't JSON; use it verbatim
    }
    throw new HionApiError(
      response.status,
      detail || `${response.status} ${response.statusText}`,
    );
  }

  return response.json() as Promise<T>;
}

export function createMission(goal: string): Promise<Mission> {
  return request<Mission>("/api/missions", {
    method: "POST",
    body: JSON.stringify({ goal }),
  });
}

export function getMission(missionId: string): Promise<Mission> {
  return request<Mission>(`/api/missions/${missionId}`);
}

export function getMissionEvents(
  missionId: string,
  afterSequence = 0,
): Promise<MissionEvent[]> {
  return request<MissionEvent[]>(
    `/api/missions/${missionId}/events?after=${afterSequence}`,
  );
}

export function getMissionMetrics(missionId: string): Promise<MissionMetrics> {
  return request<MissionMetrics>(`/api/missions/${missionId}/metrics`);
}

export function decideApproval(
  approvalId: string,
  approved: boolean,
  decidedBy = "operator",
): Promise<void> {
  return request(`/api/approvals/${approvalId}`, {
    method: "POST",
    body: JSON.stringify({ approved, decided_by: decidedBy }),
  }).then(() => undefined);
}

/** The real backend health check - used to show a genuine "system ready" state, not a decorative one. */
export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function missionEventStreamUrl(missionId: string): string {
  return `${apiBaseUrl()}/api/missions/${missionId}/events/stream`;
}
