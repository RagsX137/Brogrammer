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


async def get_events(db: aiosqlite.Connection, limit: int = 50, before: str | None = None) -> list[dict]:
    if before:
        cursor = await db.execute(
            "SELECT * FROM audit_events WHERE created_at < ? ORDER BY created_at DESC LIMIT ?",
            (before, limit),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def append_tool_call(
    db: aiosqlite.Connection,
    critique_id: str,
    round: int,
    tool: str,
    args: list[str],
    exit_code: int,
    stdout: str,
    stderr: str,
) -> str:
    from uuid import uuid4
    event_id = uuid4().hex[:16]
    created_at = datetime.now(timezone.utc).isoformat()
    stdout_excerpt = stdout[:4096]
    stderr_excerpt = stderr[:4096]
    await db.execute(
        """
        INSERT INTO tool_call_events (id, critique_id, round, tool, args, exit_code,
                                      stdout_excerpt, stderr_excerpt, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, critique_id, round, tool, json.dumps(args), exit_code,
         stdout_excerpt, stderr_excerpt, created_at),
    )
    await db.commit()
    return event_id


async def get_tool_calls(db: aiosqlite.Connection, critique_id: str) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM tool_call_events WHERE critique_id=? ORDER BY round ASC",
        (critique_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
