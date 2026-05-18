from dataclasses import dataclass, field
from textual.app import App
from backend.core.models import Understanding, SkepticCritique, ConfidenceProfile, TechPlan, BuildArtifact, TestReport
from backend.cli.screens import (
    GoalScreen, UnderstandingScreen, DesignScreen,
    BuildScreen, TestScreen, CommitScreen, DoneScreen,
)


@dataclass
class BrogrammerState:
    goal: str = ""
    understanding: Understanding | None = None
    critique: SkepticCritique | None = None
    confidence: ConfidenceProfile | None = None
    plan: TechPlan | None = None
    build: BuildArtifact | None = None
    test_report: TestReport | None = None
    commit_sha: str | None = None


class BrogrammerApp(App):
    SCREENS = {
        "goal": GoalScreen,
        "understanding": UnderstandingScreen,
        "design": DesignScreen,
        "build": BuildScreen,
        "test": TestScreen,
        "commit": CommitScreen,
        "done": DoneScreen,
    }

    def __init__(self, specialist, skeptic, planner, builder, qa, sandbox, db):
        super().__init__()
        self.specialist = specialist
        self.skeptic = skeptic
        self.planner = planner
        self.builder = builder
        self.qa = qa
        self.sandbox = sandbox
        self.db = db
        self.state = BrogrammerState()

    def on_mount(self):
        self.push_screen("goal")
