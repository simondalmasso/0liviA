from __future__ import annotations

import math
import struct

from ..contracts import AudioFrame


class EnergyVAD:
    """Tiny dependency-free VAD used only as a contract/reference baseline.

    Silero ONNX is the production challenger. This implementation exists so
    sequencing, endpointing and cancellation can be tested without shipping a
    speech model in the control plane.
    """

    def __init__(
        self,
        *,
        start_rms: float = 800.0,
        end_rms: float = 350.0,
        start_frames: int = 2,
        end_frames: int = 3,
    ) -> None:
        if end_rms > start_rms:
            raise ValueError("end_rms must be <= start_rms")
        self.start_rms = float(start_rms)
        self.end_rms = float(end_rms)
        self.start_frames = max(1, int(start_frames))
        self.end_frames = max(1, int(end_frames))
        self.reset()

    @property
    def speaking(self) -> bool:
        return self._speaking

    def reset(self) -> None:
        self._speaking = False
        self._above = 0
        self._below = 0

    @staticmethod
    def _rms(pcm: bytes) -> float:
        if not pcm:
            return 0.0
        count = len(pcm) // 2
        if not count:
            return 0.0
        total = 0
        for (sample,) in struct.iter_unpack("<h", pcm):
            total += sample * sample
        return math.sqrt(total / count)

    def accept(self, frame: AudioFrame) -> tuple[bool, bool]:
        rms = self._rms(frame.pcm_s16le)
        started = ended = False

        if rms >= self.start_rms:
            self._above += 1
            self._below = 0
        elif rms <= self.end_rms:
            self._below += 1
            self._above = 0
        else:
            self._above = self._below = 0

        if not self._speaking and self._above >= self.start_frames:
            self._speaking = True
            self._above = 0
            started = True
        elif self._speaking and self._below >= self.end_frames:
            self._speaking = False
            self._below = 0
            ended = True

        return started, ended
