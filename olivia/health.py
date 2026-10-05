"""Provider health: half-open circuit breaker, backoff and quota state.

`provider_health` is the single provider-reliability state table. It lives in
the same SQLite database as the rest of the core, while this module owns its
transitions. State changes are transaction-guarded and tolerate day rollover,
clock skew and abandoned probes.
"""

from __future__ import annotations

import contextlib
import random
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

_SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_health (
    provider TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'closed',
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    open_count INTEGER NOT NULL DEFAULT 0,
    open_until REAL NOT NULL DEFAULT 0,
    probe_in_flight INTEGER NOT NULL DEFAULT 0,
    probe_lease_until REAL NOT NULL DEFAULT 0,
    day TEXT NOT NULL DEFAULT '',
    daily_requests INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    timeout_count INTEGER NOT NULL DEFAULT 0,
    rate_limit_count INTEGER NOT NULL DEFAULT 0,
    empty_count INTEGER NOT NULL DEFAULT 0,
    interrupted_count INTEGER NOT NULL DEFAULT 0,
    last_ttft_ms REAL,
    last_error TEXT,
    last_failure_kind TEXT,
    last_attempt_at REAL,
    updated_at REAL NOT NULL
);
"""


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class FailureKind(str, Enum):
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    EMPTY_STREAM = "empty_stream"
    INTERRUPTED = "interrupted"
    HTTP = "http"
    CONFIG = "config"
    NETWORK = "network"
    UNKNOWN = "unknown"


# Failure kind -> counter column (whitelist, never interpolated from caller input).
KIND_COLUMNS: dict[str, str] = {
    FailureKind.RATE_LIMIT.value: "rate_limit_count",
    FailureKind.TIMEOUT.value: "timeout_count",
    FailureKind.EMPTY_STREAM.value: "empty_count",
    FailureKind.INTERRUPTED.value: "interrupted_count",
}

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/\-]{8,}=*"), "Bearer [redacted]"),
    (re.compile(r"\bsk-[A-Za-z0-9._\-]{6,}"), "[redacted]"),
    (re.compile(r"\b(?:gsk|AIza|hf|ghp|gho|xoxb|xoxp)[A-Za-z0-9._\-]{6,}"), "[redacted]"),
    (re.compile(r"\b[A-Za-z0-9_\-]{40,}\b"), "[redacted]"),
    (
        re.compile(r"(?i)\b(api[_-]?key|secret|token|authorization|password)\b\s*[:=]\s*\"?[^\"\s,}]{4,}"),
        r"\1=[redacted]",
    ),
)


def redact(text: Any, *, max_len: int = 200) -> str:
    """Never let secrets reach telemetry, events or exception messages.

    Strips known key shapes, `Authorization`-style headers, long opaque
    tokens, control characters and newlines, then hard-truncates.
    """
    if text is None:
        return ""
    out = str(text)
    for pattern, repl in _REDACTIONS:
        out = pattern.sub(repl, out)
    out = re.sub(r"[\x00-\x1f\x7f]+", " ", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    if max_len > 0 and len(out) > max_len:
        out = out[: max(0, max_len - 3)] + "..."
    return out


def _kind_value(kind: Any) -> str:
    return kind.value if isinstance(kind, FailureKind) else str(kind)


@dataclass(frozen=True)
class Admission:
    """Result of the breaker + quota gate for one provider attempt."""

    allowed: bool
    state: str
    reason: str
    is_probe: bool = False
    cooldown_remaining_s: float = 0.0
    open_until: float = 0.0
    daily_requests: int = 0
    daily_limit: int = 0


class ProviderHealth:
    def __init__(
        self,
        db_path: Path | str,
        settings: Any,
        *,
        now: Callable[[], float] | None = None,
        jitter: Callable[[], float] | None = None,
    ) -> None:
        self.settings = settings
        self.path = Path(db_path) if str(db_path) != ":memory:" else Path(":memory:")
        self._now = now or time.time
        self._jitter = jitter or (lambda: random.uniform(-1.0, 1.0))
        self._lock = threading.RLock()
        if str(db_path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(db_path),
            timeout=5,
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)

    @classmethod
    def from_store(cls, store: Any, settings: Any, *, now: Callable[[], float] | None = None,
                   jitter: Callable[[], float] | None = None) -> "ProviderHealth":
        """Reuse the app's SQLite file; degrade to in-memory if a stub store is passed."""
        path = getattr(store, "path", None)
        return cls(path if path is not None else ":memory:", settings, now=now, jitter=jitter)

    # ---------------------------------------------------------------- lifecycle
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def now(self) -> float:
        return float(self._now())

    # ------------------------------------------------------------------- day key
    def day_key(self, ts: float | None = None) -> str:
        offset_h = int(getattr(self.settings, "quota_utc_offset_h", 0) or 0)
        stamp = self.now() if ts is None else float(ts)
        return time.strftime("%Y-%m-%d", time.gmtime(stamp + offset_h * 3600))

    # ------------------------------------------------------------------ backoff
    def backoff_s(
        self,
        failures: int,
        *,
        kind: Any = FailureKind.UNKNOWN,
        retry_after_s: float | None = None,
    ) -> float:
        """Per-provider cooldown: exponential, capped, jittered; 429 honours Retry-After."""
        base = float(getattr(self.settings, "circuit_base_s", 15))
        cap = float(getattr(self.settings, "circuit_max_s", 600))
        k = _kind_value(kind)
        n = max(1, int(failures))
        if k == FailureKind.RATE_LIMIT.value:
            asked = max(0.0, float(retry_after_s or 0.0))
            ceiling = max(cap, asked)
            return float(min(max(asked, base), ceiling))
        if k == FailureKind.CONFIG.value:
            return cap
        raw = min(base * (2 ** min(n - 1, 16)), cap)
        ratio = max(0.0, min(1.0, float(getattr(self.settings, "circuit_jitter_ratio", 0.2))))
        if ratio:
            raw = raw + self._jitter() * raw * ratio
        return max(0.1, float(raw))

    # ------------------------------------------------------------------ internals
    def _exec(self, sql: str, args: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, args)

    def _ensure_row(self, provider: str, now: float) -> sqlite3.Row:
        row = self._exec("SELECT * FROM provider_health WHERE provider=?", (provider,)).fetchone()
        if row is None:
            self._exec(
                """INSERT OR IGNORE INTO provider_health(
                       provider,state,consecutive_failures,open_count,open_until,
                       probe_in_flight,probe_lease_until,day,daily_requests,
                       attempt_count,success_count,failure_count,timeout_count,
                       rate_limit_count,empty_count,interrupted_count,updated_at)
                   VALUES(?,?,0,0,0,0,0,?,0,0,0,0,0,0,0,0,?)""",
                (provider, BreakerState.CLOSED.value, self.day_key(now), now),
            )
            row = self._exec("SELECT * FROM provider_health WHERE provider=?", (provider,)).fetchone()
        return row

    def snapshot(self, provider: str) -> dict[str, Any]:
        with self._lock:
            row = self._ensure_row(provider, self.now())
            out = dict(row)
        out["cooldown_remaining_s"] = self.cooldown_remaining_s(out["open_until"])
        return out

    def cooldown_remaining_s(self, open_until: float) -> float:
        return max(0.0, float(open_until) - self.now())

    # ------------------------------------------------------- gate: breaker + quota
    def admit(self, provider: str, *, daily_limit: int = 0) -> Admission:
        """Atomic breaker+quota decision.

        OPEN inside cooldown -> deny. Cooldown elapsed -> transition to HALF_OPEN
        and grant at most `circuit_half_open_probes` probes (lease-bounded, so a
        cancelled/crashed probe cannot wedge the breaker). CLOSED -> allow.
        Quota is consumed only for granted attempts, in the same transaction.
        """
        now = self.now()
        probes_max = max(1, int(getattr(self.settings, "circuit_half_open_probes", 1)))
        lease = max(1.0, float(getattr(self.settings, "probe_lease_s", 90.0)))
        day = self.day_key(now)
        with self._lock:
            self._exec("BEGIN IMMEDIATE")
            try:
                row = self._ensure_row(provider, now)
                daily = int(row["daily_requests"])
                if row["day"] != day or daily < 0:
                    # new day, first use, corrupted counter or clock skew (future day):
                    # reset in the same transaction, never carry a stale counter.
                    self._exec(
                        "UPDATE provider_health SET day=?, daily_requests=0, updated_at=? WHERE provider=?",
                        (day, now, provider),
                    )
                    daily = 0
                state = str(row["state"] or BreakerState.CLOSED.value)
                open_until = float(row["open_until"])
                probes = int(row["probe_in_flight"])
                if probes > 0 and float(row["probe_lease_until"]) <= now:
                    probes = 0  # abandoned probe (cancel/disconnect): do not wedge HALF_OPEN
                    self._exec(
                        "UPDATE provider_health SET probe_in_flight=0, probe_lease_until=0 WHERE provider=?",
                        (provider,),
                    )

                if daily_limit and daily >= int(daily_limit):
                    self._exec("COMMIT")
                    return Admission(False, state, "quota_exhausted", False,
                                     self.cooldown_remaining_s(open_until), open_until, daily, int(daily_limit))

                if state == BreakerState.OPEN.value:
                    if now < open_until:
                        self._exec("COMMIT")
                        return Admission(False, state, "cooldown", False,
                                         open_until - now, open_until, daily, int(daily_limit))
                    state = BreakerState.HALF_OPEN.value
                    self._exec(
                        "UPDATE provider_health SET state=?, open_until=0 WHERE provider=?",
                        (state, provider),
                    )
                elif state == BreakerState.HALF_OPEN.value:
                    if probes >= probes_max:
                        self._exec("COMMIT")
                        return Admission(False, state, "probe_in_flight", False, 0.0, 0.0, daily, int(daily_limit))
                else:
                    state = BreakerState.CLOSED.value

                is_probe = state == BreakerState.HALF_OPEN.value
                probe_lease_until = now + lease if is_probe else 0.0
                self._exec(
                    """UPDATE provider_health
                       SET state=?, attempt_count=attempt_count+1, daily_requests=daily_requests+1,
                           day=?, probe_in_flight=CASE WHEN ?=1 THEN ? ELSE 0 END,
                           probe_lease_until=?, last_attempt_at=?, updated_at=?
                       WHERE provider=?""",
                    (state, day, 1 if is_probe else 0, probes + 1 if is_probe else 0,
                     probe_lease_until, now, now, provider),
                )
                self._exec("COMMIT")
                return Admission(True, state, "ok", is_probe, 0.0, 0.0, daily + 1, int(daily_limit))
            except BaseException:
                with contextlib.suppress(Exception):
                    self._exec("ROLLBACK")
                raise

    # ------------------------------------------------------------------ outcomes
    def record_success(self, provider: str, *, ttft_ms: float | None = None) -> dict[str, Any]:
        """First validated visible segment: breaker closes, failures reset."""
        now = self.now()
        with self._lock:
            self._exec(
                """UPDATE provider_health
                   SET state='closed', consecutive_failures=0, open_count=0, open_until=0,
                       probe_in_flight=CASE WHEN probe_in_flight>0 THEN probe_in_flight-1 ELSE 0 END,
                       probe_lease_until=0, success_count=success_count+1,
                       last_ttft_ms=COALESCE(?, last_ttft_ms), last_error=NULL,
                       updated_at=?
                   WHERE provider=?""",
                (ttft_ms, now, provider),
            )
        return self.snapshot(provider)

    def record_failure(
        self,
        provider: str,
        kind: Any,
        *,
        detail: Any = None,
        retry_after_s: float | None = None,
    ) -> dict[str, Any]:
        """Open the breaker with escalated, capped, jittered per-provider cooldown."""
        now = self.now()
        k = _kind_value(kind)
        column = KIND_COLUMNS.get(k)
        with self._lock:
            self._exec("BEGIN IMMEDIATE")
            try:
                row = self._ensure_row(provider, now)
                failures = int(row["consecutive_failures"]) + 1
                cooldown = self.backoff_s(failures, kind=k, retry_after_s=retry_after_s)
                open_count = int(row["open_count"]) + (1 if row["state"] == BreakerState.HALF_OPEN.value else 0)
                sql = (
                    """UPDATE provider_health
                       SET state='open', consecutive_failures=?, open_count=?, open_until=?,
                           probe_in_flight=CASE WHEN probe_in_flight>0 THEN probe_in_flight-1 ELSE 0 END,
                           probe_lease_until=0, failure_count=failure_count+1, last_error=?,
                           last_failure_kind=?, updated_at=?"""
                )
                if column:
                    sql += f", {column}={column}+1"
                sql += " WHERE provider=?"
                self._exec(sql, (failures, open_count, now + cooldown,
                                 redact(detail, max_len=300), k, now, provider))
                self._exec("COMMIT")
            except BaseException:
                with contextlib.suppress(Exception):
                    self._exec("ROLLBACK")
                raise
            out = self.snapshot(provider)
        out["cooldown_s"] = cooldown
        return out

    def release(self, provider: str) -> None:
        """Release an in-flight probe slot. Idempotent; never mutates breaker state."""
        now = self.now()
        with self._lock:
            self._exec(
                """UPDATE provider_health
                   SET probe_in_flight=CASE WHEN probe_in_flight>0 THEN probe_in_flight-1 ELSE 0 END,
                       probe_lease_until=CASE WHEN probe_in_flight<=1 THEN 0 ELSE probe_lease_until END,
                       updated_at=?
                   WHERE provider=?""",
                (now, provider),
            )

    def reset(self, provider: str) -> None:
        with self._lock:
            self._exec(
                """UPDATE provider_health
                   SET state='closed', consecutive_failures=0, open_count=0, open_until=0,
                       probe_in_flight=0, probe_lease_until=0, updated_at=?
                   WHERE provider=?""",
                (self.now(), provider),
            )

    # ------------------------------------------------------------------- metrics
    def metrics(self) -> dict[str, dict[str, Any]]:
        now = self.now()
        day = self.day_key(now)
        with self._lock:
            rows = self._exec("SELECT * FROM provider_health").fetchall()
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            d = dict(row)
            d["day_current"] = d["day"] == day
            d["cooldown_remaining_s"] = max(0.0, float(d["open_until"]) - now)
            out[str(d["provider"])] = d
        return out

