from textual.app import ComposeResult
from textual.widgets import Static
from textual.widget import Widget
from textual.reactive import reactive


GATE_NAMES = ["Goal", "Understanding", "Design", "Build", "Test", "Commit", "Done"]


class ProgressBar(Widget):
    current_step = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static(id="progress-text")

    def watch_current_step(self, step: int) -> None:
        parts = []
        for i, name in enumerate(GATE_NAMES):
            if i < step:
                parts.append(f"[green]●[/] {name}")
            elif i == step:
                parts.append(f"[yellow]●[/] [bold yellow]{name}[/]")
            else:
                parts.append(f"[dim]○[/] {name}")
        self.query_one("#progress-text").update("  " + "  →  ".join(parts))


class ConfidenceBadge(Static):
    def update_score(self, score: float, fragility: bool):
        color = "red" if score < 70 else ("yellow" if score < 90 else "green")
        frag = " [red bold]FRAGILE[/]" if fragility else ""
        self.update(f"[bold {color}]Confidence: {score:.1f}%[/]{frag}")
