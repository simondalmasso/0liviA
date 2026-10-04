from __future__ import annotations

import math
import struct
from dataclasses import dataclass

from .contracts import AudioFrame


@dataclass(slots=True)
class EnergyVAD:
    """Tiny dependency-free baseline used only until Silero wins the A1 bake-off."""

    start_rms: float = 800.0
    end_rms: float = 350.0
    start_frames: int = 2
    end_frames: int = 3
    speaking: bool = False
    _above: int = 0
    _below: int = 0

    @staticmethod
    def rms(frame: AudioFrame) -> float:
        frame.validate()
        samples = [sample[0] for sample in struct.iter_unpack("<h", frame.pcm_s16le)]
        if not samples:
            return 0.0
        return math.sqrt(sum(sample * sample for sample in samples) / len(samples))

    def process(self, frame: AudioFrame) -> tuple[bool, bool]:
        level = self.rms(frame)
        started = ended = False
        if level >= self.start_rms:
            self._above += 1
            self._below = 0
            if not self.speaking and self._above >= max(1, self.start_frames):
                self.speaking = True
                started = True
        elif level <= self.end_rms:
            self._below += 1
            self._above = 0
            if self.speaking and self._below >= max(1, self.end_frames):
                self.speaking = False
                ended = True
        else:
            self._above = self._below = 0
        return started, ended

    def reset(self) -> None:
        self.speaking = False
        self._above = 0
        self._below = 0


@dataclass(slots=True)
class AdaptiveSilenceEndpoint:
    """One-shot silence endpoint baseline; replaced only after measured improvement."""

    silence_ms: float = 450.0
    _silence_started_ms: float | None = None
    _fired: bool = False

    def __post_init__(self) -> None:
        self.silence_ms = max(80.0, float(self.silence_ms))

    def update(self, *, speaking: bool, now_ms: float) -> bool:
        if speaking:
            self._silence_started_ms = None
            self._fired = False
            return False
        if self._fired:
            return False
        if self._silence_started_ms is None:
            self._silence_started_ms = float(now_ms)
            return False
        if float(now_ms) - self._silence_started_ms >= self.silence_ms:
            self._fired = True
            return True
        return False

    def reset(self) -> None:
        self._silence_started_ms = None
        self._fired = False
