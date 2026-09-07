"""The reference mission script used across tests.

It encodes the hackathon's first end-to-end scenario: a competitive brief, with a
Critic rejection and revision on the Creator's work, and a Guardian-mandated
human approval before the brief is written.
"""

from __future__ import annotations

from hion.domain.enums import AgentName, RiskLevel
from hion.domain.models import Critique, GuardianVerdict, MissionPlan, PlannedTask
from tests.support.scripted_model import ScriptedTool

GOAL = (
    "Research the top competitors in the AI meeting assistant market and "
    "prepare a concise competitive brief."
)

PLAN = MissionPlan(
    objective="Produce a concise, sourced competitive brief on the AI meeting assistant market.",
    success_criteria=[
        "At least four named competitors with sourced positioning",
        "A clear recommendation backed by the research",
        "Under two pages",
    ],
    tasks=[
        PlannedTask(
            key="research_competitors",
            title="Research AI meeting assistant competitors",
            description="Identify the leading products, their positioning, pricing and differentiators.",
            assigned_agent=AgentName.RESEARCH,
            depends_on=[],
            acceptance_criteria=["At least four competitors", "A source URL for every claim"],
        ),
        PlannedTask(
            key="analyse_landscape",
            title="Analyse the competitive landscape",
            description="Compare the competitors, identify gaps and risks, and recommend a position.",
            assigned_agent=AgentName.ANALYST,
            depends_on=["research_competitors"],
            acceptance_criteria=["Comparison across consistent dimensions", "An explicit recommendation"],
        ),
        PlannedTask(
            key="write_brief",
            title="Write the competitive brief",
            description="Write the final one-to-two page competitive brief for the leadership team.",
            assigned_agent=AgentName.CREATOR,
            depends_on=["analyse_landscape"],
            acceptance_criteria=["Under two pages", "Every claim traceable to the research"],
        ),
    ],
)

RESEARCH_NOTES = (
    "Four competitors identified, each with a source URL: Otter.ai, Fireflies.ai, "
    "Fathom and Granola. Positioning and pricing captured in the competitors dataset."
)
ANALYSIS = (
    "The market splits between transcription-first incumbents and workflow-native "
    "newcomers. The unserved gap is post-meeting execution. Recommendation: enter on "
    "workflow integration, not transcription accuracy."
)
DRAFT_BRIEF = "Competitive brief, first draft. Otter leads on distribution."
FINAL_BRIEF = (
    "# AI Meeting Assistant Competitive Brief\n\n"
    "Recommendation: enter on post-meeting execution, not transcription accuracy.\n\n"
    "Otter.ai, Fireflies.ai, Fathom and Granola are compared on pricing, distribution "
    "and workflow depth, each with a cited source."
)

RESEARCH_DATASET = ScriptedTool(
    name="save_dataset",
    input={
        "name": "competitors",
        "rows": [
            {"name": "Otter.ai", "positioning": "transcription-first", "source": "https://otter.ai"},
            {"name": "Fireflies.ai", "positioning": "CRM integration", "source": "https://fireflies.ai"},
            {"name": "Fathom", "positioning": "free tier growth", "source": "https://fathom.video"},
            {"name": "Granola", "positioning": "notes-native", "source": "https://granola.ai"},
        ],
    },
)

#: The Creator reaches for a HIGH-risk tool it has not been approved for.
ATTEMPT_PUBLISH = ScriptedTool(
    name="publish_external",
    input={"channel": "stakeholders", "subject": "Competitive brief", "body": DRAFT_BRIEF},
)

WRITE_BRIEF_FILE = ScriptedTool(name="write_file", input={"path": "brief.md", "content": DRAFT_BRIEF})
UPDATE_BRIEF_FILE = ScriptedTool(name="update_file", input={"path": "brief.md", "content": FINAL_BRIEF})

APPROVE = Critique(
    approved=True, score=91, issues=[], required_changes=[], reasoning="Meets every criterion."
)
REJECT_DRAFT = Critique(
    approved=False,
    score=54,
    issues=["Only one competitor is named", "No sources cited", "No recommendation"],
    required_changes=[
        "Name all four researched competitors",
        "Cite a source URL for each claim",
        "State the recommendation up front",
    ],
    reasoning="The draft does not meet the acceptance criteria.",
)

LOW_RISK = GuardianVerdict(
    risk_level=RiskLevel.LOW,
    requires_human_approval=False,
    rationale="Read-only research inside the mission workspace.",
)
MEDIUM_RISK_NEEDS_APPROVAL = GuardianVerdict(
    risk_level=RiskLevel.MEDIUM,
    requires_human_approval=True,
    rationale="Produces the leadership-facing deliverable; a human should sign off before it is written.",
)


def reference_script() -> dict[str, list]:
    """The full model script for the reference mission."""
    return {
        "commander": [PLAN, FINAL_BRIEF],
        "guardian": [LOW_RISK, LOW_RISK, MEDIUM_RISK_NEEDS_APPROVAL],
        "research": [RESEARCH_DATASET, RESEARCH_NOTES],
        "analyst": [ANALYSIS],
        "creator": [ATTEMPT_PUBLISH, WRITE_BRIEF_FILE, DRAFT_BRIEF, UPDATE_BRIEF_FILE, FINAL_BRIEF],
        "critic": [APPROVE, APPROVE, REJECT_DRAFT, APPROVE],
    }
