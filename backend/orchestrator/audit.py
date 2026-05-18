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
