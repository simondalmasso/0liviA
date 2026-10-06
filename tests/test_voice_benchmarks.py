from pathlib import Path

from olivia.voice.benchmarks import VoiceBenchmarkRecorder


def test_benchmark_recorder_reports_required_stages(tmp_path: Path):
    recorder = VoiceBenchmarkRecorder("wss", "moonshine", "pocket-tts")
    recorder.record("connect_ms", 12)
    recorder.record("ttfa_ms", 900)
    recorder.record("ttfa_ms", 1100)
    snapshot = recorder.snapshot()
    assert snapshot["locale"] == "es-AR"
    assert snapshot["stages"]["connect_ms"]["p50"] == 12
    assert snapshot["stages"]["ttfa_ms"]["p50"] == 1000
    assert "cancel_ms" in snapshot["stages"]

    output = tmp_path / "voice.json"
    recorder.write_json(output)
    assert '"transport": "wss"' in output.read_text(encoding="utf-8")


def test_voice_acceptance_fails_closed_when_required_measurements_are_missing():
    recorder = VoiceBenchmarkRecorder("direct-wss", "moonshine", "pocket-tts")
    result = recorder.acceptance()
    assert result["passed"] is False
    assert "ttfa_ms.p50" in result["missing"]
    assert "client_stop_ms.p95" in result["missing"]
    assert "server_cancel_ms.p95" in result["missing"]
    assert "soak_minutes" in result["missing"]
    assert "soak_clean" in result["missing"]
    assert "cross_turn_leaks" in result["missing"]
    assert "es_ar_accepted" in result["missing"]
    assert "false_cut_rate_accepted" in result["missing"]


def test_voice_acceptance_passes_only_when_all_live_like_gates_pass():
    recorder = VoiceBenchmarkRecorder("direct-wss", "moonshine", "pocket-tts")
    for value in (900, 1100, 1300):
        recorder.record("ttfa_ms", value)
    for value in (60, 90, 120):
        recorder.record("client_stop_ms", value)
    for value in (120, 180, 240):
        recorder.record("server_cancel_ms", value)
    recorder.record_quality("soak_minutes", 60)
    recorder.record_quality("soak_clean", True)
    recorder.record_quality("cross_turn_leaks", 0)
    recorder.record_quality("es_ar_accepted", True)
    recorder.record_quality("false_cut_rate_accepted", True)

    result = recorder.acceptance()
    assert result["passed"] is True
    assert result["failures"] == []
    assert result["missing"] == []


def test_voice_acceptance_rejects_latency_or_quality_regression():
    recorder = VoiceBenchmarkRecorder("livekit-agents", "moonshine", "pocket-tts")
    recorder.record("ttfa_ms", 1700)
    recorder.record("client_stop_ms", 180)
    recorder.record("server_cancel_ms", 350)
    recorder.record_quality("soak_minutes", 59)
    recorder.record_quality("soak_clean", False)
    recorder.record_quality("cross_turn_leaks", 1)
    recorder.record_quality("es_ar_accepted", False)
    recorder.record_quality("false_cut_rate_accepted", False)

    result = recorder.acceptance()
    assert result["passed"] is False
    assert {
        "ttfa_ms.p50",
        "client_stop_ms.p95",
        "server_cancel_ms.p95",
        "soak_minutes",
        "soak_clean",
        "cross_turn_leaks",
        "es_ar_accepted",
        "false_cut_rate_accepted",
    }.issubset(set(result["failures"]))


def test_voice_quality_observations_reject_unknown_or_invalid_values():
    recorder = VoiceBenchmarkRecorder("direct-wss", "moonshine", "pocket-tts")
    try:
        recorder.record_quality("made_up", 1)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown quality observation must fail")

    try:
        recorder.record_quality("soak_minutes", -1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative soak time must fail")
