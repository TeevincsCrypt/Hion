"use client";

import { useState } from "react";
import { decideApproval, HionApiError } from "@/lib/api";
import type { ApprovalRequest, Mission } from "@/lib/types";
import { ROSTER } from "@/lib/agents";

const RISK_STYLES: Record<ApprovalRequest["risk_level"], string> = {
  LOW: "text-signal-research border-signal-research/40",
  MEDIUM: "text-warn border-warn/40",
  HIGH: "text-danger border-danger/40",
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

  const task = mission.tasks.find((t) => t.id === approval.task_id);
  const agentLabel = task ? ROSTER[task.assigned_agent].label : "Hion";

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
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-void-950/55 backdrop-blur-[2px]">
      <div className="animate-fade-up panel w-full max-w-lg rounded-2xl p-7 shadow-glow shadow-signal-guardian/10">
        <p className="text-center text-[11px] font-semibold uppercase tracking-widest2 text-signal-guardian">
          Human Decision Required
        </p>
        <h2 className="mt-3 text-center text-lg font-medium text-white/95">{approval.action}</h2>

        <div className="mt-5 flex items-center justify-center gap-6 text-sm">
          <Field label="Risk">
            <span
              className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${RISK_STYLES[approval.risk_level]}`}
            >
              {approval.risk_level}
            </span>
          </Field>
          <Field label="Agent">
            <span className="text-white/85">{agentLabel}</span>
          </Field>
        </div>

        {approval.rationale && (
          <p className="mt-5 rounded-xl bg-white/[0.03] px-4 py-3 text-center text-[13px] leading-relaxed text-white/60">
            {approval.rationale}
          </p>
        )}

        <div className="mt-7 flex gap-3">
          <button
            type="button"
            onClick={() => void decide(false)}
            disabled={deciding !== null}
            className="flex-1 rounded-full border border-danger/40 py-2.5 text-xs font-semibold uppercase tracking-widest2 text-danger transition hover:bg-danger/10 disabled:opacity-50"
          >
            {deciding === "reject" ? "Rejecting…" : "Reject"}
          </button>
          <button
            type="button"
            onClick={() => void decide(true)}
            disabled={deciding !== null}
            className="flex-1 rounded-full bg-ok/90 py-2.5 text-xs font-semibold uppercase tracking-widest2 text-void-950 transition hover:bg-ok disabled:opacity-50"
          >
            {deciding === "approve" ? "Approving…" : "Approve"}
          </button>
        </div>
        {error && <p className="mt-3 text-center text-xs text-danger">{error}</p>}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="text-center">
      <p className="text-[10px] font-medium uppercase tracking-widest2 text-white/30">{label}</p>
      <div className="mt-1">{children}</div>
    </div>
  );
}
