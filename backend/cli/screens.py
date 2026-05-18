from textual.app import ComposeResult, Worker, WorkerState
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static, Input, RichLog
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import work

from backend.cli.widgets import ProgressBar, ConfidenceBadge, GATE_NAMES
from backend.core.confidence import compute_confidence


class GoalScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ProgressBar()
        yield Static("\n[bold]What do you want to build?[/]\n", id="prompt")
        yield Input(placeholder="e.g., Build a habit tracker CLI", id="goal-input")
        yield Button("Start", id="start-btn", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-btn":
            goal = self.query_one("#goal-input", Input).value.strip()
            if goal:
                self.app.state.goal = goal
                self.run_pipeline()

    @work(exclusive=True)
    async def run_pipeline(self) -> None:
        self.query_one("#start-btn", Button).disabled = True
        self.query_one("#start-btn", Button).label = "Running..."
        self.query_one(ProgressBar).current_step = 1

        understanding, fragile = await self.app.specialist.generate_with_fragility_check(
            self.app.state.goal
        )
        self.app.state.understanding = understanding

        critique = await self.app.skeptic.generate_critique(understanding)
        self.app.state.critique = critique

        open_unknowns = sum(1 for u in understanding.unknowns if u.resolution is None)
        total_unknowns = len(understanding.unknowns)
        validated_count = sum(1 for a in understanding.assumptions if a.status == "validated")
        total_assumptions = len(understanding.assumptions)
        confidence = compute_confidence(
            open_unknowns, total_unknowns, validated_count, total_assumptions,
            understanding.mandatory_categories, fragility_flag=fragile,
        )
        self.app.state.confidence = confidence

        self.app.push_screen("understanding")


class UnderstandingScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ProgressBar()
        with ScrollableContainer():
            yield RichLog(id="assumptions", highlight=True, markup=True)
            yield RichLog(id="unknowns", highlight=True, markup=True)
            yield RichLog(id="categories", highlight=True, markup=True)
            yield RichLog(id="critique", highlight=True, markup=True)
            yield ConfidenceBadge(id="confidence")
            yield Input(placeholder="Resolve a question (optional)...", id="resolution-input")
            yield Button("Resolve", id="resolve-btn")
            yield Button("Proceed to Design Gate", id="proceed-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_panels()

    def _populate_panels(self) -> None:
        s = self.app.state
        u = s.understanding
        assumptions_log = self.query_one("#assumptions", RichLog)
        assumptions_log.clear()
        assumptions_log.write("[bold]Assumptions:[/]\n")
        for a in u.assumptions:
            tag = {"open": "[yellow]○ open[/]", "validated": "[green]✓ validated[/]", "invalidated": "[red]✗ invalidated[/]"}
            status = tag.get(a.status, "[dim]○[/]")
            assumptions_log.write(f"  {status} {a.statement}")

        unknowns_log = self.query_one("#unknowns", RichLog)
        unknowns_log.clear()
        unknowns_log.write("[bold]Unknowns:[/]\n")
        for uk in u.unknowns:
            unknowns_log.write(f"  [?] {uk.question}")

        cats = u.mandatory_categories
        cats_log = self.query_one("#categories", RichLog)
        cats_log.clear()
        cats_log.write("[bold]Mandatory Categories:[/]\n")
        for field in ["accessibility", "performance", "security", "state_management", "persistence"]:
            items = getattr(cats, field, [])
            joined = "; ".join(items) if items else "[dim]None[/]"
            cats_log.write(f"  [bold]{field.replace('_', ' ').title()}:[/] {joined}")

        critique_log = self.query_one("#critique", RichLog)
        critique_log.clear()
        critique_log.write("[bold]Skeptic Critique:[/]\n")
        for sc in s.critique.scenarios:
            critique_log.write(f"  [red]⚠[/] {sc}")
        for q in s.critique.questions:
            critique_log.write(f"  [?] {q}")

        self.query_one("#confidence", ConfidenceBadge).update_score(
            s.confidence.score, s.confidence.fragility_flag
        )
        self.query_one(ProgressBar).current_step = 2

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "proceed-btn":
            self.app.push_screen("design")
        elif event.button.id == "resolve-btn":
            resolution = self.query_one("#resolution-input", Input).value.strip()
            if resolution and self.app.state.critique.questions:
                self.app.state.critique.questions[-1] = (
                    f"{self.app.state.critique.questions[-1]} -> [green]Resolved: {resolution}[/]"
                )
                self.query_one("#resolution-input", Input).value = ""
                self._populate_panels()


class DesignScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ProgressBar()
        with ScrollableContainer():
            yield RichLog(id="plan-output", highlight=True, markup=True)
            yield Button("Approve Plan", id="approve-btn", variant="primary")
            yield Button("Retry", id="retry-btn")
        yield Footer()

    def on_mount(self) -> None:
        self._generate_plan()

    @work(exclusive=True)
    async def _generate_plan(self) -> None:
        s = self.app.state
        plan = await self.app.planner.generate_plan(s.understanding)
        s.plan = plan

        log = self.query_one("#plan-output", RichLog)
        log.clear()
        log.write(f"[bold]Tech Stack:[/] {', '.join(plan.tech_stack)}\n")
        log.write(f"\n[bold]Files:[/]\n")
        for f in plan.file_tree:
            log.write(f"  [blue]{f.path}[/] - {f.purpose} ({f.content_type})")
        log.write(f"\n[bold]API Routes:[/]\n")
        for r in plan.api_routes:
            log.write(f"  [green]{r.method}[/] {r.path} - {r.description}")
        self.query_one(ProgressBar).current_step = 3

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve-btn":
            self.app.push_screen("build")
        elif event.button.id == "retry-btn":
            self.query_one("#plan-output", RichLog).clear()
            self._generate_plan()


class BuildScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ProgressBar()
        with ScrollableContainer():
            yield RichLog(id="build-output", highlight=True, markup=True)
            yield RichLog(id="docker-logs", highlight=True, markup=True)
            yield Button("Proceed to Test Gate", id="proceed-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._run_build()

    @work(exclusive=True)
    async def _run_build(self) -> None:
        s = self.app.state
        build = await self.app.builder.build(s.plan)
        s.build = build

        log = self.query_one("#build-output", RichLog)
        log.clear()
        log.write("[bold]Files Created:[/]\n")
        for f in build.files_created:
            log.write(f"  [green]+[/] {f}")
        log.write("[bold]Files Modified:[/]\n")
        for f in build.files_modified:
            log.write(f"  [yellow]~[/] {f}")

        docker_log = self.query_one("#docker-logs", RichLog)
        docker_log.clear()
        docker_log.write("[bold]Docker Build Logs:[/]\n")
        for line in build.docker_logs:
            docker_log.write(f"  {line}")
        self.query_one(ProgressBar).current_step = 4

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "proceed-btn":
            self.app.push_screen("test")


class TestScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ProgressBar()
        with ScrollableContainer():
            yield RichLog(id="test-output", highlight=True, markup=True)
            yield Button("Approve Build", id="approve-btn", variant="primary")
            yield Button("Retry Build", id="retry-btn")
        yield Footer()

    def on_mount(self) -> None:
        self._run_tests()

    @work(exclusive=True)
    async def _run_tests(self) -> None:
        s = self.app.state
        assert s.plan is not None
        test_plan = await self.app.qa.generate_test_plan(s.plan)
        report = await self.app.qa.run_tests(build_id="", test_path="tests")
        s.test_report = report

        log = self.query_one("#test-output", RichLog)
        log.clear()
        log.write("[bold]Test Results:[/]\n")
        log.write(f"  [green]Passed:[/] {report.passed}")
        log.write(f"  [red]Failed:[/] {report.failed}")
        log.write(f"  [yellow]Skipped:[/] {report.skipped}")
        if report.coverage_pct is not None:
            log.write(f"  Coverage: {report.coverage_pct:.1f}%")
        log.write("\n[bold]Details:[/]\n")
        for d in report.details:
            status_icon = {"passed": "[green]✓[/]", "failed": "[red]✗[/]", "skipped": "[yellow]○[/]"}
            icon = status_icon.get(d.status, "[dim]?[/]")
            log.write(f"  {icon} {d.test_name}")
            if d.error_message:
                log.write(f"     [dim]{d.error_message}[/]")
        self.query_one(ProgressBar).current_step = 5

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve-btn":
            self.app.push_screen("commit")
        elif event.button.id == "retry-btn":
            self.query_one("#test-output", RichLog).clear()
            self._run_tests()


class CommitScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ProgressBar()
        yield Static("\n[bold]Ready to commit to Git?[/]\n")
        yield Input(placeholder="Commit message...", id="commit-msg")
        yield Button("Commit Build", id="commit-btn", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "commit-btn":
            msg = self.query_one("#commit-msg", Input).value.strip()
            if msg:
                self._do_commit(msg)

    @work(exclusive=True)
    async def _do_commit(self, message: str) -> None:
        s = self.app.state
        from backend.cli import do_git_commit
        sha = do_git_commit(message)
        s.commit_sha = sha
        self.query_one(ProgressBar).current_step = 6
        self.app.push_screen("done")


class DoneScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ProgressBar()
        yield Static(id="done-message")
        yield Button("Start New", id="restart-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        sha = self.app.state.commit_sha
        self.query_one("#done-message", Static).update(
            f"\n[bold green]Phase Complete![/]\n\nCommitted at: [bold]{sha}[/]"
        )
        self.query_one(ProgressBar).current_step = 7

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "restart-btn":
            self.app.state = self.app.state.__class__()
            self.app.push_screen("goal")
