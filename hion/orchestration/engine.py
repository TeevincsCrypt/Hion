"""The mission engine.

This is Hion's control loop. Strands runs the agents; this module decides which
agent runs, in what order, with what context, what happens when the Critic
rejects a result, and when a human has to be asked.

Why a purpose-built engine rather than ``strands.multiagent.Graph`` or ``Swarm``:
the task graph here is *generated at runtime* by the Commander, execution must be
able to suspend indefinitely mid-graph while a human approves an action, and every
transition has to be recorded as a replayable event. Those three requirements are
the engine. Everything below them - planning, delegation, critique, revision,
risk assessment - is a real Strands agent invocation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from hion.agents.commander import Commander
from hion.agents.critic import Critic
from hion.agents.factory import AgentFactory
from hion.agents.guardian import Guardian
from hion.agents.specialist import SpecialistRunner
from hion.config import Settings
from hion.domain.enums import AgentName, EventType, MissionStatus, RiskLevel, TaskStatus
from hion.domain.models import (
    AgentRun,
    ApprovalRequest,
    Critique,
    GuardianVerdict,
    Mission,
    MissionPlan,
    Task,
)
from hion.errors import ApprovalRejected, ApprovalTimeout, PlanningError
from hion.events.bus import EventBus
from hion.events.recorder import MissionRecorder
from hion.llm.provider import ModelFactory
from hion.orchestration.approvals import ApprovalRegistry
from hion.store.memory import MissionStore
from hion.tools.context import ExecutionContext

logger = logging.getLogger(__name__)


class MissionEngine:
    """Owns the mission lifecycle from goal to final result."""

    def __init__(
        self,
        *,
        settings: Settings,
        store: MissionStore,
        bus: EventBus,
        approvals: ApprovalRegistry,
        model_factory: ModelFactory,
    ) -> None:
        self._settings = settings
        self._store = store
        self._bus = bus
        self._approvals = approvals
        self._model_factory = model_factory
        self._running: dict[str, asyncio.Task[None]] = {}

    # -- public API --------------------------------------------------------

    async def start_mission(self, goal: str) -> Mission:
        """Create a mission and begin executing it in the background."""
        mission = Mission(goal=goal)
        self._store.add(mission)
        recorder = MissionRecorder(mission, self._bus)
        recorder.emit(EventType.MISSION_CREATED, message="Mission created", goal=goal)

        task = asyncio.create_task(self._run(mission), name=f"hion-mission-{mission.id}")
        self._running[mission.id] = task
        task.add_done_callback(lambda _: self._running.pop(mission.id, None))
        return mission

    async def run_mission_to_completion(self, goal: str) -> Mission:
        """Start a mission and await it. Used by the CLI and by tests."""
        mission = await self.start_mission(goal)
        await self.wait_for(mission.id)
        return mission

    async def wait_for(self, mission_id: str) -> None:
        """Await a running mission's background task, if it is still running."""
        task = self._running.get(mission_id)
        if task is not None:
            await asyncio.shield(task)

    # -- lifecycle ---------------------------------------------------------

    async def _run(self, mission: Mission) -> None:
        recorder = MissionRecorder(mission, self._bus)
        try:
            crew = self._build_crew(mission, recorder)
            plan = await self._plan(mission, crew.commander)
            self._materialise(mission, recorder, plan)

            mission.status = MissionStatus.RUNNING
            mission.touch()

            await self._execute_graph(mission, recorder, crew)
            await self._finalise(mission, recorder, crew.commander)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
        except Exception as exc:  # noqa: BLE001 - the engine is the last line of defence
            logger.exception("Mission %s failed", mission.id)
            mission.status = MissionStatus.FAILED
            mission.error = f"{type(exc).__name__}: {exc}"
            mission.touch()
            recorder.emit(
                EventType.MISSION_FAILED,
                message=f"Mission failed: {mission.error}",
                error=mission.error,
            )

    def _build_crew(self, mission: Mission, recorder: MissionRecorder) -> _Crew:
        ctx = ExecutionContext(mission_id=mission.id, settings=self._settings)
        factory = AgentFactory(model=self._model_factory(), ctx=ctx)
        return _Crew(
            commander=Commander(factory, recorder),
            specialists=SpecialistRunner(factory, recorder),
            critic=Critic(factory, recorder),
            guardian=Guardian(factory, recorder, self._settings),
        )

    async def _plan(self, mission: Mission, commander: Commander) -> MissionPlan:
        try:
            plan = await commander.plan(mission.goal)
        except PlanningError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PlanningError(f"Planning failed: {type(exc).__name__}: {exc}") from exc
        return plan

    def _materialise(self, mission: Mission, recorder: MissionRecorder, plan: MissionPlan) -> None:
        """Turn a validated plan into mission tasks and emit the creation events."""
        mission.objective = plan.objective
        mission.success_criteria = list(plan.success_criteria)

        key_to_id: dict[str, str] = {}
        for planned in plan.tasks:
            task = Task(
                mission_id=mission.id,
                key=planned.key,
                title=planned.title,
                description=planned.description,
                assigned_agent=planned.assigned_agent,
                acceptance_criteria=list(planned.acceptance_criteria),
            )
            key_to_id[planned.key] = task.id
            mission.tasks.append(task)

        for planned, task in zip(plan.tasks, mission.tasks, strict=True):
            task.dependencies = [key_to_id[dep] for dep in planned.depends_on]

        recorder.emit(
            EventType.MISSION_PLANNED,
            message=f"Commander planned {len(mission.tasks)} tasks",
            agent=AgentName.COMMANDER,
            objective=plan.objective,
            success_criteria=mission.success_criteria,
            task_count=len(mission.tasks),
        )
        for task in mission.tasks:
            recorder.emit(
                EventType.TASK_CREATED,
                message=f"Task created: {task.title}",
                task_id=task.id,
                agent=task.assigned_agent,
                title=task.title,
                description=task.description,
                assigned_agent=task.assigned_agent.value,
                dependencies=task.dependencies,
                acceptance_criteria=task.acceptance_criteria,
            )

    async def _execute_graph(self, mission: Mission, recorder: MissionRecorder, crew: _Crew) -> None:
        """Run tasks in dependency waves until nothing is left to run."""
        semaphore = asyncio.Semaphore(self._settings.max_concurrency)

        while True:
            ready = _ready_tasks(mission)
            if not ready:
                break

            async def guarded(task: Task) -> None:
                async with semaphore:
                    await self._execute_task(mission, recorder, crew, task)

            await asyncio.gather(*(guarded(task) for task in ready))

        _mark_unreachable(mission, recorder)

    async def _execute_task(
        self, mission: Mission, recorder: MissionRecorder, crew: _Crew, task: Task
    ) -> None:
        """Guardian gate, execute, critique, revise - for one task."""
        try:
            ceiling = await self._clear_guardian(mission, recorder, crew, task)
        except ApprovalRejected as exc:
            _fail_task(recorder, task, str(exc))
            return
        except ApprovalTimeout as exc:
            _fail_task(recorder, task, str(exc))
            return

        task.status = TaskStatus.RUNNING
        task.touch()
        recorder.emit(
            EventType.TASK_STARTED,
            message=f"Task started: {task.title}",
            task_id=task.id,
            agent=task.assigned_agent,
            approved_risk_ceiling=ceiling.value,
        )

        context = _upstream_context(mission, task)
        critique: Critique | None = None
        previous: str | None = None

        while True:
            run = AgentRun(agent=task.assigned_agent, attempt=task.retry_count + 1)
            try:
                outcome = await crew.specialists.run(
                    goal=mission.goal,
                    task=task,
                    context=context,
                    approved_ceiling=ceiling,
                    critique=critique,
                    previous_result=previous,
                )
            except Exception as exc:  # noqa: BLE001 - one task failing must not kill the mission
                logger.exception("Task %s failed during agent execution", task.id)
                run.error = f"{type(exc).__name__}: {exc}"
                run.finished_at = datetime.now(UTC)
                task.runs.append(run)
                recorder.emit(
                    EventType.AGENT_FAILED,
                    message=f"{task.assigned_agent.value} agent raised: {run.error}",
                    task_id=task.id,
                    agent=task.assigned_agent,
                    error=run.error,
                )
                _fail_task(recorder, task, run.error)
                return

            run.output = outcome.text
            run.tool_calls = outcome.tool_calls
            run.usage = outcome.usage
            run.finished_at = datetime.now(UTC)
            task.runs.append(run)
            task.result = outcome.text
            task.touch()

            critique = await self._critique(mission, recorder, crew, task, context)
            task.critique = critique

            if critique.approved:
                _complete_task(mission, recorder, task)
                return

            if task.retry_count >= self._settings.max_revisions:
                recorder.emit(
                    EventType.REVISION_EXHAUSTED,
                    message=(
                        f"Critic still rejects after {task.retry_count} revision(s) "
                        f"(score {critique.score}/100)"
                    ),
                    task_id=task.id,
                    agent=AgentName.CRITIC,
                    score=critique.score,
                    required_changes=critique.required_changes,
                )
                if self._settings.on_revisions_exhausted == "fail":
                    _fail_task(
                        recorder,
                        task,
                        f"Critic rejected the result after {task.retry_count} revision(s).",
                    )
                else:
                    _complete_task(mission, recorder, task, degraded=True)
                return

            previous = outcome.text
            task.retry_count += 1
            task.status = TaskStatus.REVISION_REQUIRED
            task.touch()
            recorder.emit(
                EventType.REVISION_REQUESTED,
                message=f"Critic rejected the result (score {critique.score}/100)",
                task_id=task.id,
                agent=AgentName.CRITIC,
                score=critique.score,
                issues=critique.issues,
                required_changes=critique.required_changes,
            )
            recorder.emit(
                EventType.TASK_RETRYING,
                message=f"{task.assigned_agent.value} revising (attempt {task.retry_count + 1})",
                task_id=task.id,
                agent=task.assigned_agent,
                attempt=task.retry_count + 1,
            )
            task.status = TaskStatus.RUNNING
            task.touch()

    async def _critique(
        self, mission: Mission, recorder: MissionRecorder, crew: _Crew, task: Task, context: str
    ) -> Critique:
        task.status = TaskStatus.REVIEWING
        task.touch()
        recorder.emit(
            EventType.CRITIC_STARTED,
            message=f"Critic reviewing: {task.title}",
            task_id=task.id,
            agent=AgentName.CRITIC,
        )
        critique = await crew.critic.review(
            goal=mission.goal, task=task, result=task.result or "", context=context
        )
        recorder.emit(
            EventType.CRITIC_COMPLETED,
            message=f"Critic {'approved' if critique.approved else 'rejected'} (score {critique.score}/100)",
            task_id=task.id,
            agent=AgentName.CRITIC,
            approved=critique.approved,
            score=critique.score,
            issues=critique.issues,
            required_changes=critique.required_changes,
            reasoning=critique.reasoning,
        )
        return critique

    # -- approvals ---------------------------------------------------------

    async def _clear_guardian(
        self, mission: Mission, recorder: MissionRecorder, crew: _Crew, task: Task
    ) -> RiskLevel:
        """Assess a task's risk and, if needed, block until a human decides.

        Returns:
            The risk ceiling this task's tool calls are allowed to reach.
        """
        verdict = await crew.guardian.assess(goal=mission.goal, task=task)
        task.guardian_verdict = verdict
        task.touch()
        recorder.emit(
            EventType.GUARDIAN_REVIEW,
            message=f"Guardian assessed {task.title} as {verdict.risk_level.value} risk",
            task_id=task.id,
            agent=AgentName.GUARDIAN,
            risk_level=verdict.risk_level.value,
            requires_human_approval=verdict.requires_human_approval,
            rationale=verdict.rationale,
            irreversible=verdict.irreversible,
            external_side_effects=verdict.external_side_effects,
        )

        if not verdict.requires_human_approval:
            return self._settings.auto_approve_max_risk

        await self._await_approval(mission, recorder, task, verdict)
        return verdict.risk_level

    async def _await_approval(
        self,
        mission: Mission,
        recorder: MissionRecorder,
        task: Task,
        verdict: GuardianVerdict,
    ) -> None:
        request = ApprovalRequest(
            mission_id=mission.id,
            task_id=task.id,
            action=task.title,
            risk_level=verdict.risk_level,
            rationale=verdict.rationale,
        )
        mission.approvals.append(request)
        future = self._approvals.open(request)

        task.status = TaskStatus.WAITING_FOR_APPROVAL
        task.touch()
        mission.status = MissionStatus.WAITING_FOR_APPROVAL
        mission.touch()
        recorder.emit(
            EventType.APPROVAL_REQUIRED,
            message=f"Human approval required for: {task.title}",
            task_id=task.id,
            agent=AgentName.GUARDIAN,
            approval_id=request.id,
            risk_level=verdict.risk_level.value,
            rationale=verdict.rationale,
        )

        try:
            approved = await asyncio.wait_for(future, timeout=self._settings.approval_timeout_seconds)
        except TimeoutError:
            self._approvals.expire(request.id)
            task.status = TaskStatus.FAILED
            _resume_mission(mission)
            recorder.emit(
                EventType.APPROVAL_TIMED_OUT,
                message=f"Approval timed out for: {task.title}",
                task_id=task.id,
                agent=AgentName.GUARDIAN,
                approval_id=request.id,
            )
            raise ApprovalTimeout(
                f"No decision within {self._settings.approval_timeout_seconds}s for {task.title!r}"
            ) from None

        _resume_mission(mission)
        if approved:
            recorder.emit(
                EventType.APPROVAL_GRANTED,
                message=f"Approval granted for: {task.title}",
                task_id=task.id,
                agent=AgentName.GUARDIAN,
                approval_id=request.id,
                decided_by=request.decided_by,
                note=request.note,
            )
            return

        recorder.emit(
            EventType.APPROVAL_REJECTED,
            message=f"Approval rejected for: {task.title}",
            task_id=task.id,
            agent=AgentName.GUARDIAN,
            approval_id=request.id,
            decided_by=request.decided_by,
            note=request.note,
        )
        raise ApprovalRejected(request.note or f"A human rejected: {task.title}")

    # -- completion --------------------------------------------------------

    async def _finalise(self, mission: Mission, recorder: MissionRecorder, commander: Commander) -> None:
        completed = [t for t in mission.tasks if t.status is TaskStatus.COMPLETED]
        failed = [t for t in mission.tasks if t.status is TaskStatus.FAILED]

        if not completed:
            mission.status = MissionStatus.FAILED
            mission.error = "No task completed successfully."
            mission.touch()
            recorder.emit(
                EventType.MISSION_FAILED,
                message="Mission failed: no task completed successfully",
                error=mission.error,
                failed_tasks=[t.title for t in failed],
            )
            return

        mission.final_result = await commander.synthesize(mission)
        mission.status = MissionStatus.COMPLETED
        mission.touch()
        recorder.emit(
            EventType.MISSION_COMPLETED,
            message="Mission completed",
            agent=AgentName.COMMANDER,
            completed_tasks=len(completed),
            failed_tasks=[t.title for t in failed],
            final_result=mission.final_result,
        )


class _Crew:
    """The agents working one mission."""

    __slots__ = ("commander", "specialists", "critic", "guardian")

    def __init__(
        self,
        commander: Commander,
        specialists: SpecialistRunner,
        critic: Critic,
        guardian: Guardian,
    ) -> None:
        self.commander = commander
        self.specialists = specialists
        self.critic = critic
        self.guardian = guardian


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------


def _ready_tasks(mission: Mission) -> list[Task]:
    """Pending tasks whose dependencies have all completed."""
    completed = {t.id for t in mission.tasks if t.status is TaskStatus.COMPLETED}
    return [
        task
        for task in mission.tasks
        if task.status is TaskStatus.PENDING and set(task.dependencies) <= completed
    ]


def _mark_unreachable(mission: Mission, recorder: MissionRecorder) -> None:
    """Fail tasks left pending because an upstream dependency never completed."""
    completed = {t.id for t in mission.tasks if t.status is TaskStatus.COMPLETED}
    for task in mission.tasks:
        if task.status is not TaskStatus.PENDING:
            continue
        blockers = [dep for dep in task.dependencies if dep not in completed]
        titles = [mission.task(dep).title if mission.task(dep) else dep for dep in blockers]
        _fail_task(recorder, task, f"Blocked by unfinished dependencies: {', '.join(titles)}")


def _upstream_context(mission: Mission, task: Task) -> str:
    """Results of the tasks this one depends on, formatted for the prompt."""
    sections: list[str] = []
    for dep_id in task.dependencies:
        dep = mission.task(dep_id)
        if dep is None or not dep.result:
            continue
        sections.append(f"### {dep.title} (by {dep.assigned_agent.value})\n{dep.result}")
    return "\n\n".join(sections)


def _complete_task(
    mission: Mission, recorder: MissionRecorder, task: Task, *, degraded: bool = False
) -> None:
    task.status = TaskStatus.COMPLETED
    task.touch()
    if task.result:
        mission.results[task.key] = task.result
    recorder.emit(
        EventType.TASK_COMPLETED,
        message=f"Task completed: {task.title}" + (" (accepted with open critique)" if degraded else ""),
        task_id=task.id,
        agent=task.assigned_agent,
        degraded=degraded,
        score=task.critique.score if task.critique else None,
        retry_count=task.retry_count,
    )


def _fail_task(recorder: MissionRecorder, task: Task, reason: str) -> None:
    task.status = TaskStatus.FAILED
    task.error = reason
    task.touch()
    recorder.emit(
        EventType.TASK_FAILED,
        message=f"Task failed: {task.title} - {reason}",
        task_id=task.id,
        agent=task.assigned_agent,
        error=reason,
    )


def _resume_mission(mission: Mission) -> None:
    """Return the mission to RUNNING once no task is still awaiting approval.

    Concurrent tasks can each be blocked on their own approval, so the mission
    only resumes when the last of them has been decided.
    """
    if not any(task.status is TaskStatus.WAITING_FOR_APPROVAL for task in mission.tasks):
        mission.status = MissionStatus.RUNNING
    mission.touch()
