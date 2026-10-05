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
