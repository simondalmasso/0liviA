"""Exercise the embedded canonical release SSE acceptance gate without a host."""
import json
import os
import subprocess
import sys
from pathlib import Path

SMOKE = (Path(__file__).resolve().parents[1] / "deploy" / "smoke.sh").read_text(encoding="utf-8")
MARKER = 'CHAT_STREAM="${chat_stream}" python3 - <<\'PY\'\n'
STREAM_VALIDATOR = SMOKE.split(MARKER, 1)[1].split("\nPY", 1)[0]


def check(events, *, raw=None):
    stream = raw if raw is not None else "\n".join(
        "data: " + json.dumps(event, ensure_ascii=False) for event in events
    )
    return subprocess.run(
        [sys.executable, "-c", STREAM_VALIDATOR],
        env={**os.environ, "CHAT_STREAM": stream},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


GOOD = [
    {"type": "route", "provider": "safe-free-provider"},
    {"type": "delta", "text": "Listo."},
    {"type": "done", "provider": "safe-free-provider"},
]


def test_clean_provider_stream_is_accepted():
    assert check(GOOD).returncode == 0


def test_silent_or_empty_answer_cannot_certify_production():
    bad = [
        {"type": "route", "provider": "safe-free-provider"},
        {"type": "delta", "text": "  "},
        {"type": "done"},
    ]
    result = check(bad)
    assert result.returncode != 0
    assert "no nonempty assistant answer" in result.stderr


def test_provider_error_then_done_is_not_success():
    bad = [
        {"type": "route", "provider": "safe-free-provider"},
        {"type": "error", "error": "rate limit"},
        {"type": "delta", "text": "provider unavailable"},
        {"type": "done"},
    ]
    result = check(bad)
    assert result.returncode != 0
    assert "provider/stream error" in result.stderr


def test_malformed_or_missing_completion_is_rejected():
    assert check([], raw='data: {"type": "route"\n').returncode != 0
    assert check(GOOD[:-1]).returncode != 0
    assert check(GOOD + [{"type": "done"}]).returncode != 0


def test_provider_switch_after_user_visible_output_is_rejected():
    bad = [
        {"type": "route", "provider": "first"},
        {"type": "delta", "text": "Part one"},
        {"type": "route", "provider": "second"},
        {"type": "done", "provider": "second"},
    ]
    assert check(bad).returncode != 0


def test_pre_output_failover_is_allowed():
    events = [
        {"type": "route", "provider": "first"},
        {"type": "route", "provider": "second"},
        {"type": "delta", "text": "Good answer"},
        {"type": "done", "provider": "second"},
    ]
    assert check(events).returncode == 0
