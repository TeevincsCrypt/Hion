# Hion — Mission Control

A cinematic, 3D command-center frontend for Hion. You give it a goal; a
Commander agent plans the work, and the crew — Researcher, Analyst, Creator,
Critic, Guardian, Executor — comes alive as stylized 3D characters floating in
a restrained, paper-white studio environment, whose state is driven entirely
by the real mission the Strands-based backend is running.

The visual language is deliberately monochrome — off-white paper, white
surfaces, near-black type, a single warm accent reserved for active/important
states, and a single red reserved for risk — so that color always means
something rather than decorating an agent. See `tailwind.config.ts` for the
full token set (`paper`, `surface`, `ink`, `line`, `accent`, `risk`, `ok`).

Built with Next.js 16 (App Router), React Three Fiber / drei / three, Tailwind
CSS and Zustand.

## Architecture

Four layers, kept deliberately separate (`hion/orchestration/engine.py`'s own
docstring makes the same argument on the backend side):

1. **Mission data** — `lib/types.ts` mirrors the backend's API schemas
   exactly. `lib/missionReducer.ts` is a pure, typed fold of the backend's own
   `MissionEvent` log onto a `Mission` snapshot: every field it writes comes
   directly from a field the event already carries. This is event sourcing,
   not simulation — the same transitions the Python engine performs, replayed
   client-side.
2. **Event stream** — `lib/useMissionEvents.ts` opens exactly one
   `EventSource` per mission. The backend always replays a mission's full
   historical log before going live (see `GET /api/missions/{id}/events/stream`
   in the backend), so this single connection is enough to reconstruct a
   mission whether this tab created it or is a fresh reload of one already in
   progress. `store/missionStore.ts` holds the result.
3. **Agent state** — `lib/deriveAgentState.ts` is pure functions from
   `(Mission, MissionEvent[])` to what each of the seven roster slots (the six
   backend agents plus a synthetic "Executor" for the tool-execution layer)
   should show right now: status, the task-graph-derived connections between
   them, and a short real activity caption. Nothing here is invented — a
   status is always traceable to a specific task field or event type, and
   captions are built only from a task's own title or an event's own message.
4. **3D visualization** — `components/3d/*` is a pure consumer of layer 3. It
   never holds mission state and never decides what an agent is doing.

### Why the crew looks like wireframes, not "real" characters

`components/3d/AgentCharacter.tsx` renders each agent as a translucent
physical-material core plus a bright wireframe edge overlay — a coherent,
replaceable placeholder system built from three.js primitives (icosahedron,
octahedron, tetrahedron, box, cone, torus, dodecahedron), not real character
models. Agents are told apart by geometry and floating labels, never by a
per-agent brand color — color on a character is reserved entirely for status
(idle grey, active accent, settled near-black, failed red), so a glance at the
scene reads as system state rather than decoration. `AgentCharacter` accepts
an optional `modelUrl` for a real GLTF/GLB asset; if it fails to load,
`ErrorBoundary.tsx` + `Suspense` fall back to the placeholder without breaking
the rest of the scene. Swapping in real characters later touches one prop,
not the animation, layout, or state logic. Clicking a character (live mode
only) opens the Agent Inspector — see below.

### Status → animation

Six states (`IDLE`, `WORKING`, `REVIEWING`, `WAITING`, `COMPLETED`, `FAILED`)
each drive rotation speed, bob amplitude, emissive intensity and material
opacity via `useFrame`, all read from refs rather than React state so the
frame loop never triggers a re-render. `COMPLETED` and `FAILED` additionally
arm a one-shot decaying pulse (a brief scale flash, or a brief position
jitter) the moment a transition is detected — a `useEffect` keyed on `status`,
not a render-time ref write, per React's rules on ref purity.

### Agent Inspector

Clicking any character during a live mission opens `mission/AgentInspector.tsx`,
a slide-over panel built entirely from `lib/deriveAgentState.ts`'s
`computeAgentInspector()` — role, current task, status, tools used, completed
task count, retries, cumulative duration, a result summary and a risk level,
all derived from the same event log everything else on the page reads, plus a
"Runtime process `hion-{id}`" line naming the underlying Strands agent
process. Nothing in the panel is invented for display purposes.

## Local development

The backend has no live model credentials in most dev environments. Two ways
to run the frontend against something real:

```bash
# 1. Against a real Hion backend (needs a working model provider - see the
#    root README and `hion doctor`):
cd .. && hion serve

# 2. Against the exact backend engine, event bus and API, with only the model
#    provider swapped for the same scripted double the backend's own test
#    suite uses (tests/support/scripted_model.py). This is NOT a mock agent
#    system - it is the harness `tests/test_api.py` already validates,
#    pointed at a live port instead of a test client. Useful when no model
#    credential is available:
cd .. && .venv/bin/python scripts/dev_backend.py
```

Then, in `web/`:

```bash
cp .env.example .env.local   # NEXT_PUBLIC_HION_API_URL, defaults to :8000
npm install
npm run dev                  # http://localhost:3000
```

## Scripts

```bash
npm run dev         # dev server (Turbopack)
npm run build        # production build
npm run start         # serve the production build
npm run lint          # eslint (flat config, next/core-web-vitals + next/typescript)
npm run typecheck    # tsc --noEmit
```

## Layout

```
src/
  app/
    page.tsx                 command screen (homepage)
    missions/[id]/page.tsx   Mission Control
    icon.tsx                 generated favicon
  components/
    3d/
      Scene.tsx              the one Canvas: lighting, fog, camera, particles
      CameraRig.tsx          restrained autonomous drift + pointer parallax
      AgentCharacter.tsx     one status-driven character (placeholder or GLTF)
      AgentRoster.tsx        the full crew, laid out; compresses on narrow screens
      ConnectionLines.tsx    task-graph edges + live activity pulses
      ParticleField.tsx      ambient motes (one draw call)
      ErrorBoundary.tsx      catches a failed GLTF load
      DynamicScene.tsx       client-only, code-split Canvas loader
    mission/
      MissionHud.tsx          goal, status, progress, elapsed time
      MissionTimeline.tsx    chronological system-log-style real event record
      AgentInspector.tsx     per-agent detail panel, opened by clicking a character
      GuardianOverlay.tsx    the approval moment, wired to POST /api/approvals/{id}
      CompletionPanel.tsx    real MissionMetrics + final_result
      ReplayControls.tsx     play/pause/restart/speed over the stored event log
      SystemStatus.tsx        "System Ready" indicator, backed by GET /api/health
      StrandsMark.tsx          small "Powered by Strands Agents SDK" credit
  lib/
    types.ts                 mirror of the backend's API schemas
    api.ts                   REST client (create mission, decide approval, …)
    useMissionEvents.ts       the SSE hook
    missionReducer.ts        pure event → Mission fold
    deriveAgentState.ts       pure Mission/events → agent status/edges/captions
    agents.ts                 static roster metadata (labels, colors, layout)
  store/
    missionStore.ts           zustand store: mission, events, replay state
```

## Replay

`REPLAY MISSION` (shown once a mission completes or fails) re-derives the
mission at any point in its own stored event log via
`missionReducer.reduceMissionFromEvents` — the same fold used live, just
applied to a prefix. No backend call is made and no agent is re-invoked;
`Play`/`Pause`/`Restart`/speed just step an index through history already
recorded, and the 3D roster and activity feed re-render from that
reconstructed snapshot exactly as they would live.
