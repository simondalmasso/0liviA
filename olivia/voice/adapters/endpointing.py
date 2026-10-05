from __future__ import annotations


class AdaptiveSilenceEndpoint:
    """Conservative end-of-turn detector with no language-model dependency."""

    def __init__(
        self,
        *,
        silence_ms: float = 500.0,
        floor_ms: float = 250.0,
        ceiling_ms: float = 900.0,
    ) -> None:
        self.floor_ms = max(1.0, float(floor_ms))
        self.ceiling_ms = max(self.floor_ms, float(ceiling_ms))
        self.silence_ms = min(self.ceiling_ms, max(self.floor_ms, float(silence_ms)))
        self.reset()

    def reset(self) -> None:
        self._had_speech = False
        self._silence = 0.0
        self._fired = False

    def observe(self, *, speaking: bool, frame_ms: float) -> bool:
        frame_ms = max(0.0, float(frame_ms))
        if speaking:
            self._had_speech = True
            self._silence = 0.0
            self._fired = False
            return False

        if not self._had_speech or self._fired:
            return False

        self._silence += frame_ms
        if self._silence >= self.silence_ms:
            self._fired = True
            return True
        return False
