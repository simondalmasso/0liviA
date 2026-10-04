from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Protocol, runtime_checkable


class TurnState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    RESPONDING = "responding"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class VoiceEventType(str, Enum):
    TURN_STARTED = "turn_started"
    FRAME_ACCEPTED = "frame_accepted"
    FRAME_DROPPED = "frame_dropped"
    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"
    STT_PARTIAL = "stt_partial"
    STT_FINAL = "stt_final"
    LLM_TEXT = "llm_text"
    TTS_AUDIO = "tts_audio"
    TURN_CANCELLED = "turn_cancelled"
    TURN_COMPLETED = "turn_completed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AudioFrame:
    turn_id: str
    seq: int
    pcm_s16le: bytes
    sample_rate: int = 16_000
    channels: int = 1
    client_ts_ms: float | None = None

    def validate(self) -> None:
        if not self.turn_id or len(self.turn_id) > 128:
            raise ValueError("invalid turn_id")
        if self.seq < 0:
            raise ValueError("seq must be >= 0")
        if self.sample_rate not in {8_000, 16_000, 24_000, 48_000}:
            raise ValueError("unsupported sample rate")
        if self.channels not in {1, 2}:
            raise ValueError("unsupported channel count")
        if len(self.pcm_s16le) % (2 * self.channels):
            raise ValueError("PCM16 payload is not frame-aligned")


@dataclass(frozen=True, slots=True)
class VoiceEvent:
    type: VoiceEventType
    turn_id: str
    seq: int | None = None
    text: str | None = None
    audio: bytes | None = None
    detail: str | None = None


@runtime_checkable
class VoiceTransport(Protocol):
    async def recv(self) -> AsyncIterator[AudioFrame | VoiceEvent]: ...
    async def send_event(self, event: VoiceEvent) -> None: ...
    async def close(self) -> None: ...


@runtime_checkable
class VoiceVAD(Protocol):
    def process(self, frame: AudioFrame) -> tuple[bool, bool]:
        """Return (speech_started, speech_ended)."""
        ...
    def reset(self) -> None: ...


@runtime_checkable
class VoiceEndpointing(Protocol):
    def update(self, *, speaking: bool, now_ms: float) -> bool:
        """Return True exactly when the active utterance should end."""
        ...
    def reset(self) -> None: ...


@runtime_checkable
class VoiceSTT(Protocol):
    async def push(self, frame: AudioFrame) -> str | None:
        """Return an optional partial transcript."""
        ...
    async def finalize(self) -> str: ...
    async def reset(self) -> None: ...


@runtime_checkable
class VoiceTTS(Protocol):
    async def stream(self, text: str, *, locale: str) -> AsyncIterator[bytes]: ...
    async def cancel(self) -> None: ...
