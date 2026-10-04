from __future__ import annotations

import json
import resource
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STAGES = (
    "connect_ms",
    "partial_stt_ms",
    "eot_ms",
    "llm_ttft_ms",
    "ttfa_ms",
    "cancel_ms",
)


@dataclass
class VoiceBenchmarkRecorder:
    """Small benchmark recorder; it does not fake measurements.

    Target-host runners call record() with observed durations and dump the
    result as JSON for comparison of WSS / SmallWebRTC / StreamCore and
    Moonshine / Groq Whisper / whisper.cpp / TTS candidates.
    """

    transport: str
    stt: str
    tts: str
    locale: str = "es-AR"
    started_at: float = field(default_factory=time.time)
    samples: dict[str, list[float]] = field(default_factory=lambda: {name: [] for name in STAGES})

    def record(self, stage: str, milliseconds: float) -> None:
        if stage not in self.samples:
            raise ValueError(f"unknown benchmark stage: {stage}")
        value = float(milliseconds)
        if value < 0:
            raise ValueError("benchmark duration cannot be negative")
        self.samples[stage].append(value)

    @staticmethod
    def _stats(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"n": 0, "p50": None, "p95": None, "max": None}
        ordered = sorted(values)
        p50 = statistics.median(ordered)
        p95 = ordered[min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))]
        return {"n": len(ordered), "p50": p50, "p95": p95, "max": max(ordered)}

    def snapshot(self) -> dict[str, Any]:
        rss_kb = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return {
            "transport": self.transport,
            "stt": self.stt,
            "tts": self.tts,
            "locale": self.locale,
            "started_at": self.started_at,
            "rss_kb": rss_kb,
            "stages": {key: self._stats(value) for key, value in self.samples.items()},
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.snapshot(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
