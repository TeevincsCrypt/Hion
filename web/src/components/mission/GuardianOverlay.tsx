"use client";

import { useEffect, useRef, useState } from "react";
import { decideApproval, HionApiError } from "@/lib/api";
import type { ApprovalRequest, Mission } from "@/lib/types";
import { ROSTER } from "@/lib/agents";

const RISK_STYLES: Record<ApprovalRequest["risk_level"], string> = {
  LOW: "text-ink-500 border-line",
  MEDIUM: "text-accent border-accent/40",
  HIGH: "text-risk-high border-risk-high/40",
};

/**
 * The Guardian moment: a real pending approval, wired directly to
 * `POST /api/approvals/{id}`. Nothing here is simulated - the buttons call
 * the same endpoint an operator using curl would, and the mission only
 * resumes once the backend actually resolves it and the resulting
 * `approval.granted` / `approval.rejected` event arrives over SSE.
 */
export function GuardianOverlay({
  mission,
  approval,
}: {
  mission: Mission;
  approval: ApprovalRequest;
}) {
  const [deciding, setDeciding] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  const task = mission.tasks.find((t) => t.id === approval.task_id);
  const agentLabel = task ? `${ROSTER[task.assigned_agent].label} Agent` : "Hion";

  const decide = async (approved: boolean) => {
    setError(null);
    setDeciding(approved ? "approve" : "reject");
    try {
      await decideApproval(approval.id, approved);
      // The overlay closes itself once the store reflects the resolved
      // approval (driven by the SSE event, not by this call's response).
    } catch (err) {
      setDeciding(null);
      setError(err instanceof HionApiError ? err.message : "Could not reach Hion.");
    }
  };

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-paper/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="guardian-approval-title"
    >
      {/* Focus lands on the panel itself, never on a button: this dialog can
          authorise an irreversible external action, so a stray Enter key must
          not be able to approve it. */}
      <div
        ref={panelRef}
        tabIndex={-1}
        className="animate-fade-up surface-panel w-full max-w-md rounded-lg p-8 outline-none"
      >
        <p
          id="guardian-approval-title"
          className="text-center text-[10px] font-semibold uppercase tracking-widest2 text-accent"
        >
          Human Decision Required
        </p>
        {approval.rationale && (
          <p className="mt-4 text-center text-[15px] leading-relaxed text-ink-900">{approval.rationale}</p>
        )}

        <dl className="mt-7 space-y-4 border-t border-line pt-6">
          <Row label="Action" value={approval.action} />
          <Row
            label="Risk"
            value={
              <span
                className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${RISK_STYLES[approval.risk_level]}`}
              >
                {approval.risk_level}
              </span>
            }
          />
          <Row label="Requested by" value={agentLabel} />
        </dl>

        <div className="mt-8 flex gap-3">
          <button
            type="button"
            onClick={() => void decide(false)}
            disabled={deciding !== null}
            className="flex-1 rounded-full border border-ink-900/15 py-2.5 text-xs font-semibold uppercase tracking-wide2 text-ink-900 transition hover:border-risk-high/40 hover:text-risk-high disabled:opacity-50"
          >
            {deciding === "reject" ? "Rejecting…" : "Reject"}
          </button>
          <button
            type="button"
            onClick={() => void decide(true)}
            disabled={deciding !== null}
            className="flex-1 rounded-full bg-ink-900 py-2.5 text-xs font-semibold uppercase tracking-wide2 text-paper transition hover:bg-ink-600 disabled:opacity-50"
          >
            {deciding === "approve" ? "Approving…" : "Approve"}
          </button>
        </div>
        {error && <p className="mt-3 text-center text-xs text-risk-high">{error}</p>}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-[10px] font-medium uppercase tracking-widest2 text-ink-300">{label}</dt>
      <dd className="text-[13px] font-medium text-ink-900">{value}</dd>
    </div>
  );
}
