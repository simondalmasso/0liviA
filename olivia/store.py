from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .security import redact_secrets


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {key: _scrub_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_value(item) for item in value]
    if isinstance(value, tuple):
        return [_scrub_value(item) for item in value]
    return value


DEFAULT_PROJECT_ID = "default"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS library_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    project_id TEXT REFERENCES projects(id),
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

CREATE TABLE IF NOT EXISTS owner_account (
    id INTEGER PRIMARY KEY CHECK(id=1),
    email TEXT NOT NULL UNIQUE,
    password_verifier TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trusted_devices (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trusted_devices_expiry
    ON trusted_devices(expires_at);

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
        self._migrate_workspace_schema()

    def _migrate_workspace_schema(self) -> None:
        with self._lock:
            columns = {
                str(row["name"])
                for row in self._conn.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "project_id" not in columns:
                self._conn.execute("ALTER TABLE sessions ADD COLUMN project_id TEXT")
            self._conn.execute(
                """CREATE INDEX IF NOT EXISTS idx_sessions_project_updated
                   ON sessions(project_id, updated_at DESC)"""
            )
            now = time.time()
            self._conn.execute(
                """INSERT OR IGNORE INTO projects(id,name,created_at,updated_at)
                   VALUES(?,?,?,?)""",
                (DEFAULT_PROJECT_ID, "0liviA", now, now),
            )
            self._conn.execute(
                "UPDATE sessions SET project_id=? WHERE project_id IS NULL OR project_id=''",
                (DEFAULT_PROJECT_ID,),
            )

    def project_exists(self, project_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM projects WHERE id=? LIMIT 1", (project_id,)
            ).fetchone()
        return row is not None

    def create_project(self, name: str) -> str:
        clean = redact_secrets(str(name or "").strip())[:120]
        if not clean:
            raise ValueError("project name is required")
        project_id = uuid.uuid4().hex[:16]
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO projects(id,name,created_at,updated_at) VALUES(?,?,?,?)",
                (project_id, clean, now, now),
            )
        return project_id

    def list_projects(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT id,name,created_at,updated_at
                   FROM projects
                   ORDER BY CASE WHEN id=? THEN 0 ELSE 1 END, updated_at DESC
                   LIMIT ?""",
                (DEFAULT_PROJECT_ID, max(1, min(limit, 200))),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_library_item(self, title: str, value: str) -> str:
        clean_title = redact_secrets(str(title or "").strip())[:120]
        clean_value = redact_secrets(str(value or "").strip())[:20_000]
        if not clean_title or not clean_value:
            raise ValueError("library title and value are required")
        item_id = uuid.uuid4().hex[:16]
        now = time.time()
        with self._lock:
            self._conn.execute(
                """INSERT INTO library_items(id,title,value,created_at,updated_at)
                   VALUES(?,?,?,?,?)""",
                (item_id, clean_title, clean_value, now, now),
            )
        return item_id

    def list_library_items(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT id,title,value,created_at,updated_at
                   FROM library_items
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_owner_account(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """SELECT email,password_verifier,created_at,updated_at
                   FROM owner_account WHERE id=1"""
            ).fetchone()
        return dict(row) if row is not None else None

    def register_owner(self, email: str, password_verifier: str) -> bool:
        normalized = str(email or "").strip().casefold()
        verifier = str(password_verifier or "").strip()
        if not normalized or not verifier:
            raise ValueError("email and password verifier are required")
        now = time.time()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                exists = self._conn.execute(
                    "SELECT 1 FROM owner_account WHERE id=1"
                ).fetchone()
                if exists is not None:
                    self._conn.execute("ROLLBACK")
                    return False
                self._conn.execute(
                    """INSERT INTO owner_account(id,email,password_verifier,created_at,updated_at)
                       VALUES(1,?,?,?,?)""",
                    (normalized, verifier, now, now),
                )
                self._conn.execute("COMMIT")
                return True
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def seed_owner_if_absent(self, email: str, password_verifier: str) -> None:
        if email and password_verifier:
            self.register_owner(email, password_verifier)

    def create_trusted_device(self, label: str, *, expires_at: float) -> str:
        clean_label = redact_secrets(str(label or "").strip())[:120] or "Dispositivo"
        now = time.time()
        device_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                """INSERT INTO trusted_devices(id,label,created_at,last_seen_at,expires_at)
                   VALUES(?,?,?,?,?)""",
                (device_id, clean_label, now, now, float(expires_at)),
            )
        return device_id

    def trusted_device_active(self, device_id: str, *, now: float | None = None) -> bool:
        moment = time.time() if now is None else float(now)
        with self._lock:
            row = self._conn.execute(
                "SELECT expires_at FROM trusted_devices WHERE id=? LIMIT 1",
                (str(device_id),),
            ).fetchone()
            if row is None:
                return False
            if float(row["expires_at"]) <= moment:
                self._conn.execute(
                    "DELETE FROM trusted_devices WHERE id=?",
                    (str(device_id),),
                )
                return False
            self._conn.execute(
                "UPDATE trusted_devices SET last_seen_at=? WHERE id=?",
                (moment, str(device_id)),
            )
        return True

    def list_trusted_devices(
        self,
        *,
        now: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        moment = time.time() if now is None else float(now)
        with self._lock:
            self._conn.execute(
                "DELETE FROM trusted_devices WHERE expires_at<=?",
                (moment,),
            )
            rows = self._conn.execute(
                """SELECT id,label,created_at,last_seen_at,expires_at
                   FROM trusted_devices
                   ORDER BY last_seen_at DESC
                   LIMIT ?""",
                (max(1, min(int(limit), 100)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_trusted_device(self, device_id: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM trusted_devices WHERE id=?",
                (str(device_id),),
            )
        return int(cur.rowcount)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_session(self, title: str = "", project_id: str | None = None) -> str:
        now = time.time()
        sid = uuid.uuid4().hex[:16]
        target_project = project_id or DEFAULT_PROJECT_ID
        if not self.project_exists(target_project):
            raise ValueError("project not found")
        with self._lock:
            self._conn.execute(
                """INSERT INTO sessions(id,title,project_id,created_at,updated_at)
                   VALUES(?,?,?,?,?)""",
                (sid, redact_secrets(str(title))[:200], target_project, now, now),
            )
            self._conn.execute(
                "UPDATE projects SET updated_at=? WHERE id=?",
                (now, target_project),
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
                """SELECT id,title,project_id,created_at,updated_at
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
                    (session_id, role, redact_secrets(str(content)), provider, status, now),
                )
                self._conn.execute(
                    "UPDATE sessions SET updated_at=? WHERE id=?",
                    (now, session_id),
                )
                self._conn.execute(
                    """UPDATE projects SET updated_at=?
                       WHERE id=(SELECT project_id FROM sessions WHERE id=?)""",
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
                    (scope, redact_secrets(str(key))),
                )
                cur = self._conn.execute(
                    """INSERT INTO memories(scope,key,value,source,confidence,is_active,created_at)
                       VALUES(?,?,?,?,?,1,?)""",
                    (
                        scope,
                        redact_secrets(str(key)),
                        redact_secrets(str(value)),
                        source,
                        float(confidence),
                        now,
                    ),
                )
                self._conn.execute("COMMIT")
                return int(cur.lastrowid)
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def list_memories(
        self,
        scope: str = "global",
        limit: int = 100,
        *,
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 500))
        with self._lock:
            if include_inactive:
                rows = self._conn.execute(
                    """SELECT id,scope,key,value,source,confidence,is_active,created_at
                       FROM memories
                       WHERE scope=?
                       ORDER BY id DESC
                       LIMIT ?""",
                    (scope, bounded_limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """SELECT id,scope,key,value,source,confidence,is_active,created_at
                       FROM memories
                       WHERE scope=? AND is_active=1
                       ORDER BY id DESC
                       LIMIT ?""",
                    (scope, bounded_limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def delete_memory(self, scope: str, key: str) -> int:
        """Physically delete every persisted version of a memory key."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM memories WHERE scope=? AND key=?",
                (scope, redact_secrets(str(key))),
            )
        return int(cur.rowcount)

    def deactivate_memory(self, scope: str, key: str) -> int:
        """Legacy soft-delete helper kept for migration compatibility."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE memories SET is_active=0 WHERE scope=? AND key=? AND is_active=1",
                (scope, redact_secrets(str(key))),
            )
        return int(cur.rowcount)

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
                (
                    session_id,
                    job_id,
                    event_type,
                    json.dumps(_scrub_value(payload), ensure_ascii=False),
                    time.time(),
                ),
            )
        return int(cur.lastrowid)

    def prune_security_events(
        self,
        *,
        now: float | None = None,
        retention_s: float = 90 * 24 * 60 * 60,
        keep_latest: int = 2000,
    ) -> int:
        moment = time.time() if now is None else float(now)
        cutoff = moment - max(0.0, float(retention_s))
        keep = max(1, min(int(keep_latest), 10_000))
        with self._lock:
            old = self._conn.execute(
                "DELETE FROM events WHERE type LIKE ? AND created_at<?",
                ("security.%", cutoff),
            ).rowcount
            overflow = self._conn.execute(
                """DELETE FROM events
                   WHERE type LIKE ?
                     AND id NOT IN (
                       SELECT id FROM events
                       WHERE type LIKE ?
                       ORDER BY id DESC
                       LIMIT ?
                     )""",
                ("security.%", "security.%", keep),
            ).rowcount
        return int(old) + int(overflow)

    def recent_events(self, *, prefix: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 500))
        with self._lock:
            if prefix:
                rows = self._conn.execute(
                    """SELECT id,session_id,job_id,type,payload_json,created_at
                       FROM events
                       WHERE type LIKE ?
                       ORDER BY id DESC
                       LIMIT ?""",
                    (f"{prefix}%", bounded_limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """SELECT id,session_id,job_id,type,payload_json,created_at
                       FROM events
                       ORDER BY id DESC
                       LIMIT ?""",
                    (bounded_limit,),
                ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            out.append(item)
        return out

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
                (
                    status,
                    json.dumps(_scrub_value(checkpoint), ensure_ascii=False),
                    time.time(),
                    job_id,
                ),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["checkpoint"] = json.loads(out.pop("checkpoint_json"))
        return out
