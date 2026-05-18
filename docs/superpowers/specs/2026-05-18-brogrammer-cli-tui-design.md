# Brogrammer CLI/TUI — Design Spec

## Overview

A terminal-based interactive wizard that mirrors the existing 7-step web UI. Users run `brogrammer` from the terminal, type a goal, and walk through the full gate flow (understanding → design → build → test → commit) without needing the FastAPI server or a browser.

Built with **Textual** — a modern Python TUI framework with built-in widgets for panels, buttons, inputs, rich scrolling, and async support.

## Architecture

New `backend/cli/` package imports agents directly from the existing `backend.agents.*` modules. No HTTP server required. Reuses existing data models, database, and Docker sandbox unchanged.

```
backend/
  cli/
    __init__.py
    app.py          # Textual App, screen navigation, agent wiring
    screens.py      # One file, all gate screens
    widgets.py      # Shared Rich/Textual widget fragments
```

## Entry Point

`pyproject.toml` gets a new `[project.scripts]` entry:

```toml
[project.scripts]
brogrammer = "backend.cli:run"
```

`pip install -e .` makes `brogrammer` available as a terminal command. The `run()` function instantiates agents and launches the Textual app.

## State Management

A single `BrogrammerState` dataclass owned by the App:

```python
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
```

Each screen reads/writes through this shared state. Agent calls happen on screen actions, update state, then push the next screen.

## Screen Flow

```
GoalScreen → UnderstandingScreen → DesignScreen → BuildScreen → TestScreen → CommitScreen → DoneScreen
```

Strictly forward — no back navigation, matching the web UI.

### GoalScreen
- `Input` widget for goal text
- "Start" `Button` triggers SpecialistAgent → SkepticAgent → confidence compute
- On completion, pushes UnderstandingScreen

### UnderstandingScreen
- Three `RichLog` panels: assumptions (color-coded open/validated/invalidated), unknowns, mandatory categories
- `RichLog` for skeptic critique: failure scenarios + questions
- Inline "Resolve" toggle for each question (expands an `Input` to type resolution)
- `Static` widget for confidence badge (color-coded score, fragility warning)
- "Proceed to Design Gate" button → pushes DesignScreen

### DesignScreen
- `RichLog` for tech plan: file tree, tech stack tags, API routes
- "Approve Plan" / "Retry" buttons
- Approve → pushes BuildScreen; Retry → re-runs PlannerAgent

### BuildScreen
- `RichLog` for build artifacts: files created/modified
- Second `RichLog` for Docker build logs (dark terminal style)
- "Proceed to Test Gate" → pushes TestScreen

### TestScreen
- `RichLog` for test report: passed/failed/skipped counts, detail list
- "Approve Build" / "Retry Build" buttons
- Approve → pushes CommitScreen; Retry → re-runs BuilderAgent + QAAgent

### CommitScreen
- `Input` for commit message
- "Commit" button → runs git commit via existing commit logic
- On success → pushes DoneScreen

### DoneScreen
- Displays commit SHA
- "Start New" button → pops back to GoalScreen

## Progress Bar

A `Header`-style widget at the top shows 7 circles/steps with the current step highlighted (goal → understanding → design → build → test → commit → done). Rendered as a `RichLog` or custom `Static` with colored markers.

## Dependencies

New dependency added to `pyproject.toml`:

```toml
dependencies = [
    ...existing...,
    "textual>=1.0.0",
]
```

Textual includes Rich, so no separate Rich dependency needed.

## Files to Create

| File | Purpose |
|------|---------|
| `backend/cli/__init__.py` | Package init, exports `run()` |
| `backend/cli/app.py` | `BrogrammerApp` Textual App, `BrogrammerState` dataclass, agent wiring |
| `backend/cli/screens.py` | All 7 screen classes |
| `backend/cli/widgets.py` | Shared widgets (progress bar, confidence badge, etc.) |

## Files to Modify

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `textual` dependency + `[project.scripts]` entry |
| `backend/main.py` | None — CLI is independent |

## Testing

- Existing agent unit tests cover all agent logic — no new tests needed for the backend
- CLI screens can be smoke-tested manually by running `brogrammer`
- Textual has its own testing utilities (`textual.testing`) for optional automated screen tests

## Non-Goals

- No WebSocket or real-time streaming (matching current sync design)
- No back navigation (matching web UI)
- No separate CLI binary — runs via installed package
