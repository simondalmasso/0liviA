from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class VoiceBenchmark:
    clock: Callable[[], float] = time.perf_counter
    marks: dict[str, float] = field(default_factory=dict)
    samples: list[dict[str, float]] = field(default_factory=list)

    def mark(self, name: str) -> float:
        value = float(self.clock())
        self.marks[name] = value
        return value

    def elapsed_ms(self, start: str, end: str) -> float | None:
        if start not in self.marks or end not in self.marks:
            return None
        return (self.marks[end] - self.marks[start]) * 1000.0

    def record_resources(self, *, rss_mb: float, cpu_percent: float) -> None:
        self.samples.append({"rss_mb": float(rss_mb), "cpu_percent": float(cpu_percent)})

    def summary(self) -> dict[str, float | int | None]:
        return {
            "connect_ms": self.elapsed_ms("connect_start", "connected"),
            "partial_stt_ms": self.elapsed_ms("speech_start", "stt_partial"),
            "eot_ms": self.elapsed_ms("speech_end", "eot"),
            "llm_ttft_ms": self.elapsed_ms("eot", "llm_first_token"),
            "tts_ttfa_ms": self.elapsed_ms("llm_first_token", "tts_first_audio"),
            "cancel_ms": self.elapsed_ms("cancel_requested", "cancelled"),
            "resource_samples": len(self.samples),
            "peak_rss_mb": max((s["rss_mb"] for s in self.samples), default=None),
            "peak_cpu_percent": max((s["cpu_percent"] for s in self.samples), default=None),
        }
