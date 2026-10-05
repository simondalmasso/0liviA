from __future__ import annotations

import pytest

from olivia.config import Settings
from olivia.health import FailureKind, ProviderHealth, redact


class Clock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> float:
        self.t += float(seconds)
        return self.t


def make_health(tmp_path, clock, **overrides) -> ProviderHealth:
    values = {
        "data_dir": tmp_path,
        "circuit_base_s": 1,
        "circuit_max_s": 8,
        "circuit_jitter_ratio": 0.0,
        "circuit_half_open_probes": 1,
        "probe_lease_s": 30.0,
    }
    values.update(overrides)
    settings = Settings(**values)
    return ProviderHealth(tmp_path / "health.sqlite3", settings, now=clock, jitter=lambda: 0.0)


def test_failure_opens_breaker_and_denies_during_cooldown(tmp_path):
    clock = Clock()
    health = make_health(tmp_path, clock)
    assert health.admit("p").allowed is True

    snap = health.record_failure("p", FailureKind.TIMEOUT, detail="no first token")
    assert snap["state"] == "open" and snap["cooldown_s"] == pytest.approx(1.0)
    assert snap["timeout_count"] == 1 and snap["failure_count"] == 1

    blocked = health.admit("p")
    assert blocked.allowed is False and blocked.reason == "cooldown"
    assert blocked.cooldown_remaining_s == pytest.approx(1.0)


def test_half_open_probe_closes_breaker_on_success(tmp_path):
    clock = Clock()
    health = make_health(tmp_path, clock)
    health.record_failure("p", FailureKind.UNKNOWN, detail="boom")

    clock.advance(1.5)
    probe = health.admit("p")
    assert probe.allowed is True and probe.is_probe is True and probe.state == "half_open"
    # second concurrent turn must not probe the same recovering provider
    second = health.admit("p")
    assert second.allowed is False and second.reason == "probe_in_flight"

    snap = health.record_success("p", ttft_ms=123.0)
    assert snap["state"] == "closed" and snap["consecutive_failures"] == 0
    assert snap["probe_in_flight"] == 0 and snap["open_count"] == 0
    assert snap["success_count"] == 1 and snap["last_ttft_ms"] == pytest.approx(123.0)

    plain = health.admit("p")
    assert plain.allowed is True and plain.is_probe is False


def test_half_open_probe_failure_reopens_with_escalated_backoff(tmp_path):
    clock = Clock()
    health = make_health(tmp_path, clock)

    first = health.record_failure("p", FailureKind.UNKNOWN, detail="boom")
    assert first["cooldown_s"] == pytest.approx(1.0)

    clock.advance(1.0)
    assert health.admit("p").is_probe is True
    second = health.record_failure("p", FailureKind.TIMEOUT, detail="still down")
    assert second["cooldown_s"] == pytest.approx(2.0) and second["open_count"] == 1

    clock.advance(2.0)
    assert health.admit("p").is_probe is True
    third = health.record_failure("p", FailureKind.HTTP, detail="still down")
    assert third["cooldown_s"] == pytest.approx(4.0) and third["open_count"] == 2

    # cap is enforced, no runaway exponent
    for _ in range(10):
        clock.advance(100.0)
        health.admit("p")
        last = health.record_failure("p", FailureKind.UNKNOWN, detail="x")
    assert last["cooldown_s"] == pytest.approx(8.0)


def test_abandoned_probe_does_not_wedge_half_open(tmp_path):
    clock = Clock()
    health = make_health(tmp_path, clock, probe_lease_s=5.0)
    health.record_failure("p", FailureKind.UNKNOWN, detail="boom")

    clock.advance(1.0)
    assert health.admit("p").is_probe is True
    assert health.admit("p").allowed is False  # lease still covers the in-flight probe

    clock.advance(6.0)  # probe vanished (crash/timeout without release)
    assert health.admit("p").is_probe is True


def test_quota_consumed_then_resets_on_day_rollover(tmp_path):
    clock = Clock()
    health = make_health(tmp_path, clock)

    assert health.admit("p", daily_limit=2).allowed is True
    assert health.admit("p", daily_limit=2).allowed is True
    capped = health.admit("p", daily_limit=2)
    assert capped.allowed is False and capped.reason == "quota_exhausted"
    assert capped.daily_requests == 2
    # quota denial never opens the breaker
    assert health.snapshot("p")["state"] == "closed"

    clock.advance(24 * 3600)
    rolled = health.admit("p", daily_limit=2)
    assert rolled.allowed is True and rolled.daily_requests == 1
    assert health.snapshot("p")["daily_requests"] == 1


def test_quota_reset_is_safe_on_clock_skew_and_corruption(tmp_path):
    clock = Clock()
    health = make_health(tmp_path, clock)
    health.admit("p", daily_limit=1)

    health._exec(
        "UPDATE provider_health SET day='2999-01-01', daily_requests=7 WHERE provider=?",
        ("p",),
    )
    skewed = health.admit("p", daily_limit=1)
    assert skewed.allowed is True and skewed.daily_requests == 1

    health._exec("UPDATE provider_health SET daily_requests=-4 WHERE provider=?", ("p",))
    repaired = health.admit("p", daily_limit=1)
    assert repaired.allowed is True and repaired.daily_requests == 1


def test_rate_limit_honours_retry_after_and_jitter_is_bounded(tmp_path):
    clock = Clock()
    health = make_health(tmp_path, clock, circuit_base_s=5, circuit_max_s=60)
    assert health.backoff_s(1, kind=FailureKind.RATE_LIMIT, retry_after_s=120) == pytest.approx(120.0)
    assert health.backoff_s(1, kind=FailureKind.RATE_LIMIT, retry_after_s=7) == pytest.approx(7.0)
    assert health.backoff_s(1, kind=FailureKind.RATE_LIMIT) == pytest.approx(5.0)

    jittered = ProviderHealth(
        tmp_path / "j.sqlite3",
        Settings(data_dir=tmp_path, circuit_base_s=1, circuit_max_s=8, circuit_jitter_ratio=0.5),
        now=Clock(),
    )
    values = [jittered.backoff_s(3, kind=FailureKind.TIMEOUT) for _ in range(40)]
    assert all(2.0 <= v <= 6.0 for v in values)   # base=1 -> 2**(3-1) = 4, jitter +/-50%
    assert len(set(round(v, 6) for v in values)) > 1  # jitter is actually applied
    assert jittered.backoff_s(30, kind=FailureKind.TIMEOUT) <= 12.0  # capped at max=8 (+jitter)


def test_metrics_expose_state_and_counters(tmp_path):
    clock = Clock()
    health = make_health(tmp_path, clock)
    health.admit("p", daily_limit=5)
    health.record_failure("p", FailureKind.EMPTY_STREAM, detail="empty")
    metrics = health.metrics()["p"]
    assert metrics["state"] == "open" and metrics["daily_requests"] == 1
    assert metrics["empty_count"] == 1 and metrics["day_current"] is True
    assert metrics["cooldown_remaining_s"] == pytest.approx(1.0)


def test_redact_strips_secrets_and_control_chars():
    secret = "sk-" + "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
    out = redact(f"HTTP 401 invalid key {secret}\nsecond line Bearer {secret} AIzaSyD-abcdefghijklmnop12345")
    assert secret not in out
    assert "AIzaSyD-abcdefghijklmnop12345" not in out
    assert "\n" not in out
    assert "[redacted]" in out
    assert len(redact("word " * 400, max_len=200)) == 200  # hard truncation
    assert "token=[redacted]" in redact("token=supersecretvalue")
    assert redact(None) == "" and redact("line1\nline2") == "line1 line2"