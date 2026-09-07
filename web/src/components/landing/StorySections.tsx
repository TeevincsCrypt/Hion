"use client";

import { CHARACTER_IDS, ROSTER } from "@/lib/agents";

/**
 * The scroll narrative below the hero. Its whole job is to answer, in the time
 * a judge takes to scroll, the question the 3D scene raises: what is actually
 * happening here?
 *
 * Every claim on this page is one the running system genuinely makes good on -
 * the pipeline is the engine's real sequence, the roster is the real roster
 * from `lib/agents.ts`, and the Guardian section describes the approval gate
 * that actually blocks execution. Nothing here is aspirational copy.
 */

const PIPELINE = [
  { step: "Goal", detail: "A person states the outcome, not the steps." },
  { step: "Plan", detail: "Commander decomposes it into a dependency-ordered task graph." },
  { step: "Delegate", detail: "Each task is assigned to the specialist that fits it." },
  { step: "Execute", detail: "Agents run with real tools, in a sandboxed workspace." },
  { step: "Critique", detail: "A Critic scores the output against acceptance criteria." },
  { step: "Fix", detail: "Rejected work is revised and re-reviewed, not shipped." },
  { step: "Approval", detail: "Guardian halts anything risky until a human decides." },
  { step: "Complete", detail: "The mission returns a finished deliverable." },
];

export function StorySections() {
  return (
    <div className="relative z-10 bg-paper">
      <Section index="01" title="AI assistants wait. Hion works.">
        <p>
          A chat assistant answers a question and stops. It has no plan, no memory of what it owes
          you, and no way to carry a piece of work from start to finish.
        </p>
        <p>
          Hion takes a goal and runs it as a mission — planning the work, delegating it across
          specialist agents, reviewing its own output, and stopping to ask when the stakes are real.
        </p>
      </Section>

      <Section index="02" title="How a mission runs">
        <ol className="mt-2 divide-y divide-line border-y border-line">
          {PIPELINE.map(({ step, detail }, i) => (
            <li key={step} className="flex flex-col gap-1 py-4 sm:flex-row sm:items-baseline sm:gap-6">
              <span className="flex shrink-0 items-baseline gap-3 sm:w-44">
                <span className="font-mono text-[11px] tabular-nums text-ink-200">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="text-[13px] font-semibold uppercase tracking-wide2 text-ink-900">
                  {step}
                </span>
              </span>
              <span className="text-[14px] leading-relaxed text-ink-500">{detail}</span>
            </li>
          ))}
        </ol>
      </Section>

      <Section index="03" title="The workforce">
        <p className="mb-8">
          Seven roles, each a separate agent running on the Strands Agents SDK, each with a
          different job and a different shape in the scene above.
        </p>
        <dl className="grid grid-cols-1 gap-x-10 gap-y-6 sm:grid-cols-2">
          {CHARACTER_IDS.map((id) => (
            <div key={id} className="border-l border-line pl-4">
              <dt className="text-[12px] font-semibold uppercase tracking-wide2 text-ink-900">
                {ROSTER[id].label}
              </dt>
              <dd className="mt-1 text-[13px] leading-relaxed text-ink-500">{ROSTER[id].role}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section index="04" title="Autonomy with a hand on the brake">
        <p>
          Hion runs on its own until something is irreversible or reaches outside the workspace.
          Then the Guardian stops the mission and asks a human — naming the action, the risk level,
          and which agent requested it.
        </p>
        <p>
          Nothing resumes until a person decides. That gate is real: the approval is recorded by the
          backend, and execution stays blocked until it resolves.
        </p>
      </Section>
    </div>
  );
}

function Section({
  index,
  title,
  children,
}: {
  index: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-line px-6 py-20 sm:px-10 sm:py-28">
      <div className="mx-auto max-w-3xl">
        <p className="mb-5 font-mono text-[11px] tabular-nums text-ink-300">{index}</p>
        <h2 className="max-w-2xl text-2xl font-semibold leading-tight tracking-tight text-ink-900 sm:text-[34px]">
          {title}
        </h2>
        <div className="mt-6 max-w-2xl space-y-4 text-[15px] leading-relaxed text-ink-500">
          {children}
        </div>
      </div>
    </section>
  );
}
