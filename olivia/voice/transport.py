from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DirectWssConfig:
    """Wire contract for the default Browser ↔ Oracle voice transport."""

    path: str = "/api/voice/ws"
    max_audio_frame_bytes: int = 64 * 1024
    ping_interval_s: float = 20.0
    receive_timeout_s: float = 45.0

    def validate(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("voice WSS path must be absolute")
        if self.max_audio_frame_bytes < 1024:
            raise ValueError("audio frame limit too small")
        if self.ping_interval_s <= 0 or self.receive_timeout_s <= 0:
            raise ValueError("timeouts must be positive")


CONTROL_TYPES = frozenset(
    {
        "start",
        "cancel",
        "audio_meta",
        "stt_partial",
        "stt_final",
        "llm_text",
        "tts_meta",
        "done",
        "error",
    }
)
