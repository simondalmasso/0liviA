from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VoiceEventType(str, Enum):
    TURN_STARTED = "turn_started"
    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"
    STT_PARTIAL = "stt_partial"
    STT_FINAL = "stt_final"
    LLM_DELTA = "llm_delta"
    TTS_AUDIO = "tts_audio"
    TURN_COMPLETED = "turn_completed"
    CANCELLED = "cancelled"
    DROPPED_AUDIO = "dropped_audio"
    ERROR = "error"


class TurnState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    CANCELLED = "cancelled"
    COMPLETE = "complete"


class SequenceDecision(str, Enum):
    ACCEPT = "accept"
    WRONG_TURN = "wrong_turn"
    OUT_OF_ORDER = "out_of_order"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class AudioFrame:
    turn_id: str
    seq: int
    pcm_s16le: bytes
    sample_rate: int = 16_000
    channels: int = 1

    def __post_init__(self) -> None:
        if not self.turn_id:
            raise ValueError("turn_id is required")
        if self.seq < 0:
            raise ValueError("seq must be >= 0")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be > 0")
        if self.channels <= 0:
            raise ValueError("channels must be > 0")
        if len(self.pcm_s16le) % 2:
            raise ValueError("pcm_s16le must contain complete int16 samples")

    @property
    def duration_ms(self) -> float:
        samples_per_channel = len(self.pcm_s16le) / 2 / self.channels
        return samples_per_channel / self.sample_rate * 1000.0


@dataclass(frozen=True)
class TranscriptChunk:
    text: str
    final: bool = False


@dataclass(frozen=True)
class VoiceEvent:
    type: VoiceEventType
    turn_id: str
    seq: int | None = None
    text: str | None = None
    detail: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterTarget:
    kind: str
    name: str
    local: bool
    streaming: bool
    locale: str | None = None
    notes: str = ""
