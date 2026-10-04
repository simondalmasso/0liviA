from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    provider TEXT,
    status TEXT NOT NULL DEFAULT 'complete',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session_id_id
    ON messages(session_id, id DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content)
    VALUES('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content)
    VALUES('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_scope_active
    ON memories(scope, is_active, id DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    key,
    value,
    content='memories',
    content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, key, value) VALUES (new.id, new.key, new.value);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, key, value)
    VALUES('delete', old.id, old.key, old.value);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, key, value)
    VALUES('delete', old.id, old.key, old.value);
    INSERT INTO memories_fts(rowid, key, value) VALUES (new.id, new.key, new.value);
END;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    job_id TEXT,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session_id_id
    ON events(session_id, id DESC);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    repo TEXT,
    worktree TEXT,
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_state (
    provider TEXT PRIMARY KEY,
    failures INTEGER NOT NULL DEFAULT 0,
    cooldown_until REAL NOT NULL DEFAULT 0,
    day TEXT NOT NULL DEFAULT '',
    daily_requests INTEGER NOT NULL DEFAULT 0,
    last_ttft_ms REAL,
    last_error TEXT,
    updated_at REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self.path,
            timeout=5,
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_session(self, title: str = "") -> str:
        now = time.time()
        sid = uuid.uuid4().hex[:16]
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                (sid, title[:200], now, now),
            )
        return sid

    def session_exists(self, session_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM sessions WHERE id=? LIMIT 1", (session_id,)
            ).fetchone()
        return row is not None

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT id,title,created_at,updated_at
                   FROM sessions
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        provider: str | None = None,
        status: str = "complete",
    ) -> int:
        now = time.time()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                cur = self._conn.execute(
                    """INSERT INTO messages(session_id,role,content,provider,status,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    (session_id, role, content, provider, status, now),
                )
                self._conn.execute(
                    "UPDATE sessions SET updated_at=? WHERE id=?",
                    (now, session_id),
                )
                self._conn.execute("COMMIT")
                return int(cur.lastrowid)
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def recent_messages(self, session_id: str, limit: int = 24) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT id,role,content,provider,status,created_at
                   FROM messages WHERE session_id=?
                   ORDER BY id DESC LIMIT ?""",
                (session_id, max(1, min(limit, 200))),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def message_count(self, session_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return int(row["n"])

    def promote_memory(
        self,
        scope: str,
        key: str,
        value: str,
        *,
        source: str,
        confidence: float = 1.0,
    ) -> int:
        now = time.time()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "UPDATE memories SET is_active=0 WHERE scope=? AND key=? AND is_active=1",
                    (scope, key),
                )
                cur = self._conn.execute(
                    """INSERT INTO memories(scope,key,value,source,confidence,is_active,created_at)
                       VALUES(?,?,?,?,?,1,?)""",
                    (scope, key, value, source, float(confidence), now),
                )
                self._conn.execute("COMMIT")
                return int(cur.lastrowid)
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def recall_memories(self, query: str, scope: str = "global", limit: int = 8) -> list[dict[str, Any]]:
        tokens = re.findall(r"[\wÀ-ÿ]+", query.lower(), flags=re.UNICODE)
        if not tokens:
            return []
        expr = " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens[:12])
        with self._lock:
            try:
                rows = self._conn.execute(
                    """SELECT m.id,m.scope,m.key,m.value,m.source,m.confidence,m.created_at,
                              bm25(memories_fts) AS rank
                       FROM memories_fts
                       JOIN memories m ON m.id=memories_fts.rowid
                       WHERE memories_fts MATCH ?
                         AND m.is_active=1
                         AND (m.scope=? OR m.scope='global')
                       ORDER BY rank
                       LIMIT ?""",
                    (expr, scope, max(1, min(limit, 50))),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = self._conn.execute(
                    """SELECT id,scope,key,value,source,confidence,created_at,0 AS rank
                       FROM memories
                       WHERE is_active=1
                         AND (scope=? OR scope='global')
                         AND (lower(key) LIKE ? OR lower(value) LIKE ?)
                       ORDER BY id DESC LIMIT ?""",
                    (scope, "%" + query.lower() + "%", "%" + query.lower() + "%", limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def record_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
        job_id: str | None = None,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO events(session_id,job_id,type,payload_json,created_at)
                   VALUES(?,?,?,?,?)""",
                (session_id, job_id, event_type, json.dumps(payload, ensure_ascii=False), time.time()),
            )
        return int(cur.lastrowid)

    def create_job(self, kind: str, repo: str | None = None) -> str:
        job_id = uuid.uuid4().hex[:16]
        now = time.time()
        with self._lock:
            self._conn.execute(
                """INSERT INTO jobs(id,kind,status,repo,checkpoint_json,created_at,updated_at)
                   VALUES(?,?, 'queued', ?, '{}', ?, ?)""",
                (job_id, kind, repo, now, now),
            )
        return job_id

    def checkpoint_job(self, job_id: str, status: str, checkpoint: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE jobs
                   SET status=?,checkpoint_json=?,updated_at=?
                   WHERE id=?""",
                (status, json.dumps(checkpoint, ensure_ascii=False), time.time(), job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["checkpoint"] = json.loads(out.pop("checkpoint_json"))
        return out

    def provider_state(self, provider: str) -> dict[str, Any]:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM provider_state WHERE provider=?",
                (provider,),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    """INSERT INTO provider_state(provider,day,updated_at)
                       VALUES(?,?,?)""",
                    (provider, today, time.time()),
                )
                row = self._conn.execute(
                    "SELECT * FROM provider_state WHERE provider=?",
                    (provider,),
                ).fetchone()
            state = dict(row)
            if state["day"] != today:
                self._conn.execute(
                    """UPDATE provider_state
                       SET day=?,daily_requests=0,updated_at=?
                       WHERE provider=?""",
                    (today, time.time(), provider),
                )
                state["day"] = today
                state["daily_requests"] = 0
        return state

    def provider_attempt(self, provider: str) -> None:
        self.provider_state(provider)
        with self._lock:
            self._conn.execute(
                """UPDATE provider_state
                   SET daily_requests=daily_requests+1,updated_at=?
                   WHERE provider=?""",
                (time.time(), provider),
            )

    def provider_success(self, provider: str, ttft_ms: float) -> None:
        self.provider_state(provider)
        with self._lock:
            self._conn.execute(
                """UPDATE provider_state
                   SET failures=0,cooldown_until=0,last_ttft_ms=?,last_error=NULL,updated_at=?
                   WHERE provider=?""",
                (float(ttft_ms), time.time(), provider),
            )

    def provider_failure(self, provider: str, error: str, cooldown_until: float) -> None:
        self.provider_state(provider)
        with self._lock:
            self._conn.execute(
                """UPDATE provider_state
                   SET failures=failures+1,cooldown_until=?,last_error=?,updated_at=?
                   WHERE provider=?""",
                (float(cooldown_until), error[:1000], time.time(), provider),
            )
