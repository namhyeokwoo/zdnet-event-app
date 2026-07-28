"""ZD브리핑 캘린더 개인 CRUD + 검수 상태 저장소 (Postgres/Neon).

K:\\claude\\events_store.py 의 Postgres 이식판 — 함수 시그니처/반환 형태는 동일,
sqlite3 -> psycopg2, ? -> %s, INSERT OR IGNORE -> ON CONFLICT DO NOTHING 로 교체.
"""
import json
import os
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ["DATABASE_URL"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS manual_events (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  title TEXT NOT NULL,
  organizer TEXT,
  start_at TEXT NOT NULL,
  end_at TEXT,
  time TEXT,
  location TEXT,
  description TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_review (
  event_id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'pending',
  overrides_json TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS event_tags (
  event_id TEXT NOT NULL,
  tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (event_id, tag_id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db() -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
        conn.commit()


# ── 개인 일정 (manual_events) ──────────────────────────────────────────

def list_manual_events() -> list[dict]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM manual_events ORDER BY start_at")
        return [dict(r) for r in cur.fetchall()]


def create_manual_event(data: dict) -> dict:
    now = _now()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO manual_events
               (title, organizer, start_at, end_at, time, location, description, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (data["title"], data.get("organizer"), data["start_at"], data.get("end_at"),
             data.get("time"), data.get("location"), data.get("description"), now, now),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return row


def update_manual_event(event_id: int, data: dict) -> dict | None:
    fields = ["title", "organizer", "start_at", "end_at", "time", "location", "description"]
    updates = {k: v for k, v in data.items() if k in fields}
    with _conn() as conn, conn.cursor() as cur:
        if not updates:
            cur.execute("SELECT * FROM manual_events WHERE id = %s", (event_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        cur.execute(
            f"UPDATE manual_events SET {set_clause} WHERE id = %s RETURNING *",
            (*updates.values(), event_id),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def delete_manual_event(event_id: int) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM event_tags WHERE event_id = %s", (str(event_id),))
        cur.execute("DELETE FROM manual_events WHERE id = %s", (event_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


# ── 검수 상태 (event_review) — 자동 추출 이벤트용 오버레이 ──────────────

def list_review_status() -> dict:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM event_review")
        result = {}
        for r in cur.fetchall():
            d = dict(r)
            raw = d.pop("overrides_json")
            d["overrides"] = json.loads(raw) if raw else None
            result[d["event_id"]] = d
        return result


def set_review_status(event_id: str, status: str, overrides: dict | None = None) -> dict:
    if status not in ("pending", "confirmed", "rejected"):
        raise ValueError("status는 pending/confirmed/rejected 중 하나여야 합니다")
    now = _now()
    overrides_json = json.dumps(overrides, ensure_ascii=False) if overrides else None
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO event_review (event_id, status, overrides_json, updated_at)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (event_id) DO UPDATE SET
                 status = EXCLUDED.status,
                 overrides_json = EXCLUDED.overrides_json,
                 updated_at = EXCLUDED.updated_at
               RETURNING *""",
            (event_id, status, overrides_json, now),
        )
        d = dict(cur.fetchone())
        conn.commit()
        raw = d.pop("overrides_json")
        d["overrides"] = json.loads(raw) if raw else None
        return d


# ── 태그 ────────────────────────────────────────────────────────────────

def list_tags() -> list[dict]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM tags ORDER BY name")
        return [dict(r) for r in cur.fetchall()]


def create_tag(name: str) -> dict:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO tags (name) VALUES (%s)
               ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
               RETURNING *""",
            (name,),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return row


def delete_tag(tag_id: int) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tags WHERE id = %s", (tag_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def get_event_tags(event_id: str) -> list[dict]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT t.* FROM tags t
               JOIN event_tags et ON et.tag_id = t.id
               WHERE et.event_id = %s ORDER BY t.name""",
            (event_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def add_event_tag(event_id: str, tag_id: int) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO event_tags (event_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (event_id, tag_id),
        )
        conn.commit()


def remove_event_tag(event_id: str, tag_id: int) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM event_tags WHERE event_id = %s AND tag_id = %s",
            (event_id, tag_id),
        )
        conn.commit()


init_db()
