"use client";

import { useState } from "react";
import Link from "next/link";
import { apiBaseUrl } from "@/lib/api";

/**
 * Shown when the mission stream cannot be established - the backend is down,
 * unreachable, or the mission id does not exist. Deliberately says what is
 * true and no more: the interface cannot reach the work system. The technical
 * detail is available but folded away, because a stack trace in the middle of
 * the screen is not an error state, it is a shrug.
 */
export function MissionInterrupted({ missionId, onRetry }: { missionId: string; onRetry: () => void }) {
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  return (
    <main className="flex h-dvh w-full items-center justify-center bg-paper px-6">
      <div className="animate-fade-up w-full max-w-md text-center">
        <p className="text-[10px] font-medium uppercase tracking-widest2 text-risk-high">
          Mission interrupted
        </p>
        <h1 className="mt-3 text-xl font-semibold text-ink-900">
          Unable to reach the autonomous work system
        </h1>
        <p className="mt-3 text-[13px] leading-relaxed text-ink-500">
          The mission may still be running. Hion could not open its event stream, so nothing shown
          here would be current.
        </p>

        <div className="mt-7 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={onRetry}
            className="rounded-full bg-ink-900 px-6 py-2.5 text-xs font-semibold uppercase tracking-wide2 text-paper transition hover:bg-ink-600"
          >
            Retry
          </button>
          <Link
            href="/"
            className="rounded-full border border-line px-5 py-2.5 text-xs font-semibold uppercase tracking-wide2 text-ink-600 transition hover:border-ink-900/25 hover:text-ink-900"
          >
            New mission
          </Link>
        </div>

        <button
          type="button"
          onClick={() => setShowDiagnostics((s) => !s)}
          aria-expanded={showDiagnostics}
          className="mt-8 text-[10px] font-medium uppercase tracking-wide2 text-ink-300 transition hover:text-ink-600"
        >
          {showDiagnostics ? "Hide diagnostics" : "Diagnostics"}
        </button>
        {showDiagnostics && (
          <dl className="animate-fade-in mt-3 space-y-1.5 rounded-md bg-paper-dim px-4 py-3 text-left">
            <Row label="Endpoint" value={`${apiBaseUrl()}/api/missions/${missionId}/events/stream`} />
            <Row label="Mission" value={missionId} />
            <Row label="Transport" value="EventSource (SSE)" />
          </dl>
        )}
      </div>
    </main>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <dt className="shrink-0 text-[10px] font-medium uppercase tracking-wide2 text-ink-300">{label}</dt>
      <dd className="min-w-0 break-all font-mono text-[10px] text-ink-600">{value}</dd>
    </div>
  );
}
