# Brogrammer Phase 0: Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Runnable dual-agent text loop (Specialist → Skeptic) with mechanical confidence scoring, SQLite audit log, and a bare-bones React gate UI. All LLM calls go through local Ollama.

**Architecture:** FastAPI backend with Pydantic v2 data contracts, SQLite append-only audit store, Specialist/Skeptic agents calling Ollama. React (Vite + TypeScript) frontend with diff view, color-coded tags, and resolution toggles.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite, Ollama (Python client), React 18, Vite, TypeScript.

---

## File Structure

```
brogrammer/
├── backend/
│   ├── pyproject.toml
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py          # Pydantic v2: Understanding, Assumption, Unknown, MandatoryCategories, SkepticCritique, ConfidenceProfile
│   │   └── confidence.py      # Mechanical confidence formula
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── specialist.py      # Generates Understanding via Ollama (prompt → JSON)
│   │   └── skeptic.py         # Generates SkepticCritique via Ollama
│   └── orchestrator/
│       ├── __init__.py
│       ├── database.py        # SQLite connection setup, table creation
│       ├── audit.py           # Append-only event store
│       └── gates.py           # FastAPI router with /api/run-loop, /api/resolve-critique, /api/audit/events
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── App.css
│       ├── api.ts
│       └── components/
│           ├── UnderstandingView.tsx
│           ├── CritiquePanel.tsx
│           └── ConfidenceBadge.tsx
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_confidence.py
│   ├── test_audit.py
│   ├── test_agents.py
│   └── test_integration.py
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/core/__init__.py`
- Create: `backend/agents/__init__.py`
- Create: `backend/orchestrator/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "brogrammer"
version = "0.1.0"
description = "Human-centric AI engineering team"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "ollama>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
    "aiosqlite>=0.20.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

Write to `backend/pyproject.toml`.

- [ ] **Step 2: Create empty __init__.py files**

Contents of each `__init__.py`:
```python
```

Create in:
- `backend/core/__init__.py`
- `backend/agents/__init__.py`
- `backend/orchestrator/__init__.py`
- `tests/__init__.py`

- [ ] **Step 3: Create test conftest.py**

```python
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
```

Write to `tests/conftest.py`.

- [ ] **Step 4: Verify project loads**

Run:
```bash
cd backend && python -c "import fastapi, pydantic, ollama; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/ tests/
git commit -m "chore: scaffold Phase 0 project structure"
```

---

### Task 2: Core Data Models

**Files:**
- Create: `backend/core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone
from backend.core.models import (
    Assumption,
    Unknown,
    MandatoryCategories,
    Understanding,
    SkepticCritique,
    ConfidenceProfile,
)


def test_assumption_defaults():
    a = Assumption(statement="Users want visual feedback")
    assert a.id is not None
    assert a.statement == "Users want visual feedback"
    assert a.status == "open"
    assert a.validated_by is None


def test_assumption_validated_status():
    a = Assumption(status="validated", statement="DB is PostgreSQL", validated_by="human")
    assert a.status == "validated"
    assert a.validated_by == "human"


def test_unknown_defaults():
    u = Unknown(question="What DB to use?")
    assert u.id is not None
    assert u.question == "What DB to use?"
    assert u.resolution is None
    assert u.resolved_at is None


def test_unknown_resolved():
    now = datetime.now(timezone.utc)
    u = Unknown(question="What DB?", resolution="SQLite", resolved_at=now)
    assert u.resolution == "SQLite"
    assert u.resolved_at == now


def test_mandatory_categories_defaults():
    mc = MandatoryCategories()
    assert mc.accessibility == []
    assert mc.performance == []
    assert mc.security == []
    assert mc.state_management == []
    assert mc.persistence == []


def test_understanding_full():
    mc = MandatoryCategories(performance=["latency < 200ms"])
    u = Understanding(
        goal="Build a habit tracker",
        assumptions=[Assumption(statement="Users want streaks")],
        unknowns=[Unknown(question="What framework?")],
        mandatory_categories=mc,
    )
    assert u.goal == "Build a habit tracker"
    assert len(u.assumptions) == 1
    assert len(u.unknowns) == 1
    assert u.mandatory_categories.performance == ["latency < 200ms"]


def test_skeptic_critique_defaults():
    sc = SkepticCritique(understanding_id="uid-1")
    assert sc.critique_id is not None
    assert sc.understanding_id == "uid-1"
    assert sc.scenarios == []
    assert sc.questions == []
    assert sc.tool_evidence == []


def test_confidence_profile_defaults():
    cp = ConfidenceProfile(
        score=0.75,
        open_unknowns=2,
        total_unknowns=8,
        validation_ratio=0.5,
    )
    assert cp.score == 0.75
    assert cp.open_unknowns == 2
    assert cp.total_unknowns == 8
    assert cp.validation_ratio == 0.5
    assert cp.fragility_flag is False


def test_confidence_profile_fragile():
    cp = ConfidenceProfile(
        score=0.3,
        open_unknowns=5,
        total_unknowns=10,
        validation_ratio=0.2,
        fragility_flag=True,
    )
    assert cp.fragility_flag is True
```

Write to `tests/test_models.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && python -m pytest ../tests/test_models.py -v
```
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


class Assumption(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    statement: str
    status: str = "open"  # "validated" | "open" | "invalidated"
    validated_by: str | None = None


class Unknown(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    question: str
    resolution: str | None = None
    resolved_at: datetime | None = None


class MandatoryCategories(BaseModel):
    accessibility: list[str] = []
    performance: list[str] = []
    security: list[str] = []
    state_management: list[str] = []
    persistence: list[str] = []


class Understanding(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    goal: str
    assumptions: list[Assumption] = []
    unknowns: list[Unknown] = []
    mandatory_categories: MandatoryCategories = MandatoryCategories()


class SkepticCritique(BaseModel):
    critique_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    understanding_id: str
    scenarios: list[str] = []
    questions: list[str] = []
    tool_evidence: list[str] = []


class ConfidenceProfile(BaseModel):
    score: float
    open_unknowns: int
    total_unknowns: int
    validation_ratio: float
    fragility_flag: bool = False
```

Write to `backend/core/models.py`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd backend && python -m pytest ../tests/test_models.py -v
```
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/models.py tests/test_models.py
git commit -m "feat: add core Pydantic v2 data models"
```

---

### Task 3: Confidence Formula

**Files:**
- Create: `backend/core/confidence.py`
- Create: `tests/test_confidence.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from backend.core.confidence import compute_confidence
from backend.core.models import (
    Assumption,
    MandatoryCategories,
    ConfidenceProfile,
)


def test_confidence_basic():
    """Base formula: score = 1 - open/total"""
    profile = compute_confidence(
        open_unknowns=2,
        total_unknowns=10,
        validated_count=5,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(
            performance=["latency < 200ms"],
            security=["auth required"],
        ),
        fragility_flag=False,
    )
    assert profile.score == pytest.approx(0.8)
    assert profile.open_unknowns == 2
    assert profile.total_unknowns == 10
    assert profile.validation_ratio == 1.0
    assert profile.fragility_flag is False


def test_confidence_zero_total_unknowns():
    """If no unknowns identified, score defaults to 0.5."""
    profile = compute_confidence(
        open_unknowns=0,
        total_unknowns=0,
        validated_count=3,
        total_assumptions=3,
        mandatory_categories=MandatoryCategories(performance=["x"]),
        fragility_flag=False,
    )
    assert profile.score == 0.5


def test_confidence_capped_by_validation_ratio():
    """Score cannot exceed validation_ratio."""
    profile = compute_confidence(
        open_unknowns=1,
        total_unknowns=10,
        validated_count=1,       # only 1 of 5 validated
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(performance=["x"]),
        fragility_flag=False,
    )
    # base = 0.9, cap = 0.2, so score = 0.2
    assert profile.score == pytest.approx(0.2)


def test_confidence_mandatory_category_penalty():
    """Empty mandatory category halves the score."""
    profile = compute_confidence(
        open_unknowns=2,
        total_unknowns=10,
        validated_count=5,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(performance=["x"]),
        # accessibility empty, everything else empty
        fragility_flag=False,
    )
    # base = 0.8, cap = 1.0, penalty = 0.5 -> 0.4
    assert profile.score == pytest.approx(0.4)


def test_confidence_multiple_empty_categories_single_penalty():
    """Multiple empty categories still apply penalty only once."""
    profile = compute_confidence(
        open_unknowns=2,
        total_unknowns=10,
        validated_count=5,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(),  # all empty
        fragility_flag=False,
    )
    # base = 0.8, cap = 1.0, penalty = 0.5 -> 0.4
    assert profile.score == pytest.approx(0.4)


def test_confidence_fragility_flag_passed_through():
    profile = compute_confidence(
        open_unknowns=2,
        total_unknowns=10,
        validated_count=5,
        total_assumptions=5,
        mandatory_categories=MandatoryCategories(performance=["x"]),
        fragility_flag=True,
    )
    assert profile.fragility_flag is True


def test_confidence_clamp_negative():
    """Score is clamped to minimum 0."""
    profile = compute_confidence(
        open_unknowns=10,
        total_unknowns=10,
        validated_count=0,
        total_assumptions=1,
        mandatory_categories=MandatoryCategories(performance=["x"]),
        fragility_flag=False,
    )
    assert profile.score >= 0.0
```

Write to `tests/test_confidence.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && python -m pytest ../tests/test_confidence.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

```python
from backend.core.models import ConfidenceProfile, MandatoryCategories


_MANDATORY_FIELDS = [
    "accessibility",
    "performance",
    "security",
    "state_management",
    "persistence",
]


def _any_category_empty(mc: MandatoryCategories) -> bool:
    for field in _MANDATORY_FIELDS:
        if not getattr(mc, field):
            return True
    return False


def compute_confidence(
    open_unknowns: int,
    total_unknowns: int,
    validated_count: int,
    total_assumptions: int,
    mandatory_categories: MandatoryCategories,
    fragility_flag: bool = False,
) -> ConfidenceProfile:
    if total_unknowns == 0:
        base_score = 0.5
    else:
        base_score = max(0.0, 1.0 - (open_unknowns / total_unknowns))

    validation_ratio = validated_count / total_assumptions if total_assumptions > 0 else 0.0

    score = min(base_score, validation_ratio)

    if _any_category_empty(mandatory_categories):
        score *= 0.5

    return ConfidenceProfile(
        score=round(score, 4),
        open_unknowns=open_unknowns,
        total_unknowns=total_unknowns,
        validation_ratio=validation_ratio,
        fragility_flag=fragility_flag,
    )
```

Write to `backend/core/confidence.py`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd backend && python -m pytest ../tests/test_confidence.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/confidence.py tests/test_confidence.py
git commit -m "feat: implement mechanical confidence formula"
```

---

### Task 4: SQLite Database & Audit Log

**Files:**
- Create: `backend/orchestrator/database.py`
- Create: `backend/orchestrator/audit.py`
- Create: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import pytest
from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event, get_events


@pytest.fixture
async def db():
    db = await get_db(":memory:")
    await init_db(db)
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_append_and_read_events(db):
    await append_event(
        db,
        event_type="critique_created",
        understanding_id="u1",
        critique_id="c1",
        payload={"scenarios": ["failure"]},
    )
    events = await get_events(db, limit=10)
    assert len(events) == 1
    assert events[0]["event_type"] == "critique_created"
    assert events[0]["understanding_id"] == "u1"
    assert events[0]["critique_id"] == "c1"
    data = json.loads(events[0]["payload"])
    assert data["scenarios"] == ["failure"]


@pytest.mark.asyncio
async def test_events_ordered_by_time(db):
    await append_event(db, "understanding_generated", "u1", None, {"a": 1})
    await append_event(db, "critique_created", "u1", "c1", {"b": 2})
    await append_event(db, "human_resolution", "u1", "c1", {"c": 3})
    events = await get_events(db, limit=10)
    assert len(events) == 3
    types = [e["event_type"] for e in events]
    assert types == ["understanding_generated", "critique_created", "human_resolution"]


@pytest.mark.asyncio
async def test_get_events_limit(db):
    for i in range(5):
        await append_event(db, "test_event", None, None, {"i": i})
    events = await get_events(db, limit=2)
    assert len(events) == 2


@pytest.mark.asyncio
async def test_event_id_is_unique(db):
    ids = set()
    for _ in range(20):
        await append_event(db, "test", None, None, {})
    events = await get_events(db, limit=100)
    for e in events:
        ids.add(e["id"])
    assert len(ids) == 20
```

Write to `tests/test_audit.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && python -m pytest ../tests/test_audit.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write database.py**

```python
import aiosqlite

DB_PATH = "brogrammer.db"


async def get_db(path: str | None = None) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path or DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            understanding_id TEXT,
            critique_id TEXT,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.commit()
```

Write to `backend/orchestrator/database.py`.

- [ ] **Step 4: Write audit.py**

```python
import json
from datetime import datetime, timezone
from uuid import uuid4

import aiosqlite


async def append_event(
    db: aiosqlite.Connection,
    event_type: str,
    understanding_id: str | None,
    critique_id: str | None,
    payload: dict,
) -> str:
    event_id = uuid4().hex[:16]
    created_at = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO audit_events (id, event_type, understanding_id, critique_id, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (event_id, event_type, understanding_id, critique_id, json.dumps(payload), created_at),
    )
    await db.commit()
    return event_id


async def get_events(db: aiosqlite.Connection, limit: int = 50) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM audit_events ORDER BY created_at ASC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
```

Write to `backend/orchestrator/audit.py`.

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
cd backend && python -m pytest ../tests/test_audit.py -v
```
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/database.py backend/orchestrator/audit.py tests/test_audit.py
git commit -m "feat: implement SQLite audit log with append-only events"
```

---

### Task 5: Specialist Agent

**Files:**
- Create: `backend/agents/specialist.py`
- Create: `tests/test_agents.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from datetime import datetime, timezone
from backend.core.models import Understanding, MandatoryCategories


class FakeOllamaClient:
    """Returns a canned Understanding JSON."""
    def __init__(self, model: str = "llama3.2"):
        self.model = model

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        return {
            "message": {
                "content": (
                    '{"goal": "Build a habit tracker", '
                    '"assumptions": [{"statement": "Users want streaks", "status": "open"}], '
                    '"unknowns": [{"question": "What platform?"}], '
                    '"mandatory_categories": {"accessibility": [], "performance": ["fast"], '
                    '"security": [], "state_management": [], "persistence": []}}'
                )
            }
        }


@pytest.mark.asyncio
async def test_specialist_generates_understanding():
    from backend.agents.specialist import SpecialistAgent

    agent = SpecialistAgent(ollama_client=FakeOllamaClient())
    result = await agent.generate_understanding("Build a habit tracker")
    assert isinstance(result, Understanding)
    assert result.goal == "Build a habit tracker"
    assert len(result.assumptions) == 1
    assert result.assumptions[0].statement == "Users want streaks"
    assert len(result.unknowns) == 1
    assert result.unknowns[0].question == "What platform?"


class FragileFakeClient:
    """Returns different Understanding each call — triggers fragility."""
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        self.call_count += 1
        goals = {
            1: "Build a habit tracker",
            2: "Create a workout app",
            3: "Make a todo list",
        }
        return {
            "message": {
                "content": (
                    '{"goal": "' + goals.get(self.call_count, "Unknown") + '", '
                    '"assumptions": [{"statement": "assumption ' + str(self.call_count) + '", "status": "open"}], '
                    '"unknowns": [], '
                    '"mandatory_categories": {"accessibility": [], "performance": [], '
                    '"security": [], "state_management": [], "persistence": []}}'
                )
            }
        }


@pytest.mark.asyncio
async def test_specialist_fragility_detection():
    from backend.agents.specialist import SpecialistAgent

    agent = SpecialistAgent(ollama_client=FragileFakeClient())
    result, fragile = await agent.generate_with_fragility_check("Build a habit tracker")
    assert fragile is True


class StableFakeClient:
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        return {
            "message": {
                "content": (
                    '{"goal": "Build a habit tracker", '
                    '"assumptions": [{"statement": "Users want streaks", "status": "open"}], '
                    '"unknowns": [], '
                    '"mandatory_categories": {"accessibility": [], "performance": [], '
                    '"security": [], "state_management": [], "persistence": []}}'
                )
            }
        }


@pytest.mark.asyncio
async def test_specialist_no_fragility():
    from backend.agents.specialist import SpecialistAgent

    agent = SpecialistAgent(ollama_client=StableFakeClient())
    result, fragile = await agent.generate_with_fragility_check("Build a habit tracker")
    assert fragile is False
```

Write to `tests/test_agents.py`. Place these tests BEFORE the implementation, then mark them as the first step.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && python -m pytest ../tests/test_agents.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write specialist.py**

```python
from backend.core.models import Understanding


class OllamaClient:
    """Thin wrapper around the `ollama` Python package."""
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        import ollama
        client = ollama.AsyncClient(host=self.base_url)
        kwargs = {"model": self.model, "messages": messages, "options": {"temperature": temperature}}
        if format:
            kwargs["format"] = format
        response = await client.chat(**kwargs)
        return response


class SpecialistAgent:
    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.system_prompt = (
            "You are the SpecialistAgent. Given a user's goal, produce a structured Understanding document. "
            "Return ONLY valid JSON — no markdown, no explanation. "
            'Format: {"goal": "...", "assumptions": [{"statement": "...", "status": "open"}], '
            '"unknowns": [{"question": "..."}], '
            '"mandatory_categories": {"accessibility": [...], "performance": [...], '
            '"security": [...], "state_management": [...], "persistence": [...]}}'
        )

    async def generate_understanding(self, goal: str) -> Understanding:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Goal: {goal}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.0)
        raw = response["message"]["content"]
        return Understanding.model_validate_json(raw)

    async def _single_understanding(self, goal: str, temperature: float) -> set[str]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Goal: {goal}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=temperature)
        raw = response["message"]["content"]
        u = Understanding.model_validate_json(raw)
        return {a.statement for a in u.assumptions}

    async def generate_with_fragility_check(self, goal: str) -> tuple[Understanding, bool]:
        result = await self.generate_understanding(goal)

        sets = []
        for _ in range(3):
            s = await self._single_understanding(goal, temperature=0.7)
            sets.append(s)

        first_set = sets[0]
        fragile = any(s != first_set for s in sets[1:])
        return result, fragile
```

Write to `backend/agents/specialist.py`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd backend && python -m pytest ../tests/test_agents.py -v
```
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/specialist.py tests/test_agents.py
git commit -m "feat: implement SpecialistAgent with Ollama integration and fragility check"
```

---

### Task 6: Skeptic Agent

**Files:**
- Modify: `backend/agents/skeptic.py` (create)
- Modify: `tests/test_agents.py` (extend)

- [ ] **Step 1: Write the failing test** (append to test_agents.py)

```python
from backend.core.models import Understanding, MandatoryCategories, Assumption, Unknown


class SkepticFakeClient:
    async def chat(self, messages: list[dict], format: str = "", temperature: float = 0.0):
        return {
            "message": {
                "content": (
                    '{"scenarios": ["Fireworks library adds 6MB bloat"], '
                    '"questions": ["Should we use CSS animations instead?"], '
                    '"tool_evidence": ["npm view react-native-fireworks unpackedSize -> 6MB"]}'
                )
            }
        }


@pytest.mark.asyncio
async def test_skeptic_generates_critique():
    from backend.agents.skeptic import SkepticAgent

    agent = SkepticAgent(ollama_client=SkepticFakeClient())
    understanding = Understanding(
        goal="Build a habit tracker",
        assumptions=[Assumption(statement="Users want fireworks")],
        unknowns=[Unknown(question="What library?")],
        mandatory_categories=MandatoryCategories(),
    )
    critique = await agent.generate_critique(understanding)
    assert critique.understanding_id == understanding.id
    assert len(critique.scenarios) == 1
    assert "6MB" in critique.scenarios[0]
    assert len(critique.questions) == 1
    assert len(critique.tool_evidence) == 1
```

Add this test to `tests/test_agents.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && python -m pytest ../tests/test_agents.py::test_skeptic_generates_critique -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write skeptic.py**

```python
from backend.core.models import Understanding, SkepticCritique
from backend.agents.specialist import OllamaClient


class SkepticAgent:
    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama = ollama_client or OllamaClient()
        self.system_prompt = (
            "You are the SkepticAgent. Given an Understanding document, produce a critique. "
            "Return ONLY valid JSON — no markdown, no explanation. "
            'Format: {"scenarios": ["plausible failure scenario 1", "scenario 2"], '
            '"questions": ["clarifying question for the human?"], '
            '"tool_evidence": ["evidence gathered from tools"]}'
        )

    async def generate_critique(self, understanding: Understanding) -> SkepticCritique:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Understanding: {understanding.model_dump_json(indent=2)}"},
        ]
        response = await self.ollama.chat(messages, format="json", temperature=0.3)
        raw = response["message"]["content"]
        data = SkepticCritique.model_validate_json(raw)
        data.understanding_id = understanding.id
        return data
```

Write to `backend/agents/skeptic.py`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd backend && python -m pytest ../tests/test_agents.py -v
```
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/skeptic.py tests/test_agents.py
git commit -m "feat: implement SkepticAgent with critique generation"
```

---

### Task 7: FastAPI Orchestrator Endpoints

**Files:**
- Create: `backend/orchestrator/gates.py`
- Create: `backend/main.py`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from backend.orchestrator.gates import create_app


@pytest.fixture
def app():
    return create_app(db_path=":memory:")


@pytest.mark.asyncio
async def test_run_loop_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/run-loop", json={"goal": "Build a habit tracker"})
    assert resp.status_code == 200
    data = resp.json()
    assert "understanding" in data
    assert "critique" in data
    assert "confidence" in data
    assert "critique_resolved" in data
    assert data["critique_resolved"] is False


@pytest.mark.asyncio
async def test_resolve_critique(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_resp = await client.post("/api/run-loop", json={"goal": "Test app"})
        critique_id = run_resp.json()["critique"]["critique_id"]

        resolve_resp = await client.post(
            "/api/resolve-critique",
            json={"critique_id": critique_id, "resolution": "Use CSS animations"},
        )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_audit_events_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/run-loop", json={"goal": "Test app"})
        resp = await client.get("/api/audit/events?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert len(data["events"]) > 0


@pytest.mark.asyncio
async def test_run_loop_missing_goal(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/run-loop", json={})
    assert resp.status_code == 422
```

Write to `tests/test_integration.py`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && python -m pytest ../tests/test_integration.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write gates.py**

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event, get_events
from backend.agents.specialist import SpecialistAgent
from backend.agents.skeptic import SkepticAgent
from backend.core.confidence import compute_confidence


class RunLoopRequest(BaseModel):
    goal: str


class ResolveCritiqueRequest(BaseModel):
    critique_id: str
    resolution: str


def create_app(db_path: str | None = None, specialist: SpecialistAgent | None = None,
               skeptic: SkepticAgent | None = None) -> FastAPI:
    _specialist = specialist or SpecialistAgent()
    _skeptic = skeptic or SkepticAgent()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = await get_db(db_path)
        await init_db(db)
        app.state.db = db
        yield
        await db.close()

    app = FastAPI(lifespan=lifespan)

    @app.post("/api/run-loop")
    async def run_loop(req: RunLoopRequest):
        db = app.state.db

        understanding, fragile = await _specialist.generate_with_fragility_check(req.goal)

        await append_event(
            db, "understanding_generated", understanding.id, None,
            {"goal": req.goal, "assumptions": [a.model_dump() for a in understanding.assumptions],
             "fragile": fragile},
        )

        critique = await _skeptic.generate_critique(understanding)

        await append_event(
            db, "critique_created", understanding.id, critique.critique_id,
            {"scenarios": critique.scenarios, "questions": critique.questions},
        )

        profile = compute_confidence(
            open_unknowns=len([u for u in understanding.unknowns if u.resolution is None]),
            total_unknowns=len(understanding.unknowns),
            validated_count=len([a for a in understanding.assumptions if a.status == "validated"]),
            total_assumptions=len(understanding.assumptions),
            mandatory_categories=understanding.mandatory_categories,
            fragility_flag=fragile,
        )

        return {
            "understanding": understanding.model_dump(),
            "critique": critique.model_dump(),
            "confidence": profile.model_dump(),
            "critique_resolved": False,
        }

    @app.post("/api/resolve-critique")
    async def resolve_critique(req: ResolveCritiqueRequest):
        db = app.state.db
        await append_event(
            db, "human_resolution", None, req.critique_id,
            {"resolution": req.resolution},
        )
        return {"success": True}

    @app.get("/api/audit/events")
    async def list_events(limit: int = 50):
        db = app.state.db
        events = await get_events(db, limit=limit)
        return {"events": events}

    return app
```

Write to `backend/orchestrator/gates.py`.

- [ ] **Step 4: Create main.py**

```python
import uvicorn
from backend.orchestrator.gates import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Write to `backend/main.py`.

- [ ] **Step 5: Run test to verify it passes**

The integration tests need a running Ollama instance to fully pass. For CI, add a flag to skip real LLM calls.

Run:
```bash
ollama pull llama3.2  # ensure model is available
cd backend && python -m pytest ../tests/test_integration.py -v
```
Expected: All 4 tests PASS

If Ollama is not running, the Specialist/Skeptic calls will fail. For development, you can run Ollama separately: `ollama serve`.

- [ ] **Step 6: Verify endpoint works manually**

```bash
cd backend && python -m uvicorn backend.orchestrator.gates:create_app --reload &
curl -X POST http://localhost:8000/api/run-loop -H "Content-Type: application/json" -d '{"goal":"Build a habit tracker"}'
```
Kill the server afterwards:
```bash
kill %1
```

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/orchestrator/gates.py tests/test_integration.py
git commit -m "feat: implement FastAPI orchestrator with /api/run-loop endpoint"
```

---

### Task 8: Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.css`
- Create: `frontend/src/api.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "brogrammer-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "vite": "^5.1.0"
  }
}
```

Write to `frontend/package.json`.

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
```

Write to `frontend/vite.config.ts`.

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

Write to `frontend/tsconfig.json`.

- [ ] **Step 4: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Brogrammer – Phase 0</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Write to `frontend/index.html`.

- [ ] **Step 5: Create main.tsx**

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './App.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Write to `frontend/src/main.tsx`.

- [ ] **Step 6: Create api.ts**

```typescript
const API_BASE = '/api';

export interface Assumption {
  id: string;
  statement: string;
  status: 'open' | 'validated' | 'invalidated';
  validated_by: string | null;
}

export interface Unknown {
  id: string;
  question: string;
  resolution: string | null;
  resolved_at: string | null;
}

export interface MandatoryCategories {
  accessibility: string[];
  performance: string[];
  security: string[];
  state_management: string[];
  persistence: string[];
}

export interface Understanding {
  goal: string;
  assumptions: Assumption[];
  unknowns: Unknown[];
  mandatory_categories: MandatoryCategories;
}

export interface SkepticCritique {
  critique_id: string;
  understanding_id: string;
  scenarios: string[];
  questions: string[];
  tool_evidence: string[];
}

export interface ConfidenceProfile {
  score: number;
  open_unknowns: number;
  total_unknowns: number;
  validation_ratio: number;
  fragility_flag: boolean;
}

export interface RunLoopResponse {
  understanding: Understanding;
  critique: SkepticCritique;
  confidence: ConfidenceProfile;
  critique_resolved: boolean;
}

export async function runLoop(goal: string): Promise<RunLoopResponse> {
  const res = await fetch(`${API_BASE}/run-loop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function resolveCritique(critiqueId: string, resolution: string) {
  const res = await fetch(`${API_BASE}/resolve-critique`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ critique_id: critiqueId, resolution }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getAuditEvents(limit = 50) {
  const res = await fetch(`${API_BASE}/audit/events?limit=${limit}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
```

Write to `frontend/src/api.ts`.

- [ ] **Step 7: Create App.css**

```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
  color: #333;
  line-height: 1.5;
}

.app {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

h1 {
  font-size: 1.5rem;
  margin-bottom: 16px;
}

h2 {
  font-size: 1.15rem;
  margin-bottom: 8px;
  border-bottom: 1px solid #ddd;
  padding-bottom: 4px;
}

.goal-input {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.goal-input input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 1rem;
}

.goal-input button {
  padding: 10px 20px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1rem;
}

.goal-input button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.section {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  margin-right: 6px;
}

.tag-open {
  background: #fef2f2;
  color: #dc2626;
}

.tag-validated {
  background: #f0fdf4;
  color: #16a34a;
}

.tag-invalidated {
  background: #fef2f2;
  color: #dc2626;
}

.assumption-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.critique-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.critique-item:last-child {
  border-bottom: none;
}

.resolve-btn {
  padding: 4px 12px;
  background: #f0f0f0;
  border: 1px solid #ccc;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  margin-top: 4px;
}

.resolve-btn:hover {
  background: #e0e0e0;
}

.confidence-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: 700;
  font-size: 1.1rem;
}

.confidence-badge.low {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.confidence-badge.medium {
  background: #fefce8;
  color: #ca8a04;
  border: 1px solid #fef08a;
}

.confidence-badge.high {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #bbf7d0;
}

.confidence-details {
  font-size: 0.85rem;
  color: #666;
  margin-top: 4px;
}

.fragile-warning {
  color: #dc2626;
  font-weight: 600;
  margin-top: 4px;
}
```

Write to `frontend/src/App.css`.

- [ ] **Step 8: Create App.tsx**

```tsx
import { useState } from 'react';
import { runLoop, resolveCritique, RunLoopResponse } from './api';
import UnderstandingView from './components/UnderstandingView';
import CritiquePanel from './components/CritiquePanel';
import ConfidenceBadge from './components/ConfidenceBadge';

function App() {
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RunLoopResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await runLoop(goal.trim());
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (critiqueId: string, resolution: string) => {
    try {
      await resolveCritique(critiqueId, resolution);
      setResult((prev) => prev ? { ...prev, critique_resolved: true } : prev);
    } catch (e) {
      console.error('Resolve failed', e);
    }
  };

  return (
    <div className="app">
      <h1>Brogrammer — Phase 0</h1>

      <div className="goal-input">
        <input
          type="text"
          placeholder="Describe what you want to build..."
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRun()}
        />
        <button onClick={handleRun} disabled={loading}>
          {loading ? 'Running...' : 'Run Loop'}
        </button>
      </div>

      {error && <div className="section" style={{ color: '#dc2626' }}>{error}</div>}

      {result && (
        <>
          <UnderstandingView understanding={result.understanding} />
          <CritiquePanel
            critique={result.critique}
            resolved={result.critique_resolved}
            onResolve={handleResolve}
          />
          <div className="section">
            <ConfidenceBadge profile={result.confidence} />
          </div>
        </>
      )}
    </div>
  );
}

export default App;
```

Write to `frontend/src/App.tsx`.

- [ ] **Step 9: Verify frontend builds**

```bash
cd frontend && npm install && npx tsc --noEmit
```
Expected: No type errors

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React frontend with Vite + TypeScript"
```

---

### Task 9: Frontend Components

**Files:**
- Create: `frontend/src/components/UnderstandingView.tsx`
- Create: `frontend/src/components/CritiquePanel.tsx`
- Create: `frontend/src/components/ConfidenceBadge.tsx`

- [ ] **Step 1: Create UnderstandingView.tsx**

```tsx
import { Understanding } from '../api';

interface Props {
  understanding: Understanding;
}

function statusTag(status: string) {
  const labels: Record<string, string> = {
    open: '🔴 Open',
    validated: '🟢 Validated',
    invalidated: '🔴 Invalidated',
  };
  return labels[status] || status;
}

function statusClass(status: string) {
  const classes: Record<string, string> = {
    open: 'tag-open',
    validated: 'tag-validated',
    invalidated: 'tag-invalidated',
  };
  return classes[status] || '';
}

export default function UnderstandingView({ understanding }: Props) {
  return (
    <div className="section">
      <h2>Understanding</h2>
      <p><strong>Goal:</strong> {understanding.goal}</p>

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Assumptions</h3>
      {understanding.assumptions.length === 0 && <p style={{ color: '#999' }}>None identified</p>}
      {understanding.assumptions.map((a) => (
        <div key={a.id} className="assumption-item">
          <span className={`tag ${statusClass(a.status)}`}>{statusTag(a.status)}</span>
          <span>{a.statement}</span>
          {a.validated_by && <span style={{ fontSize: '0.8rem', color: '#666' }}>(by {a.validated_by})</span>}
        </div>
      ))}

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Unknowns</h3>
      {understanding.unknowns.length === 0 && <p style={{ color: '#999' }}>None identified</p>}
      <ul style={{ paddingLeft: 20 }}>
        {understanding.unknowns.map((u) => (
          <li key={u.id}>
            {u.question}
            {u.resolution && <span style={{ color: '#16a34a' }}> → {u.resolution}</span>}
          </li>
        ))}
      </ul>

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Mandatory Categories</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <tbody>
          {(['accessibility', 'performance', 'security', 'state_management', 'persistence'] as const).map((cat) => (
            <tr key={cat}>
              <td style={{ padding: '4px 8px', fontWeight: 600, borderBottom: '1px solid #f0f0f0' }}>
                {cat.replace('_', ' ')}
              </td>
              <td style={{ padding: '4px 8px', borderBottom: '1px solid #f0f0f0' }}>
                {understanding.mandatory_categories[cat].length > 0
                  ? understanding.mandatory_categories[cat].join(', ')
                  : <span style={{ color: '#dc2626' }}>⚠ Empty</span>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

Write to `frontend/src/components/UnderstandingView.tsx`.

- [ ] **Step 2: Create CritiquePanel.tsx**

```tsx
import { useState } from 'react';
import { SkepticCritique } from '../api';

interface Props {
  critique: SkepticCritique;
  resolved: boolean;
  onResolve: (critiqueId: string, resolution: string) => void;
}

export default function CritiquePanel({ critique, resolved, onResolve }: Props) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  return (
    <div className="section">
      <h2>Skeptic Critique {resolved && <span style={{ color: '#16a34a' }}>✅ Resolved</span>}</h2>

      <h3 style={{ marginTop: 8, fontSize: '1rem' }}>Failure Scenarios</h3>
      {critique.scenarios.length === 0 && <p style={{ color: '#999' }}>No scenarios identified</p>}
      {critique.scenarios.map((s, i) => (
        <div key={i} className="critique-item">⚠ {s}</div>
      ))}

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Questions for Resolution</h3>
      {critique.questions.length === 0 && <p style={{ color: '#999' }}>No questions</p>}
      {critique.questions.map((q, i) => (
        <div key={i} className="critique-item">
          <div>❓ {q}</div>
          {!resolved && (
            <>
              <button className="resolve-btn" onClick={() => setActiveIndex(activeIndex === i ? null : i)}>
                {activeIndex === i ? 'Cancel' : 'Resolve'}
              </button>
              {activeIndex === i && (
                <div style={{ marginTop: 8 }}>
                  <input
                    type="text"
                    placeholder="Your resolution..."
                    style={{ padding: '6px 10px', border: '1px solid #ccc', borderRadius: 4, width: '60%', marginRight: 8 }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        const input = e.target as HTMLInputElement;
                        if (input.value.trim()) {
                          onResolve(critique.critique_id, input.value.trim());
                        }
                      }
                    }}
                  />
                  <button
                    className="resolve-btn"
                    onClick={(e) => {
                      const input = (e.target as HTMLElement).previousElementSibling as HTMLInputElement;
                      if (input?.value?.trim()) {
                        onResolve(critique.critique_id, input.value.trim());
                      }
                    }}
                  >
                    Submit
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      ))}

      {critique.tool_evidence.length > 0 && (
        <>
          <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Tool Evidence</h3>
          <ul style={{ paddingLeft: 20, fontSize: '0.9rem', color: '#666' }}>
            {critique.tool_evidence.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}
```

Write to `frontend/src/components/CritiquePanel.tsx`.

- [ ] **Step 3: Create ConfidenceBadge.tsx**

```tsx
import { ConfidenceProfile } from '../api';

interface Props {
  profile: ConfidenceProfile;
}

export default function ConfidenceBadge({ profile }: Props) {
  const scorePct = Math.round(profile.score * 100);
  const levelClass = scorePct >= 90 ? 'high' : scorePct >= 70 ? 'medium' : 'low';

  return (
    <div>
      <div className={`confidence-badge ${levelClass}`}>
        {scorePct >= 90 ? '🟢' : scorePct >= 70 ? '🟡' : '🔴'}
        Confidence: {scorePct}%
      </div>
      <div className="confidence-details">
        Open unknowns: {profile.open_unknowns} / {profile.total_unknowns} total |
        Validation ratio: {Math.round(profile.validation_ratio * 100)}%
      </div>
      {profile.fragility_flag && (
        <div className="fragile-warning">
          ⚠ Fragile: Specialist produced divergent assumptions at high temperature
        </div>
      )}
    </div>
  );
}
```

Write to `frontend/src/components/ConfidenceBadge.tsx`.

- [ ] **Step 4: Verify frontend builds**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: implement UnderstandingView, CritiquePanel, ConfidenceBadge components"
```

---

### Task 10: Final Integration Test & Verification

**Files:**
- No new files — run existing test suite and manual verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest ../tests/ -v
```
Expected: All tests PASS

- [ ] **Step 2: Run frontend type check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Manual end-to-end verification**

Start the backend:
```bash
cd backend && python -m uvicorn backend.orchestrator.gates:create_app --reload
```

Start the frontend (separate terminal):
```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`, enter a goal like "Build a habit tracker", click "Run Loop". Verify:
- Understanding view shows assumptions (🟢/🔴 tags), unknowns, mandatory categories
- Critique panel shows scenarios and questions with resolve toggles
- Confidence badge shows score with color coding
- Submitting a resolution marks the critique as resolved

- [ ] **Step 4: Update ACTIVE.md**

Mark all Phase 0 tasks as complete in `docs/ACTIVE.md`.

- [ ] **Step 5: Append to COMPLETED.md**

```
| P0-001 | 0 | Project scaffold | 2026-05-17 |
| P0-002 | 0 | Core data models | 2026-05-17 |
| P0-003 | 0 | Confidence formula | 2026-05-17 |
| P0-004 | 0 | SQLite audit log | 2026-05-17 |
| P0-005 | 0 | Specialist agent | 2026-05-17 |
| P0-006 | 0 | Skeptic agent | 2026-05-17 |
| P0-007 | 0 | FastAPI orchestrator | 2026-05-17 |
| P0-008 | 0 | Frontend scaffold | 2026-05-17 |
| P0-009 | 0 | Frontend components | 2026-05-17 |
| P0-010 | 0 | Integration test | 2026-05-17 |
```

- [ ] **Step 6: Final commit**

```bash
git add docs/ACTIVE.md docs/COMPLETED.md
git commit -m "docs: mark Phase 0 complete"
```
