"""Router reliability gates: 429, timeout, empty stream, half-open recovery,
cancellation, post-first-token failure, attempt dedupe, quota and redaction.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from olivia.config import Settings
from olivia.health import ProviderHealth
from olivia.router import (
    AllProvidersFailed,
    ProviderHTTPError,
    ProviderPool,
    ProviderStreamInterrupted,
    is_visible_segment,
)
from olivia.store import Store

MSG = [{"role": "user", "content": "hi"}]
SECRET = "sk-" + "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"


class Clock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> float:
        self.t += float(seconds)
        return self.t


class ScriptedProvider:
    """Deterministic provider: scripted yields, sleeps and raises."""

    def __init__(self, name, actions=(), *, priority=10, daily_limit=0):
        self.name = name
        self.actions = list(actions)
        self.priority = priority
        self.daily_limit = daily_limit
        self.calls = 0

    async def stream(self, messages):
        self.calls += 1
        for action, arg in self.actions:
            if action == "yield":
                yield arg
            elif action == "sleep":
                await asyncio.sleep(arg)
            elif action == "raise":
                raise arg
            else:  # pragma: no cover - defensive
                raise AssertionError(f"unknown action {action}")


def make_env(tmp_path, providers, *, event_sink=None, **overrides):
    values = {
        "data_dir": tmp_path,
        "ttft_timeout_s": 1.0,
        "circuit_base_s": 1,
        "circuit_max_s": 8,
        "circuit_jitter_ratio": 0.0,
        "circuit_half_open_probes": 1,
        "probe_lease_s": 30.0,
        "max_provider_attempts": 3,
        "cooldown_rate_limit_s": 1,
    }
    values.update(overrides)
    settings = Settings(**values)
    clock = Clock()
    store = Store(tmp_path / "db.sqlite3")
    health = ProviderHealth(store.path, settings, now=clock, jitter=lambda: 0.0)
    pool = ProviderPool(providers, store, settings, health=health, clock=clock, event_sink=event_sink)
    return pool, health, clock, store, settings


async def collect(pool, messages=None):
    return [event async for event in pool.stream(messages or MSG)]


def kinds(pool):
    return [record["kind"] for record in pool.telemetry]


def record(pool, kind):
    return next((r for r in pool.telemetry if r["kind"] == kind), None)


# ------------------------------------------------------------------ 429 + backoff
@pytest.mark.asyncio
async def test_429_fails_over_and_cools_provider_from_retry_after(tmp_path):
    limited = ScriptedProvider(
        "limited", [("raise", ProviderHTTPError("limited", 429, "rate limit exceeded", 30.0))], priority=1
    )
    healthy = ScriptedProvider("healthy", [("yield", "ok")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [limited, healthy])

    events = await collect(pool)
    assert [e.type for e in events] == ["route", "delta"]
    assert events[0].provider == "healthy" and events[1].text == "ok"

    snapshot = health.snapshot("limited")
    assert snapshot["state"] == "open"
    assert snapshot["rate_limit_count"] == 1
    assert snapshot["cooldown_remaining_s"] >= 29.0  # Retry-After wins over circuit_base_s

    failure = record(pool, "failure")
    assert failure["failure_kind"] == "rate_limit" and failure["cooldown_s"] >= 29.0 and failure["visible"] is False
    assert {"attempt", "failure", "first_segment", "success", "ttft"}.issubset(set(kinds(pool)))

    # second turn: the breaker must skip, not hammer
    await collect(pool)
    assert limited.calls == 1
    assert record(pool, "breaker.skip")["provider"] == "limited"


# ----------------------------------------------------------------------- timeout
@pytest.mark.asyncio
async def test_ttft_watchdog_fails_over_and_skips_hot_provider(tmp_path):
    slow = ScriptedProvider("slow", [("sleep", 5.0), ("yield", "too-late")], priority=1)
    fast = ScriptedProvider("fast", [("yield", "fast-answer")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [slow, fast], ttft_timeout_s=0.05)

    events = await collect(pool)
    assert events[0].provider == "fast"
    assert "".join(e.text or "" for e in events if e.type == "delta") == "fast-answer"

    assert record(pool, "failure")["failure_kind"] == "timeout"
    snapshot = health.snapshot("slow")
    assert snapshot["state"] == "open" and snapshot["timeout_count"] == 1

    await collect(pool)
    assert slow.calls == 1  # watchdog + breaker: no repeated hammering


# ------------------------------------------------------------------- empty stream
@pytest.mark.asyncio
async def test_empty_stream_fails_over(tmp_path):
    empty = ScriptedProvider("empty", [], priority=1)
    backup = ScriptedProvider("backup", [("yield", "real")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [empty, backup])

    events = await collect(pool)
    assert events[0].provider == "backup"
    assert record(pool, "failure")["failure_kind"] == "empty_stream"
    assert health.snapshot("empty")["empty_count"] == 1


@pytest.mark.asyncio
async def test_keepalives_only_do_not_block_first_visible_segment(tmp_path):
    keepalive = ScriptedProvider("keepalive", [("yield", ""), ("yield", ""), ("yield", "real")], priority=1)
    backup = ScriptedProvider("backup", [("yield", "never")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [keepalive, backup])

    events = await collect(pool)
    assert [e.type for e in events] == ["route", "delta"]
    assert events[0].provider == "keepalive" and events[1].text == "real"
    assert backup.calls == 0


@pytest.mark.asyncio
async def test_whitespace_only_prefix_is_not_a_visible_segment(tmp_path):
    blank = ScriptedProvider(
        "blank",
        [("yield", "\n"), ("yield", "   "), ("yield", "\u200b"), ("raise", RuntimeError("boom"))],
        priority=1,
    )
    backup = ScriptedProvider("backup", [("yield", "real")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [blank, backup])

    events = await collect(pool)
    assert events[0].provider == "backup"
    assert all(e.provider != "blank" for e in events)  # nothing visible was published
    failure = record(pool, "failure")
    assert failure["failure_kind"] == "unknown" and failure["visible"] is False
    assert is_visible_segment("\u200b \n") is False and is_visible_segment(" x") is True


@pytest.mark.asyncio
async def test_whitespace_flood_is_classified_as_empty_stream(tmp_path):
    flood = ScriptedProvider("flood", [("yield", "  ")] * 5, priority=1)
    backup = ScriptedProvider("backup", [("yield", "real")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [flood, backup], visible_prefix_max_chars=4)

    events = await collect(pool)
    assert events[0].provider == "backup"
    assert record(pool, "failure")["failure_kind"] == "empty_stream"


# ------------------------------------------------------------ half-open recovery
@pytest.mark.asyncio
async def test_half_open_probe_recovers_provider_after_cooldown(tmp_path):
    flaky = ScriptedProvider("flaky", [("raise", RuntimeError("down"))], priority=1)
    backup = ScriptedProvider("backup", [("yield", "backup")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [flaky, backup])

    await collect(pool)
    assert health.snapshot("flaky")["state"] == "open"

    flaky.actions = [("yield", "recovered")]
    clock.advance(1.5)  # cooldown elapsed -> HALF_OPEN probe allowed

    events = await collect(pool)
    assert events[0].provider == "flaky"
    assert "".join(e.text or "" for e in events if e.type == "delta") == "recovered"
    assert flaky.calls == 2 and backup.calls == 1

    snapshot = health.snapshot("flaky")
    assert snapshot["state"] == "closed" and snapshot["consecutive_failures"] == 0
    assert snapshot["probe_in_flight"] == 0

    # once closed, a third turn uses it normally without extra probes
    third = await collect(pool)
    assert third[0].provider == "flaky"


@pytest.mark.asyncio
async def test_half_open_allows_one_probe_under_concurrency(tmp_path):
    flaky = ScriptedProvider("flaky", [("raise", RuntimeError("down"))], priority=1)
    backup = ScriptedProvider("backup", [("yield", "backup")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [flaky, backup])

    await collect(pool)  # opens the breaker
    flaky.actions = [("sleep", 0.05), ("yield", "recovered")]
    clock.advance(1.5)

    first, second = await asyncio.gather(collect(pool), collect(pool))
    assert first[0].provider == "flaky"      # single probe
    assert second[0].provider == "backup"    # concurrent turn must not hammer the half-open provider
    assert flaky.calls == 2 and backup.calls == 2
    assert health.snapshot("flaky")["state"] == "closed"
    probes = [r for r in pool.telemetry if r["kind"] == "attempt" and r.get("probe")]
    assert len(probes) == 1 and probes[0]["provider"] == "flaky"  # exactly one probe, ever


# ----------------------------------------------------------------- cancellation
@pytest.mark.asyncio
async def test_user_cancellation_never_fails_over_and_releases_probe(tmp_path):
    flaky = ScriptedProvider("flaky", [("raise", RuntimeError("down"))], priority=1)
    backup = ScriptedProvider("backup", [("yield", "backup")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [flaky, backup])

    await collect(pool)
    flaky.actions = [("sleep", 5.0), ("yield", "late")]
    clock.advance(1.5)
    backup_calls_before = backup.calls
    pool.drain_telemetry()  # window: cancellation only

    task = asyncio.create_task(collect(pool))
    await asyncio.sleep(0.05)
    assert health.snapshot("flaky")["state"] == "half_open"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert backup.calls == backup_calls_before      # no failover on cancellation
    assert flaky.calls == 2
    snapshot = health.snapshot("flaky")
    assert snapshot["failure_count"] == 1 and snapshot["state"] == "half_open"
    assert snapshot["probe_in_flight"] == 0         # probe slot released, breaker not wedged
    assert "cancelled" in kinds(pool) and "failure" not in kinds(pool)


@pytest.mark.asyncio
async def test_cancellation_inside_streaming_is_not_an_error(tmp_path):
    chatty = ScriptedProvider("chatty", [("yield", "a"), ("sleep", 5.0), ("yield", "b")], priority=1)
    backup = ScriptedProvider("backup", [("yield", "never")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [chatty, backup])

    task = asyncio.create_task(collect(pool))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert backup.calls == 0
    snapshot = health.snapshot("chatty")
    assert snapshot["state"] == "closed" and snapshot["failure_count"] == 0
    assert snapshot["success_count"] == 1  # first visible segment already succeeded
    assert "failure" not in kinds(pool)


# ------------------------------------------------- post-first-visible failure gate
@pytest.mark.asyncio
async def test_post_visible_failure_never_fails_over_and_cools_provider(tmp_path):
    flaky = ScriptedProvider(
        "flaky", [("yield", "hello"), ("raise", RuntimeError("socket reset"))], priority=1
    )
    backup = ScriptedProvider("backup", [("yield", "fallback")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [flaky, backup])

    with pytest.raises(ProviderStreamInterrupted):
        await collect(pool)
    assert backup.calls == 0                        # no silent provider switch mid-answer
    assert flaky.calls == 1                         # no duplicate attempt in the same turn

    failure = record(pool, "failure")
    assert failure["visible"] is True and failure["failure_kind"] == "interrupted"
    snapshot = health.snapshot("flaky")
    assert snapshot["state"] == "open" and snapshot["interrupted_count"] == 1

    events = await collect(pool)                    # next turn skips the broken provider
    assert events[0].provider == "backup"


# ----------------------------------------------------------- attempts / dedupe
@pytest.mark.asyncio
async def test_provider_is_attempted_at_most_once_per_turn(tmp_path):
    first = ScriptedProvider("dup", [("raise", RuntimeError("boom"))], priority=1)
    second = ScriptedProvider("dup", [("yield", "must-not-run")], priority=2)
    backup = ScriptedProvider("backup", [("yield", "ok")], priority=3)
    pool, health, clock, store, _ = make_env(tmp_path, [first, second, backup])

    assert [p.name for p in pool.providers] == ["dup", "backup"]
    assert pool.duplicates == ["dup"]

    events = await collect(pool)
    assert first.calls == 1 and second.calls == 0 and backup.calls == 1
    assert events[0].provider == "backup"
    assert record(pool, "pool.duplicates_dropped") is not None


@pytest.mark.asyncio
async def test_failover_ceiling_is_enforced(tmp_path):
    providers = [
        ScriptedProvider(f"p{i}", [("raise", RuntimeError("down"))], priority=i) for i in range(1, 6)
    ]
    pool, health, clock, store, _ = make_env(tmp_path, providers, max_provider_attempts=2)

    with pytest.raises(AllProvidersFailed) as excinfo:
        await collect(pool)
    assert providers[0].calls == 1 and providers[1].calls == 1 and providers[2].calls == 0
    assert "ceiling" in str(excinfo.value)
    assert record(pool, "attempts.capped") is not None


# ------------------------------------------------------------------ quota state
@pytest.mark.asyncio
async def test_daily_quota_gate_skips_provider_without_opening_breaker(tmp_path):
    capped = ScriptedProvider("capped", [("yield", "first")], priority=1, daily_limit=1)
    backup = ScriptedProvider("backup", [("yield", "second")], priority=2)
    pool, health, clock, store, _ = make_env(tmp_path, [capped, backup])

    events = await collect(pool)
    assert events[0].provider == "capped"

    events = await collect(pool)
    assert events[0].provider == "backup" and capped.calls == 1
    snapshot = health.snapshot("capped")
    assert snapshot["state"] == "closed" and snapshot["daily_requests"] == 1
    assert record(pool, "quota.exhausted")["daily_limit"] == 1


# ------------------------------------------------------------------ telemetry
@pytest.mark.asyncio
async def test_telemetry_and_errors_never_leak_secrets(tmp_path):
    leaky = ScriptedProvider(
        "leaky",
        [("raise", ProviderHTTPError("leaky", 401, f"invalid Authorization: Bearer {SECRET}"))],
        priority=1,
    )
    also_leaky = ScriptedProvider("also-leaky", [("raise", ValueError(f"bad api_key={SECRET}"))], priority=2)
    sink_records: list[dict] = []
    pool, health, clock, store, settings = make_env(
        tmp_path, [leaky, also_leaky], event_sink=sink_records.append, max_provider_attempts=2
    )

    with pytest.raises(AllProvidersFailed) as excinfo:
        await collect(pool)

    telemetry = pool.drain_telemetry()
    blobs = [str(excinfo.value), json.dumps(telemetry), json.dumps(sink_records)]
    for blob in blobs:
        assert SECRET not in blob
        assert "a1b2c3d4e5f6" not in blob
    assert "redacted" in blobs[0]
    assert sum(r["kind"] == "failure" for r in telemetry) == 2
    assert health.snapshot("leaky")["failure_count"] == 1


@pytest.mark.asyncio
async def test_telemetry_failures_never_break_a_turn(tmp_path):
    class ExplodingSink:
        def __call__(self, record):
            raise RuntimeError("sink down")

    class StoreWithoutEvents:
        path = ":memory:"  # no record_event attribute at all

    ok = ScriptedProvider("ok", [("yield", "fine")], priority=1)
    settings = Settings(data_dir=tmp_path, ttft_timeout_s=1, circuit_base_s=1, circuit_max_s=4)
    clock = Clock()
    pool = ProviderPool(
        [ok],
        StoreWithoutEvents(),
        settings,
        health=ProviderHealth(tmp_path / "h.sqlite3", settings, now=clock, jitter=lambda: 0.0),
        clock=clock,
        event_sink=ExplodingSink(),
    )
    events = await collect(pool)
    assert [e.type for e in events] == ["route", "delta"]
    assert record(pool, "success") is not None


@pytest.mark.asyncio
async def test_route_events_keep_agent_compatible_surface(tmp_path):
    provider = ScriptedProvider("ok", [("yield", "hello"), ("yield", " world")], priority=1)
    pool, health, clock, store, _ = make_env(tmp_path, [provider])

    events = await collect(pool)
    assert [e.type for e in events] == ["route", "delta", "delta"]
    assert events[0].provider == "ok"
    assert "".join(e.text or "" for e in events if e.type == "delta") == "hello world"
    metrics = pool.metrics()
    assert metrics["turns"] == 1 and metrics["providers"]["ok"]["success_count"] == 1