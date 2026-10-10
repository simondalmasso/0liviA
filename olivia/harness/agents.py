"""Fail-closed durable Agent Fabric PR-B control plane.

No model inference, tool invocation, network access, automatic worker spawn or
background retry exists in this module. Owner and executor attestations must be
provided by separate *trusted* Core adapters; unconfigured entry points deny.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from .budget import BudgetGuard


class AgentDenied(RuntimeError):
    """Permission, schema or budget policy rejected the request."""


class AgentConflict(RuntimeError):
    """Immutable identity or state transition conflict."""


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    role: str
    allowed_tools: tuple[str, ...]
    max_tokens: int
    max_calls: int
    parent_id: str | None = None
    model_provider: str = ""


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    agent_id: str
    request_key: str
    input_sha256: str


_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,79}$")
_TOOL_RE = re.compile(r"^[a-z][a-z0-9._:-]{0,63}$")
_ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_MODEL_RE = re.compile(r"^[a-zA-Z0-9@][a-zA-Z0-9@./:_-]{0,127}$")
_MAX_DEPTH = 12
_MAX_CHECKPOINT_BYTES = 16_384

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fabric_agents (
  agent_id TEXT PRIMARY KEY,
  proposal_key TEXT NOT NULL UNIQUE,
  proposal_hash TEXT NOT NULL,
  parent_id TEXT REFERENCES fabric_agents(agent_id),
  role TEXT NOT NULL,
  tools_json TEXT NOT NULL,
  model_provider TEXT NOT NULL DEFAULT '',
  max_tokens INTEGER NOT NULL CHECK (max_tokens > 0),
  max_calls INTEGER NOT NULL CHECK (max_calls > 0),
  reserved_runs INTEGER NOT NULL DEFAULT 0 CHECK (reserved_runs >= 0),
  state TEXT NOT NULL CHECK (state IN ('draft','approved','revoked')),
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fabric_agents_parent ON fabric_agents(parent_id);
CREATE TABLE IF NOT EXISTS fabric_agent_runs (
  run_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES fabric_agents(agent_id),
  request_key TEXT NOT NULL UNIQUE,
  input_sha256 TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN
      ('queued','leased','uncertain','completed','failed','cancelled')),
  checkpoint_json TEXT NOT NULL DEFAULT '{}',
  checkpoint_seq INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  lease_expires_at REAL,
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
  result_sha256 TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fabric_runs_agent ON fabric_agent_runs(agent_id,state);
CREATE TABLE IF NOT EXISTS fabric_agent_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL,
  run_id TEXT,
  kind TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fabric_events_run ON fabric_agent_events(run_id,seq);
"""


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ID_RE.fullmatch(value))


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.fullmatch(value))


def _agent_view(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "agent_id": row["agent_id"],
        "proposal_key": row["proposal_key"],
        "parent_id": row["parent_id"],
        "role": row["role"],
        "allowed_tools": tuple(json.loads(row["tools_json"])),
        "model_provider": row["model_provider"],
        "max_tokens": row["max_tokens"],
        "max_calls": row["max_calls"],
        "reserved_runs": row["reserved_runs"],
        "state": row["state"],
        "approved": row["state"] == "approved",
    }


def _run_view(row: sqlite3.Row) -> dict[str, Any]:
    # Never expose a lease token through read-only state or audit surfaces.
    return {
        "run_id": row["run_id"],
        "agent_id": row["agent_id"],
        "request_key": row["request_key"],
        "input_sha256": row["input_sha256"],
        "state": row["state"],
        "checkpoint_seq": row["checkpoint_seq"],
        "cancel_requested": bool(row["cancel_requested"]),
        "result_sha256": row["result_sha256"],
    }


class AgentFabric:
    """SQLite agent registry; intentionally *not* an executor or scheduler.

    owner_verifier(agent_id, proposal_sha256, opaque_proof) must be supplied by
    the authenticated Core approval adapter. A model cannot mint approval.
    executor_verifier(run_id, opaque_proof) must be supplied by an authorized
    worker adapter; callers cannot lease a task merely by knowing its ID.

    These callbacks are local trust boundaries, NOT secure signatures by
    themselves: do not wire user/model-supplied callbacks in production.
    """

    def __init__(
        self, db_path: Path | str, *,
        owner_verifier: Callable[[str, str, str], bool] | None = None,
        executor_verifier: Callable[[str, str], bool] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self._owner_verifier = owner_verifier
        self._executor_verifier = executor_verifier
        self._clock = clock or time.time
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # PR-A's hierarchy uses exactly the same DB and is inserted atomically
        # on approval; draft agents have NO spendable budget scope.
        BudgetGuard(self.db_path)
        with self._transaction() as conn:
            conn.executescript(_SCHEMA)

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _one(self, table: str, key: str, value: str) -> sqlite3.Row | None:
        # table/key are fixed internal constants, never user input.
        conn = self._connection()
        try:
            return conn.execute(
                f"SELECT * FROM {table} WHERE {key}=?", (value,)
            ).fetchone()
        finally:
            conn.close()

    def _audit(
        self, conn: sqlite3.Connection, agent_id: str,
        run_id: str | None, kind: str,
    ) -> None:
        # Structured event names only; never store prompts, approvals or secrets.
        conn.execute(
            "INSERT INTO fabric_agent_events(agent_id,run_id,kind,created_at)"
            " VALUES(?,?,?,?)",
            (agent_id, run_id, kind, self._clock()),
        )

    def _owner_allowed(self, agent: sqlite3.Row, proof: str) -> bool:
        return bool(
            self._owner_verifier is not None
            and isinstance(proof, str) and proof
            and self._owner_verifier(
                agent["agent_id"], agent["proposal_hash"], proof
            )
        )

    def _executor_allowed(self, run_id: str, proof: str) -> bool:
        return bool(
            self._executor_verifier is not None
            and isinstance(proof, str) and proof
            and self._executor_verifier(run_id, proof)
        )

    def propose(
        self, agent_id: str, proposal_key: str, role: str,
        allowed_tools: tuple[str, ...] | list[str], max_tokens: int,
        max_calls: int, parent_id: str | None = None,
        model_provider: str = "",
    ) -> dict[str, Any]:
        if not _valid_id(agent_id) or not _valid_id(proposal_key):
            raise AgentDenied("invalid_identifier")
        if parent_id is not None and not _valid_id(parent_id):
            raise AgentDenied("invalid_identifier")
        if not isinstance(role, str) or not _ROLE_RE.fullmatch(role):
            raise AgentDenied("invalid_role")
        if type(max_tokens) is not int or type(max_calls) is not int:
            raise AgentDenied("invalid_budget")
        if max_tokens <= 0 or max_calls <= 0:
            raise AgentDenied("invalid_budget")
        if not isinstance(allowed_tools, (tuple, list)):
            raise AgentDenied("invalid_tool")
        if (len(allowed_tools) > 32
                or any(not isinstance(x, str) or not _TOOL_RE.fullmatch(x)
                       for x in allowed_tools)
                or len(set(allowed_tools)) != len(allowed_tools)):
            raise AgentDenied("invalid_tool")
        if not isinstance(model_provider, str):
            raise AgentDenied("invalid_model")
        if model_provider and not _MODEL_RE.fullmatch(model_provider):
            raise AgentDenied("invalid_model")
        compact = "".join(x for x in model_provider.casefold() if x.isalnum())
        if "nemotron" in compact:
            raise AgentDenied("forbidden_model")
        tools = tuple(sorted(allowed_tools))
        canonical = json.dumps(
            [agent_id, parent_id, role, tools, max_tokens, max_calls,
             model_provider], ensure_ascii=True, separators=(",", ":")
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        now = self._clock()
        with self._transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM fabric_agents WHERE agent_id=? OR proposal_key=?",
                (agent_id, proposal_key)
            ).fetchall()
            if existing:
                if (len(existing) == 1 and existing[0]["agent_id"] == agent_id
                        and existing[0]["proposal_key"] == proposal_key
                        and existing[0]["proposal_hash"] == digest):
                    return _agent_view(existing[0])
                raise AgentConflict("proposal_conflict")
            if parent_id is not None:
                current: str | None = parent_id
                depth = 0
                while current is not None:
                    if current == agent_id or depth >= _MAX_DEPTH:
                        raise AgentDenied("invalid_parent_hierarchy")
                    parent = conn.execute(
                        "SELECT * FROM fabric_agents WHERE agent_id=?", (current,)
                    ).fetchone()
                    if parent is None or parent["state"] != "approved":
                        raise AgentDenied("parent_not_approved")
                    if depth == 0:
                        if not set(tools).issubset(set(json.loads(parent["tools_json"]))):
                            raise AgentDenied("permissions_exceed_parent")
                        if max_tokens > parent["max_tokens"] or max_calls > parent["max_calls"]:
                            raise AgentDenied("budget_exceeds_parent")
                    current = parent["parent_id"]
                    depth += 1
            conn.execute(
                "INSERT INTO fabric_agents(agent_id,proposal_key,proposal_hash,"
                "parent_id,role,tools_json,model_provider,max_tokens,max_calls,"
                "state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,'draft',?,?)",
                (agent_id, proposal_key, digest, parent_id, role,
                 json.dumps(tools), model_provider, max_tokens, max_calls, now, now)
            )
            self._audit(conn, agent_id, None, "agent.proposed")
            return _agent_view(conn.execute(
                "SELECT * FROM fabric_agents WHERE agent_id=?", (agent_id,)
            ).fetchone())

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        if not _valid_id(agent_id):
            raise AgentDenied("invalid_identifier")
        row = self._one("fabric_agents", "agent_id", agent_id)
        if row is None:
            raise AgentDenied("unknown_agent")
        return _agent_view(row)

    def approve(self, agent_id: str, *, proof: str) -> None:
        with self._transaction() as conn:
            agent = conn.execute(
                "SELECT * FROM fabric_agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if agent is None:
                raise AgentDenied("unknown_agent")
            if agent["state"] != "draft":
                raise AgentConflict("already_approved_or_revoked")
            if not self._owner_allowed(agent, proof):
                raise AgentDenied("owner_authorization_required")
            parent_scope = None
            if agent["parent_id"] is not None:
                p = conn.execute(
                    "SELECT state FROM fabric_agents WHERE agent_id=?",
                    (agent["parent_id"],)
                ).fetchone()
                if p is None or p["state"] != "approved":
                    raise AgentDenied("parent_not_approved")
                parent_scope = "agent:" + agent["parent_id"]
            # Same transaction as approval. Nothing is spendable until approved.
            conn.execute(
                "INSERT INTO fabric_scopes(scope_id,parent_scope_id,max_tokens,max_calls)"
                " VALUES(?,?,?,?)",
                ("agent:" + agent_id, parent_scope,
                 agent["max_tokens"], agent["max_calls"])
            )
            conn.execute(
                "UPDATE fabric_agents SET state='approved',updated_at=? WHERE agent_id=?",
                (self._clock(), agent_id)
            )
            self._audit(conn, agent_id, None, "agent.approved")

    def create_run(
        self, agent_id: str, run_id: str, request_key: str, input_sha256: str,
    ) -> dict[str, Any]:
        if not all(_valid_id(value) for value in (agent_id, run_id, request_key)):
            raise AgentDenied("invalid_identifier")
        if not _valid_digest(input_sha256):
            raise AgentDenied("invalid_input_digest")
        with self._transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM fabric_agent_runs WHERE run_id=? OR request_key=?",
                (run_id, request_key)
            ).fetchall()
            if existing:
                if (len(existing) == 1 and existing[0]["run_id"] == run_id
                        and existing[0]["request_key"] == request_key
                        and existing[0]["agent_id"] == agent_id
                        and existing[0]["input_sha256"] == input_sha256):
                    return _run_view(existing[0])
                raise AgentConflict("request_conflict")
            # Reserve one permanent dispatch slot against every ancestor,
            # not just the immediate agent. Never refund on failure or
            # uncertain outcomes: a replay could duplicate external effects.
            ancestors: list[str] = []
            current: str | None = agent_id
            while current is not None:
                if len(ancestors) >= _MAX_DEPTH:
                    raise AgentDenied("invalid_parent_hierarchy")
                agent = conn.execute(
                    "SELECT parent_id,state,max_calls,reserved_runs FROM fabric_agents "
                    "WHERE agent_id=?", (current,)
                ).fetchone()
                if agent is None or agent["state"] != "approved":
                    raise AgentDenied("not_approved")
                if agent["reserved_runs"] >= agent["max_calls"]:
                    raise AgentDenied("run_budget_exhausted")
                ancestors.append(current)
                current = agent["parent_id"]
            now = self._clock()
            for ancestor_id in ancestors:
                conn.execute(
                    "UPDATE fabric_agents SET reserved_runs=reserved_runs+1,"
                    "updated_at=? WHERE agent_id=?", (now, ancestor_id)
                )
            conn.execute(
                "INSERT INTO fabric_agent_runs(run_id,agent_id,request_key,input_sha256,"
                "state,created_at,updated_at) VALUES(?,?,?,?,'queued',?,?)",
                (run_id, agent_id, request_key, input_sha256, now, now)
            )
            self._audit(conn, agent_id, run_id, "run.queued")
            return _run_view(conn.execute(
                "SELECT * FROM fabric_agent_runs WHERE run_id=?", (run_id,)
            ).fetchone())

    def get_run(self, run_id: str) -> dict[str, Any]:
        if not _valid_id(run_id):
            raise AgentDenied("invalid_identifier")
        row = self._one("fabric_agent_runs", "run_id", run_id)
        if row is None:
            raise AgentDenied("unknown_run")
        return _run_view(row)

    def claim(self, run_id: str, *, proof: str, lease_seconds: int = 60) -> str:
        if not _valid_id(run_id):
            raise AgentDenied("invalid_identifier")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise AgentDenied("invalid_lease")
        if not self._executor_allowed(run_id, proof):
            raise AgentDenied("executor_authorization_required")
        self.expire_leases()
        with self._transaction() as conn:
            run = conn.execute(
                "SELECT * FROM fabric_agent_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if run is None:
                raise AgentDenied("unknown_run")
            if run["state"] != "queued":
                if run["state"] == "leased":
                    raise AgentConflict("already_claimed")
                raise AgentConflict("not_queued")
            agent = conn.execute(
                "SELECT state FROM fabric_agents WHERE agent_id=?",
                (run["agent_id"],)
            ).fetchone()
            if agent is None or agent["state"] != "approved":
                raise AgentDenied("not_approved")
            token = secrets.token_hex(32)
            now = self._clock()
            conn.execute(
                "UPDATE fabric_agent_runs SET state='leased',lease_token=?,"
                "lease_expires_at=?,updated_at=? WHERE run_id=?",
                (token, now + lease_seconds, now, run_id)
            )
            self._audit(conn, run["agent_id"], run_id, "run.leased")
            return token

    def _get_lease(
        self, conn: sqlite3.Connection, run_id: str, lease_token: str,
    ) -> sqlite3.Row:
        run = conn.execute(
            "SELECT * FROM fabric_agent_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if run is None or run["state"] != "leased":
            raise AgentConflict("not_leased")
        if (not isinstance(lease_token, str)
                or not secrets.compare_digest(str(run["lease_token"]), lease_token)):
            raise AgentDenied("lease_token_invalid")
        return run

    def checkpoint(
        self, run_id: str, lease_token: str, *, seq: int,
        payload: dict[str, Any],
    ) -> None:
        if not isinstance(payload, dict) or type(seq) is not int or seq < 1:
            raise AgentDenied("invalid_checkpoint")
        try:
            serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise AgentDenied("invalid_checkpoint") from exc
        if len(serialized.encode("utf-8")) > _MAX_CHECKPOINT_BYTES:
            raise AgentDenied("invalid_checkpoint")
        self.expire_leases()
        with self._transaction() as conn:
            run = self._get_lease(conn, run_id, lease_token)
            if run["cancel_requested"]:
                raise AgentDenied("cancellation_pending")
            if seq != run["checkpoint_seq"] + 1:
                raise AgentConflict("stale_checkpoint")
            conn.execute(
                "UPDATE fabric_agent_runs SET checkpoint_json=?,checkpoint_seq=?,"
                "updated_at=? WHERE run_id=?",
                (serialized, seq, self._clock(), run_id)
            )
            self._audit(conn, run["agent_id"], run_id, "run.checkpoint")

    def finish(
        self, run_id: str, lease_token: str, *,
        result_sha256: str, success: bool = True,
    ) -> None:
        if not _valid_digest(result_sha256) or type(success) is not bool:
            raise AgentDenied("invalid_result_digest")
        self.expire_leases()
        with self._transaction() as conn:
            run = self._get_lease(conn, run_id, lease_token)
            if run["cancel_requested"]:
                raise AgentDenied("cancellation_pending")
            outcome = "completed" if success else "failed"
            conn.execute(
                "UPDATE fabric_agent_runs SET state=?,result_sha256=?,lease_token=NULL,"
                "lease_expires_at=NULL,updated_at=? WHERE run_id=?",
                (outcome, result_sha256, self._clock(), run_id)
            )
            self._audit(conn, run["agent_id"], run_id, "run." + outcome)

    def expire_leases(self) -> int:
        """Only quarantine expired runs as uncertain; never automatically replay."""
        with self._transaction() as conn:
            now = self._clock()
            expired = conn.execute(
                "SELECT run_id,agent_id FROM fabric_agent_runs "
                "WHERE state='leased' AND lease_expires_at<=?",
                (now,)
            ).fetchall()
            for item in expired:
                conn.execute(
                    "UPDATE fabric_agent_runs SET state='uncertain',lease_token=NULL,"
                    "lease_expires_at=NULL,updated_at=? WHERE run_id=?",
                    (now, item["run_id"])
                )
                self._audit(conn, item["agent_id"], item["run_id"], "run.uncertain")
            return len(expired)

    def cancel_agent(self, agent_id: str, *, proof: str) -> None:
        with self._transaction() as conn:
            agent = conn.execute(
                "SELECT * FROM fabric_agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if agent is None:
                raise AgentDenied("unknown_agent")
            if not self._owner_allowed(agent, proof):
                raise AgentDenied("owner_authorization_required")
            descendants = conn.execute(
                "WITH RECURSIVE family(agent_id) AS ("
                " SELECT agent_id FROM fabric_agents WHERE agent_id=?"
                " UNION ALL SELECT a.agent_id FROM fabric_agents a"
                " JOIN family f ON a.parent_id=f.agent_id)"
                " SELECT agent_id FROM family", (agent_id,)
            ).fetchall()
            now = self._clock()
            for item in descendants:
                aid = item["agent_id"]
                conn.execute(
                    "UPDATE fabric_agents SET state='revoked',updated_at=? WHERE agent_id=?",
                    (now, aid)
                )
                self._audit(conn, aid, None, "agent.revoked")
                queued = conn.execute(
                    "SELECT run_id FROM fabric_agent_runs WHERE agent_id=? AND state='queued'",
                    (aid,)
                ).fetchall()
                for run in queued:
                    conn.execute(
                        "UPDATE fabric_agent_runs SET state='cancelled',updated_at=? "
                        "WHERE run_id=?", (now, run["run_id"])
                    )
                    self._audit(conn, aid, run["run_id"], "run.cancelled")
                running = conn.execute(
                    "SELECT run_id FROM fabric_agent_runs WHERE agent_id=? AND state='leased'",
                    (aid,)
                ).fetchall()
                for run in running:
                    conn.execute(
                        "UPDATE fabric_agent_runs SET cancel_requested=1,updated_at=? "
                        "WHERE run_id=?", (now, run["run_id"])
                    )
                    self._audit(conn, aid, run["run_id"], "run.cancellation_requested")

    def ack_cancel(self, run_id: str, lease_token: str) -> None:
        self.expire_leases()
        with self._transaction() as conn:
            run = self._get_lease(conn, run_id, lease_token)
            if not run["cancel_requested"]:
                raise AgentDenied("cancellation_not_requested")
            conn.execute(
                "UPDATE fabric_agent_runs SET state='cancelled',lease_token=NULL,"
                "lease_expires_at=NULL,updated_at=? WHERE run_id=?",
                (self._clock(), run_id)
            )
            self._audit(conn, run["agent_id"], run_id, "run.cancelled")

    def reconcile(
        self, run_id: str, *, proof: str,
        result_sha256: str, success: bool,
    ) -> None:
        if not _valid_digest(result_sha256) or type(success) is not bool:
            raise AgentDenied("invalid_result_digest")
        with self._transaction() as conn:
            run = conn.execute(
                "SELECT * FROM fabric_agent_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if run is None:
                raise AgentDenied("unknown_run")
            agent = conn.execute(
                "SELECT * FROM fabric_agents WHERE agent_id=?", (run["agent_id"],)
            ).fetchone()
            if not self._owner_allowed(agent, proof):
                raise AgentDenied("owner_authorization_required")
            if run["state"] != "uncertain":
                raise AgentConflict("not_uncertain")
            state = "completed" if success else "failed"
            conn.execute(
                "UPDATE fabric_agent_runs SET state=?,result_sha256=?,updated_at=? "
                "WHERE run_id=?", (state, result_sha256, self._clock(), run_id)
            )
            self._audit(conn, run["agent_id"], run_id, "run.owner_reconciled")

    def inspect_checkpoint(self, run_id: str, *, proof: str) -> dict[str, Any]:
        """Read durable checkpoint only through the trusted owner verifier."""
        if not _valid_id(run_id):
            raise AgentDenied("invalid_identifier")
        conn = self._connection()
        try:
            run = conn.execute(
                "SELECT * FROM fabric_agent_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if run is None:
                raise AgentDenied("unknown_run")
            agent = conn.execute(
                "SELECT * FROM fabric_agents WHERE agent_id=?",
                (run["agent_id"],)
            ).fetchone()
            if agent is None or not self._owner_allowed(agent, proof):
                raise AgentDenied("owner_authorization_required")
            return {
                "seq": run["checkpoint_seq"],
                "checkpoint": json.loads(run["checkpoint_json"]),
            }
        finally:
            conn.close()

    def audit_events(self, run_id: str) -> list[dict[str, Any]]:
        if not _valid_id(run_id):
            raise AgentDenied("invalid_identifier")
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT seq,agent_id,run_id,kind,created_at "
                "FROM fabric_agent_events WHERE run_id=? ORDER BY seq", (run_id,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
