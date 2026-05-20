import aiosqlite

from backend.core import config

DB_PATH = config.get("BROGRAMMER_DB_PATH", "brogrammer.db")


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
    await db.execute("""
        CREATE TABLE IF NOT EXISTS tech_plans (
            id TEXT PRIMARY KEY,
            understanding_id TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS build_artifacts (
        id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL,
        artifact_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (plan_id) REFERENCES tech_plans(id)
    )
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS test_reports (
        id TEXT PRIMARY KEY,
        build_id TEXT NOT NULL,
        report_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (build_id) REFERENCES build_artifacts(id)
    )
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS tool_call_events (
        id TEXT PRIMARY KEY,
        critique_id TEXT NOT NULL,
        round INTEGER NOT NULL,
        tool TEXT NOT NULL,
        args TEXT NOT NULL,
        exit_code INTEGER NOT NULL,
        stdout_excerpt TEXT NOT NULL,
        stderr_excerpt TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    await db.execute("""
    CREATE INDEX IF NOT EXISTS idx_tool_call_events_critique
    ON tool_call_events(critique_id)
    """)
    await db.commit()
