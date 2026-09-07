# Hion

**Autonomous work management, built on the [Strands Agents SDK](https://strandsagents.com).**

You do not ask Hion questions. You give it a goal.

A **Commander** agent works out what you actually need, decomposes it into a task
graph, and delegates each task to a specialist. A **Critic** evaluates every
result and sends weak work back for revision. A **Guardian** decides what a human
has to approve before it happens — and enforces that decision inside the tool
pipeline, not just in a prompt. Every transition is recorded as a mission event
and streamed live.

---

## Status

Backend and agent brain, complete and tested end to end. No UI yet — that is the
next layer, and the event stream is shaped for it.

```
95 tests passing · ruff clean · mypy clean · Strands Agents SDK 1.54
```

`hion doctor` confirms whether a real model is currently reachable in your
environment, and `hion verify` runs the full lifecycle against it.

---

## The crew

| Agent | Role | Tools | Structured output |
|---|---|---|---|
| **Commander** | Plans the mission, synthesises the final result | none | `MissionPlan` |
| **Research** | Gathers and verifies information from the web | search, fetch, workspace read/write, datasets | — |
| **Analyst** | Compares options, finds risks, recommends | search, fetch, workspace read, datasets | — |
| **Creator** | Writes the deliverable | full workspace, external publishing | — |
| **Critic** | Judges another agent's result | none | `Critique` |
| **Guardian** | Decides what needs human approval | none | `GuardianVerdict` |

Capability is scoped per role. The Critic and Guardian have no tools at all —
they judge, they do not act. The Research agent cannot publish anything.

---

## How Strands is used

Strands is the execution substrate, not a wrapper around one.

- **Every agent is a real `strands.Agent`** with its own system prompt, tool set
  and hooks, running on a shared `Model`. There are no scripted replies and no
  simulated reasoning anywhere in `hion/`.
- **Typed agent contracts run through Strands structured output.** The
  Commander's plan, the Critic's verdict and the Guardian's risk assessment are
  Pydantic models passed as `structured_output_model` into the agent invocation,
  so they are schema-constrained rather than parsed out of prose.
- **The Guardian enforces policy inside the SDK's tool pipeline.** A
  `HookProvider` on `BeforeToolCallEvent` sets `cancel_tool` on any call whose
  risk exceeds the ceiling a human actually approved. The block reaches the model
  as a tool error explaining why. It cannot be talked around.
- **Observability comes from the SDK, not from guesswork.** A second
  `HookProvider` turns `BeforeInvocationEvent`, `AfterInvocationEvent`,
  `BeforeToolCallEvent` and `AfterToolCallEvent` into mission events, so the
  activity stream reflects what the event loop actually did.

### Why a custom engine instead of `Graph` or `Swarm`

Strands ships multi-agent primitives. They do not fit this problem, for three
reasons:

1. The task graph is **generated at runtime** by the Commander, not declared up front.
2. Execution must **suspend indefinitely mid-graph** while a human decides on an
   approval, then resume exactly where it stopped.
3. Every transition must be a **replayable event**, because Mission Control
   renders from the log.

`hion/orchestration/engine.py` is those three requirements and nothing else.
Everything it coordinates — planning, delegation, critique, revision, risk
assessment — is a real Strands agent invocation.

---

## Mission lifecycle

```
goal
 │
 ├─ Commander plans ──────────────► MissionPlan (validated: no cycles, no dangling deps)
 │
 ├─ for each dependency wave, concurrently:
 │    │
 │    ├─ Guardian assesses risk ──► LOW / MEDIUM / HIGH
 │    │     └─ needs a human? ────► mission suspends on APPROVAL_REQUIRED
 │    │                              rejected ──► task FAILED
 │    │
 │    ├─ specialist executes (tool calls gated at the approved ceiling)
 │    │
 │    └─ Critic reviews ──────────► approved? ──► task COMPLETED
 │          └─ rejected ──────────► specialist revises with the critique
 │                                   (up to HION_MAX_REVISIONS)
 │
 └─ Commander synthesises ────────► final result
```

**Mission**: `PLANNING → RUNNING → WAITING_FOR_APPROVAL → COMPLETED | FAILED`

**Task**: `PENDING → RUNNING → REVIEWING → REVISION_REQUIRED → WAITING_FOR_APPROVAL → COMPLETED | FAILED`

`WAITING_FOR_APPROVAL` is a genuine suspension: the mission's asyncio task awaits
a future that only an HTTP call can resolve. Nothing proceeds on a guess about
what the human would have said.

---

## Risk model

The Guardian agent reasons about risk. The static policy in `hion/tools/risk.py`
is the floor, applied mechanically before any tool runs:

| Level | Actions | Approval |
|---|---|---|
| **LOW** | search, fetch, read, list, create a new artifact in the mission workspace | auto |
| **MEDIUM** | modify or delete an existing artifact | configurable |
| **HIGH** | anything leaving the system: publishing, sending, irreversible change | **always required** |

Two rules are not negotiable by the model:

- An **unknown tool defaults to HIGH**. Unknown means dangerous.
- **HIGH always requires a human**, whatever the Guardian concluded and whatever
  `HION_AUTO_APPROVE_MAX_RISK` is set to.

### Nothing is pretended

External side effects either happen or fail loudly. `publish_external` with no
configured destination returns an error telling the agent to report that nothing
was published — it never claims delivery. `web_search` with no backend returns an
error rather than inventing plausible results, and the Critic is instructed not
to penalise an agent for honestly reporting a gap.

---

## Quickstart

```bash
uv venv && uv pip install -e '.[dev]'
cp .env.example .env      # then set your provider credentials
```

**Check the provider actually works before running a mission:**

```bash
hion doctor
```

This makes one real, cheap call to whatever provider is configured and reports
`REACHABLE` or `UNREACHABLE` with an actionable reason — an invalid or expired
credential, a model not enabled for the account, wrong region, no network
route. `hion run` and `hion serve` both refuse to start a mission against a
provider that fails this check rather than failing deep inside a mission.

Run a mission in the terminal, with a live event feed:

```bash
hion run "Research the top competitors in the AI meeting assistant market \
and prepare a concise competitive brief."
```

Or serve the API:

```bash
hion serve            # http://localhost:8000/docs
```

**Run the full lifecycle against a real model and get a pass/fail report:**

```bash
hion verify
```

Runs the reference mission for real and checks every stage of the lifecycle
against what actually happened — the plan, delegation, tool use, critique,
Guardian assessment, completion — from the mission's own event log. Exits
non-zero if anything is missing.

### Model providers

Provider-agnostic by design — the engine only ever sees a `strands.models.Model`.
No credential is ever hardcoded; everything comes from the environment.

```bash
HION_MODEL_PROVIDER=auto       # default: Bedrock if AWS credentials are present,
                                # else falls back to an API-key provider
HION_MODEL_PROVIDER=bedrock    # pin explicitly, no extra needed
HION_MODEL_PROVIDER=anthropic  # pip install 'hion[anthropic]'; needs HION_MODEL_API_KEY
HION_MODEL_PROVIDER=openai     # pip install 'hion[openai]'; needs HION_MODEL_API_KEY
HION_MODEL_PROVIDER=ollama     # pip install 'hion[ollama]'; local, no key needed
```

With nothing configured, startup fails immediately with the exact environment
variables to set — never with a stack trace from inside a running mission. A
configured-but-broken provider (revoked key, wrong region, model not enabled)
is diagnosed the same way, in one sentence naming the cause and the fix.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/missions` | Start a mission. Returns immediately with the mission id and initial state. |
| `GET` | `/api/missions` | List missions, newest first. |
| `GET` | `/api/missions/{id}` | Full mission state: tasks, critiques, verdicts, approvals, result. |
| `GET` | `/api/missions/{id}/events` | Recorded events. `?after=N` for incremental polling. |
| `GET` | `/api/missions/{id}/metrics` | `MissionMetrics`: tasks, retries, tool calls, approvals, tokens, duration. |
| `GET` | `/api/missions/{id}/events/stream` | **SSE**: replays the log, then streams live. |
| `GET` | `/api/approvals` | Approvals waiting on a human. `?mission_id=` to filter. |
| `POST` | `/api/approvals/{id}` | Grant or reject, resuming the suspended mission. |
| `GET` | `/api/health` | Liveness and effective configuration (whether a provider is even configured). |
| `GET` | `/api/health/provider` | Makes one real call to the model provider; reports reachable or the diagnosed cause. |
| `GET` | `/api/risk-policy` | The risk tiers the Guardian's tool gate actually enforces. |

```bash
curl -X POST localhost:8000/api/missions \
  -H 'content-type: application/json' \
  -d '{"goal": "Research the top competitors in the AI meeting assistant market and prepare a concise competitive brief."}'

curl -N localhost:8000/api/missions/msn_abc123/events/stream
```

### Events

Every event carries `id`, `sequence`, `mission_id`, `task_id`, `agent`, `type`,
`message`, `status`, `duration_ms`, `retry_count`, `tool_name`, `risk_level`,
`error`, a truncated `result_summary`, a typed `data` payload, and a timestamp —
enough for a Mission Control UI to render the stream without re-deriving state.

Only text output ever reaches an event or a task result. Reasoning content
blocks are dropped at the point output is read from the model, so hidden
chain-of-thought can never appear in the log, the API, or `result_summary` —
observability here means recorded actions and decisions, not internal reasoning.

```
mission.created     mission.planned      mission.completed    mission.failed      plan.warning
task.created        task.started         task.completed       task.failed         task.retrying
agent.started       agent.completed      agent.failed
tool.started        tool.completed       tool.blocked
critic.started      critic.completed     revision.requested   revision.exhausted
guardian.review     approval.required    approval.granted     approval.rejected   approval.timed_out
```

### Metrics

`GET /api/missions/{id}/metrics` returns a `MissionMetrics` snapshot, computed
from the mission's own tasks and event log — so it can never disagree with the
activity stream a UI renders from the same data:

```
total_tasks · completed_tasks · failed_tasks · tasks_accepted_with_open_critique
retries · revisions_requested · agent_invocations · tool_calls · tool_calls_blocked
approvals_requested/granted/rejected/timed_out · events_recorded
input/output/total_tokens · average_critic_score · duration_seconds
```

A running mission returns a live snapshot of the same shape; a finished one
returns the snapshot taken at completion.

---

## Layout

```
hion/
  config.py              HION_*-prefixed settings; auto/bedrock/anthropic/openai/ollama resolution
  verify.py              hion verify: real-model lifecycle checks against the reference mission
  domain/                enums + the mission/task/event/critique/verdict/metrics models
  events/                event bus (live fan-out) and recorder (the single write path)
  store/                 mission persistence behind a swappable protocol
  llm/
    provider.py            Strands Model factory: bedrock | anthropic | openai | ollama
    preflight.py           one real call to confirm a provider works; translates
                            provider errors into one actionable sentence
  tools/                 the executor: workspace, research, external, risk policy, per-role registry
  hooks/                 telemetry hook, the Guardian's tool gate, and the SDK-internal-tool filter
  agents/                prompts, agent factory, Commander, Critic, Guardian, specialist runner
  orchestration/
    engine.py              the mission engine
    approvals.py           the approval registry
    metrics.py             MissionMetrics computed from mission state and events
  api/                   FastAPI app, routes, schemas, DI container
  cli.py                 hion serve | run | doctor | verify
tests/
  support/               the scripted model provider and the reference scenario
```

---

## Testing

```bash
pytest              # 95 tests
ruff check .
mypy                # optional dev dependency; pyproject.toml configures it
```

The suite runs the **real** agents, tool pipeline, hooks and engine. Only the
model provider is substituted — `tests/support/scripted_model.py` is a genuine
`strands.models.Model` implementation that replays a fixed script, the same way
you would substitute an HTTP client in any other test. That is what makes
assertions like these possible without a paid API call:

- a Critic rejection really drives a revision, and the required changes reach the
  Creator's next prompt;
- the Creator's attempt to call `publish_external` is really blocked by the
  Guardian's hook, and recorded as `blocked` rather than as done;
- an unclassified tool name is treated as HIGH risk and blocked, every time it
  is attempted, not just the first;
- `save_dataset` and `update_file` really write files to disk;
- a human "no" really fails the task, and the Creator never runs;
- a Critic that never approves still terminates at `HION_MAX_REVISIONS`, and by
  default fails the task with an explanation naming the score, the weakest
  evaluation dimension, and what was still outstanding — never accepted
  silently and never looped forever;
- a model that answers in prose where a `MissionPlan` or `Critique` was
  required fails just that step, with a typed `MalformedModelOutput` error,
  not a crash;
- a Guardian or Critic invocation that raises fails only the task it was
  judging, not every task running concurrently with it;
- mission metrics agree exactly with the event log they were computed from,
  including on a mission that failed outright.

`hion verify` is the real-model equivalent of the lifecycle test: same
assertions, run against whatever provider is actually configured.

---

## Extending it

- **A new specialist**: add it to `AgentName`, write a prompt in
  `agents/prompts.py`, scope its tools in `tools/registry.py`. The Commander can
  delegate to it immediately.
- **A new tool**: write a `@tool` function, register it for a role, and give it a
  risk level in `tools/risk.py`. The Guardian gates it automatically.
- **Durable missions**: implement the `MissionStore` protocol. Nothing else changes.
