"""Agent Fabric PR-C1: zero-default, durable, at-most-once tool gateway.

Does not install any live adapter, invoke models, poll a queue, create a
sandbox, authenticate an owner, or grant network/file permissions. Production
tool adapters belong to an independently audited PR-C2.
"""
from __future__ import annotations

import inspect
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping

from .agents import AgentFabric

_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,79}$")
_TOOL_RE = re.compile(r"^[a-z][a-z0-9._:-]{0,63}$")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_READ_ACTIONS = frozenset({"get", "list", "inspect", "search", "head"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fabric_tool_actions (
  request_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES fabric_agent_runs(run_id),
  tool TEXT NOT NULL,
  action TEXT NOT NULL,
  args_sha256 TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('reserved','completed','accepted','uncertain','failed')),
  evidence_sha256 TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fabric_tool_actions_run
 ON fabric_tool_actions(run_id,created_at);
CREATE TABLE IF NOT EXISTS fabric_tool_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fabric_tool_events_run
 ON fabric_tool_events(run_id,seq);
"""


class ToolDenied(RuntimeError):
    """Tool capability, approval, sandbox or budget check failed."""


class ToolConflict(RuntimeError):
    """A previous or uncertain effect cannot be re-issued."""


class ToolOutcomeUnknown(RuntimeError):
    """An adapter might have performed an external effect; never retry."""


@dataclass(frozen=True)
class ToolRule:
    name: str
    actions: frozenset[str]
    read_only: bool
    sandbox_kind: str = ""

    def __post_init__(self) -> None:
        if (not isinstance(self.name, str)
                or not _TOOL_RE.fullmatch(self.name)
                or type(self.read_only) is not bool
                or not isinstance(self.actions, frozenset)
                or not self.actions
                or not all(isinstance(a, str) and _TOOL_RE.fullmatch(a)
                           for a in self.actions)):
            raise ValueError("invalid_tool_policy")
        if self.read_only:
            if not self.actions.issubset(_READ_ACTIONS) or self.sandbox_kind:
                raise ValueError("invalid_read_policy")
        else:
            if not isinstance(self.sandbox_kind, str) or not self.sandbox_kind:
                raise ValueError("write_tool_requires_sandbox")
            if not _TOOL_RE.fullmatch(self.sandbox_kind):
                raise ValueError("invalid_sandbox_kind")


@dataclass(frozen=True)
class ToolReceipt:
    state: str
    evidence_sha256: str

    def __post_init__(self) -> None:
        if self.state not in {"completed", "accepted"}:
            raise ValueError("invalid_receipt_state")
        if not isinstance(self.evidence_sha256, str) or not _SHA_RE.fullmatch(
            self.evidence_sha256
        ):
            raise ValueError("invalid_receipt_evidence")


class ToolGateway:
    """Explicitly registered, permission-bounded adapters only.

    owner_action_verifier(run_id, tool, action, args_sha256, opaque_proof)
    and sandbox_verifier(sandbox_kind, sandbox_id, tool, opaque_proof)
    must be implemented by trusted Core/sandbox attestors; by default
    they deny writes. A model cannot supply callbacks through prompts.
    """

    def __init__(
        self,
        fabric: AgentFabric,
        tools: Mapping[str, tuple[ToolRule, Any]] | None = None,
        *,
        owner_action_verifier: Callable[[str, str, str, str, str], bool] | None = None,
        sandbox_verifier: Callable[[str, str, str, str], bool] | None = None,
        max_actions_per_run: int = 4,
    ) -> None:
        if not isinstance(fabric, AgentFabric):
            raise ValueError("invalid_fabric")
        if (type(max_actions_per_run) is not int
                or not 1 <= max_actions_per_run <= 16):
            raise ValueError("invalid_action_limit")
        self.fabric = fabric
        self._owner_action_verifier = owner_action_verifier
        self._sandbox_verifier = sandbox_verifier
        self._max_actions_per_run = max_actions_per_run
        self._tools: dict[str, tuple[ToolRule, Any]] = {}
        for key, item in (tools or {}).items():
            if (not isinstance(key, str)
                    or not isinstance(item, tuple) or len(item) != 2
                    or not isinstance(item[0], ToolRule)
                    or item[0].name != key
                    or not inspect.iscoroutinefunction(
                        getattr(item[1], "invoke", None)
                    )):
                raise ValueError("invalid_tool_registration")
            self._tools[key] = item
        with self._transaction() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.fabric.db_path, timeout=10, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _audit(
        self, conn: sqlite3.Connection,
        request_id: str, run_id: str, kind: str,
    ) -> None:
        # Event names only, not user args, proofs, secrets or returned payloads.
        conn.execute(
            "INSERT INTO fabric_tool_events(request_id,run_id,kind,created_at)"
            " VALUES(?,?,?,?)",
            (request_id, run_id, kind, self.fabric._clock())
        )

    def _owner_allowed(
        self, run_id: str, tool: str, action: str,
        digest: str, proof: str,
    ) -> bool:
        return bool(
            self._owner_action_verifier is not None
            and isinstance(proof, str) and proof
            and self._owner_action_verifier(
                run_id, tool, action, digest, proof
            )
        )

    def _sandbox_allowed(
        self, kind: str, sandbox_id: str, tool: str, proof: str,
    ) -> bool:
        return bool(
            self._sandbox_verifier is not None
            and isinstance(sandbox_id, str) and bool(_ID_RE.fullmatch(sandbox_id))
            and isinstance(proof, str) and proof
            and self._sandbox_verifier(kind, sandbox_id, tool, proof)
        )

    def _reserve(
        self, run_id: str, lease_token: str, request_id: str,
        tool: str, action: str, args_sha256: str,
        approval_proof: str, sandbox_id: str, sandbox_proof: str,
    ) -> None:
        if not all(isinstance(x, str) and bool(_ID_RE.fullmatch(x))
                   for x in (run_id, request_id)):
            raise ToolDenied("invalid_identifier")
        if not isinstance(args_sha256, str) or not _SHA_RE.fullmatch(args_sha256):
            raise ToolDenied("invalid_argument_digest")
        with self._transaction() as conn:
            if conn.execute(
                "SELECT 1 FROM fabric_tool_actions WHERE request_id=?",
                (request_id,)
            ).fetchone():
                raise ToolConflict("duplicate_or_uncertain_action")
            binding = self._tools.get(tool)
            if binding is None:
                raise ToolDenied("unregistered_tool")
            rule = binding[0]
            run = conn.execute(
                "SELECT * FROM fabric_agent_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if run is None or run["state"] != "leased":
                raise ToolDenied("run_not_leased")
            agent = conn.execute(
                "SELECT * FROM fabric_agents WHERE agent_id=?",
                (run["agent_id"],)
            ).fetchone()
            if agent is None or agent["state"] != "approved":
                raise ToolDenied("agent_not_approved")
            if run["cancel_requested"]:
                raise ToolDenied("cancellation_pending")
            if run["lease_expires_at"] is None or (
                run["lease_expires_at"] <= self.fabric._clock()
            ):
                raise ToolDenied("lease_expired")
            if (not isinstance(lease_token, str)
                    or not secrets.compare_digest(
                        str(run["lease_token"]), lease_token
                    )):
                raise ToolDenied("lease_token_invalid")
            # AgentSpec permissions are owner-approved and inherited by children.
            import json
            if tool not in json.loads(agent["tools_json"]):
                raise ToolDenied("tool_not_permitted")
            if action not in rule.actions:
                raise ToolDenied("action_not_permitted")
            if not rule.read_only:
                if not self._owner_allowed(
                    run_id, tool, action, args_sha256, approval_proof
                ):
                    raise ToolDenied("owner_action_approval_required")
                if not self._sandbox_allowed(
                    rule.sandbox_kind, sandbox_id, tool, sandbox_proof
                ):
                    raise ToolDenied("sandbox_attestation_required")
            used = conn.execute(
                "SELECT COUNT(*) FROM fabric_tool_actions WHERE run_id=?",
                (run_id,)
            ).fetchone()[0]
            if used >= self._max_actions_per_run:
                raise ToolDenied("tool_action_budget_exhausted")
            now = self.fabric._clock()
            conn.execute(
                "INSERT INTO fabric_tool_actions(request_id,run_id,tool,action,"
                "args_sha256,state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,'reserved',?,?)",
                (request_id, run_id, tool, action, args_sha256, now, now)
            )
            self._audit(conn, request_id, run_id, "tool.reserved")

    def _settle(
        self, request_id: str, state: str,
        evidence_sha256: str | None = None,
    ) -> None:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT run_id,state FROM fabric_tool_actions WHERE request_id=?",
                (request_id,)
            ).fetchone()
            if row is None or row["state"] != "reserved":
                raise ToolConflict("action_already_finalized")
            conn.execute(
                "UPDATE fabric_tool_actions SET state=?,evidence_sha256=?,"
                "updated_at=? WHERE request_id=?",
                (state, evidence_sha256, self.fabric._clock(), request_id)
            )
            self._audit(conn, request_id, row["run_id"], "tool." + state)

    async def execute(
        self, run_id: str, lease_token: str, request_id: str,
        tool: str, action: str, args_sha256: str, *,
        approval_proof: str = "", sandbox_id: str = "",
        sandbox_proof: str = "",
    ) -> ToolReceipt:
        self._reserve(
            run_id, lease_token, request_id, tool, action, args_sha256,
            approval_proof, sandbox_id, sandbox_proof,
        )
        adapter = self._tools[tool][1]
        try:
            received = await adapter.invoke(
                action=action, request_id=request_id,
                args_sha256=args_sha256, sandbox_id=sandbox_id,
            )
            if not isinstance(received, ToolReceipt):
                raise ValueError("unverified_adapter_receipt")
        except BaseException as exc:
            # Any exception or cancellation may follow an external side effect.
            self._settle(request_id, "uncertain")
            raise ToolOutcomeUnknown("remote_outcome_uncertain") from exc
        self._settle(request_id, received.state, received.evidence_sha256)
        return received

    def get_action(self, request_id: str) -> dict[str, Any]:
        if not isinstance(request_id, str) or not _ID_RE.fullmatch(request_id):
            raise ToolDenied("invalid_identifier")
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT request_id,run_id,tool,action,args_sha256,state,evidence_sha256"
                " FROM fabric_tool_actions WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is None:
                raise ToolDenied("unknown_action")
            return dict(row)
        finally:
            conn.close()

    def audit_events(self, run_id: str) -> list[dict[str, Any]]:
        if not isinstance(run_id, str) or not _ID_RE.fullmatch(run_id):
            raise ToolDenied("invalid_identifier")
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT seq,request_id,run_id,kind,created_at FROM fabric_tool_events"
                " WHERE run_id=? ORDER BY seq", (run_id,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def reconcile(
        self, request_id: str, approval_proof: str,
        evidence_sha256: str, *, success: bool,
    ) -> None:
        if (not isinstance(evidence_sha256, str)
                or not _SHA_RE.fullmatch(evidence_sha256)
                or type(success) is not bool):
            raise ToolDenied("invalid_evidence_digest")
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM fabric_tool_actions WHERE request_id=?",
                (request_id,)
            ).fetchone()
            if row is None:
                raise ToolDenied("unknown_action")
            if not self._owner_allowed(
                row["run_id"], row["tool"], row["action"],
                row["args_sha256"], approval_proof
            ):
                raise ToolDenied("owner_action_approval_required")
            if row["state"] not in {"uncertain", "accepted"}:
                raise ToolConflict("action_not_uncertain")
            state = "completed" if success else "failed"
            conn.execute(
                "UPDATE fabric_tool_actions SET state=?,evidence_sha256=?,"
                "updated_at=? WHERE request_id=?",
                (state, evidence_sha256, self.fabric._clock(), request_id)
            )
            self._audit(
                conn, request_id, row["run_id"], "tool.owner_reconciled"
            )
