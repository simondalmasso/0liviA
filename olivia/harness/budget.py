"""Atomic SQLite upper-bound reservations for nested Agent Fabric budgets.

Reservations are pessimistic: a failed or uncertain request does not release
tokens or daily call capacity. This is a local limit, NOT proof of provider
billing eligibility. ModelRegistry admission must precede every reservation.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from .model_registry import ModelAdmission


class BudgetDenied(RuntimeError):
    pass


@dataclass(frozen=True)
class BudgetReceipt:
    request_id: str
    scope_id: str
    provider: str
    model: str
    reserved_tokens: int
    state: str = "reserved"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS fabric_scopes(
  scope_id TEXT PRIMARY KEY,
  parent_scope_id TEXT REFERENCES fabric_scopes(scope_id),
  max_tokens INTEGER NOT NULL CHECK(max_tokens>0),
  max_calls INTEGER NOT NULL CHECK(max_calls>0),
  reserved_tokens INTEGER NOT NULL DEFAULT 0,
  reserved_calls INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fabric_reservations(
  request_id TEXT PRIMARY KEY,
  scope_id TEXT NOT NULL REFERENCES fabric_scopes(scope_id),
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  reserved_tokens INTEGER NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('reserved','completed','uncertain')),
  created_day TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fabric_daily_limits(
  day TEXT NOT NULL,
  account_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  calls INTEGER NOT NULL,
  PRIMARY KEY(day,account_id,provider,model)
);
CREATE TABLE IF NOT EXISTS fabric_shared_pool_limits(
  day TEXT NOT NULL,
  account_id TEXT NOT NULL,
  billing_pool TEXT NOT NULL,
  max_units INTEGER NOT NULL,
  external_floor_units INTEGER NOT NULL,
  reserved_units INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(day,account_id,billing_pool)
);
"""


class BudgetGuard:
    def __init__(self, db_path: Path, *, today: date | None = None) -> None:
        self.db_path = Path(db_path)
        self._today = today
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10, isolation_level=None)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def create_scope(
        self, scope_id: str, max_tokens: int, max_calls: int,
        parent_scope_id: str | None = None,
    ) -> None:
        if not scope_id or scope_id == parent_scope_id:
            raise BudgetDenied("invalid_scope")
        if any(type(v) is not int or v <= 0 for v in (max_tokens, max_calls)):
            raise BudgetDenied("invalid_scope_limits")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                "SELECT parent_scope_id,max_tokens,max_calls FROM fabric_scopes WHERE scope_id=?",
                (scope_id,)
            ).fetchone()
            if prior is not None:
                if prior != (parent_scope_id, max_tokens, max_calls):
                    raise BudgetDenied("cannot_change_existing_scope")
                conn.commit()
                return
            if parent_scope_id is not None:
                parent = conn.execute(
                    "SELECT max_tokens,max_calls FROM fabric_scopes WHERE scope_id=?",
                    (parent_scope_id,)
                ).fetchone()
                if parent is None:
                    raise BudgetDenied("parent_scope_not_found")
                if max_tokens > parent[0] or max_calls > parent[1]:
                    raise BudgetDenied("child_scope_exceeds_parent")
            conn.execute(
                "INSERT INTO fabric_scopes(scope_id,parent_scope_id,max_tokens,max_calls) VALUES(?,?,?,?)",
                (scope_id, parent_scope_id, max_tokens, max_calls)
            )
            conn.commit()

    def reserve(self, admission: ModelAdmission, *, request_id: str, scope_id: str) -> BudgetReceipt:
        if not admission.allowed or admission.reason != "permitted":
            raise BudgetDenied("model_not_admitted")
        if not request_id or not scope_id:
            raise BudgetDenied("missing_reservation_identity")
        tokens = admission.reserved_input_tokens + admission.reserved_output_tokens
        if (not admission.account_id or not admission.provider or not admission.model
                or any(type(x) is not int or x <= 0 for x in (
                    admission.reserved_input_tokens,
                    admission.reserved_output_tokens,
                    admission.daily_request_cap,
                ))):
            raise BudgetDenied("invalid_model_reservation")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM fabric_reservations WHERE request_id=?", (request_id,)).fetchone():
                raise BudgetDenied("duplicate_or_uncertain_request")
            chain: list[tuple[str, int, int, int, int]] = []
            seen: set[str] = set()
            current: str | None = scope_id
            while current is not None:
                if current in seen or len(chain) >= 16:
                    raise BudgetDenied("invalid_scope_hierarchy")
                seen.add(current)
                row = conn.execute(
                    "SELECT scope_id,parent_scope_id,max_tokens,max_calls,reserved_tokens,reserved_calls "
                    "FROM fabric_scopes WHERE scope_id=?", (current,)
                ).fetchone()
                if row is None:
                    raise BudgetDenied("unknown_scope")
                _, parent, max_tokens, max_calls, reserved_tokens, reserved_calls = row
                if reserved_tokens + tokens > max_tokens or reserved_calls + 1 > max_calls:
                    raise BudgetDenied("scope_budget_exhausted")
                chain.append((current, max_tokens, max_calls, reserved_tokens, reserved_calls))
                current = parent
            today = (self._today or datetime.now(timezone.utc).date()).isoformat()
            key = (today, admission.account_id, admission.provider, admission.model)
            daily = conn.execute(
                "SELECT calls FROM fabric_daily_limits "
                "WHERE day=? AND account_id=? AND provider=? AND model=?", key
            ).fetchone()
            if daily is not None and daily[0] >= admission.daily_request_cap:
                raise BudgetDenied("daily_request_budget_exhausted")
            shared_update = None
            if admission.billing_pool:
                if (admission.usage_day is None or admission.usage_day.isoformat() != today
                        or any(type(v) is not int or v <= 0 for v in (
                            admission.shared_daily_cap_units, admission.shared_request_units,
                        ))
                        or type(admission.external_usage_units) is not int
                        or admission.external_usage_units < 0):
                    raise BudgetDenied("shared_account_evidence_missing_or_stale")
                pool_key = (today, admission.account_id, admission.billing_pool)
                prior = conn.execute(
                    "SELECT max_units,external_floor_units,reserved_units "
                    "FROM fabric_shared_pool_limits WHERE day=? AND account_id=? AND billing_pool=?",
                    pool_key
                ).fetchone()
                effective_cap = min(prior[0], admission.shared_daily_cap_units) if prior else admission.shared_daily_cap_units
                external_floor = max(prior[1], admission.external_usage_units) if prior else admission.external_usage_units
                reserved = prior[2] if prior else 0
                if external_floor + reserved + admission.shared_request_units > effective_cap:
                    raise BudgetDenied("shared_account_budget_exhausted")
                shared_update = (pool_key, effective_cap, external_floor, reserved)
            elif admission.shared_request_units or admission.shared_daily_cap_units:
                raise BudgetDenied("shared_pool_identity_missing")
            for item in chain:
                conn.execute(
                    "UPDATE fabric_scopes SET reserved_tokens=reserved_tokens+?, "
                    "reserved_calls=reserved_calls+1 WHERE scope_id=?",
                    (tokens, item[0])
                )
            if shared_update is not None:
                pool_key, cap, floor, reserved = shared_update
                conn.execute(
                    "INSERT INTO fabric_shared_pool_limits(day,account_id,billing_pool,max_units,"
                    "external_floor_units,reserved_units) VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(day,account_id,billing_pool) DO UPDATE SET "
                    "max_units=excluded.max_units, external_floor_units=excluded.external_floor_units,"
                    "reserved_units=excluded.reserved_units",
                    (*pool_key, cap, floor, reserved + admission.shared_request_units)
                )
            conn.execute(
                "INSERT INTO fabric_daily_limits(day,account_id,provider,model,calls) "
                "VALUES(?,?,?,?,1) ON CONFLICT(day,account_id,provider,model) "
                "DO UPDATE SET calls=calls+1", key
            )
            conn.execute(
                "INSERT INTO fabric_reservations(request_id,scope_id,provider,model,reserved_tokens,state,created_day) "
                "VALUES(?,?,?,?,?,'reserved',?)",
                (request_id, scope_id, admission.provider, admission.model, tokens, today)
            )
            conn.commit()
        return BudgetReceipt(request_id, scope_id, admission.provider, admission.model, tokens)

    def settle(self, request_id: str, *, uncertain: bool = False) -> None:
        """No refunds, including on transport failure or unknown outcomes."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT state FROM fabric_reservations WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                raise BudgetDenied("unknown_reservation")
            if row[0] != "reserved":
                raise BudgetDenied("reservation_already_settled")
            conn.execute(
                "UPDATE fabric_reservations SET state=? WHERE request_id=?",
                ("uncertain" if uncertain else "completed", request_id)
            )
            conn.commit()

    def inspect_scope(self, scope_id: str) -> dict[str, int]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT max_tokens,max_calls,reserved_tokens,reserved_calls "
                "FROM fabric_scopes WHERE scope_id=?", (scope_id,)
            ).fetchone()
        if row is None:
            raise BudgetDenied("unknown_scope")
        return dict(zip(("max_tokens", "max_calls", "reserved_tokens", "reserved_calls"), row))
