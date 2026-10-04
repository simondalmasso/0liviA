from olivia.voice.benchmarks import VoiceBenchmark


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def test_voice_benchmark_reports_pipeline_latency_and_resources():
    clock = Clock()
    b = VoiceBenchmark(clock=clock)
    b.mark("connect_start"); clock.advance(0.1); b.mark("connected")
    b.mark("speech_start"); clock.advance(0.2); b.mark("stt_partial")
    b.mark("speech_end"); clock.advance(0.3); b.mark("eot")
    clock.advance(0.4); b.mark("llm_first_token")
    clock.advance(0.5); b.mark("tts_first_audio")
    b.mark("cancel_requested"); clock.advance(0.08); b.mark("cancelled")
    b.record_resources(rss_mb=120, cpu_percent=35)
    b.record_resources(rss_mb=140, cpu_percent=55)
    s = b.summary()
    assert round(s["connect_ms"]) == 100
    assert round(s["partial_stt_ms"]) == 200
    assert round(s["eot_ms"]) == 300
    assert round(s["llm_ttft_ms"]) == 400
    assert round(s["tts_ttfa_ms"]) == 500
    assert round(s["cancel_ms"]) == 80
    assert s["peak_rss_mb"] == 140
    assert s["peak_cpu_percent"] == 55
