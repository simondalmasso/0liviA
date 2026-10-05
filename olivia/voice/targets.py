from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpeechTargets:
    """Benchmark candidates, not mandatory runtime dependencies."""

    transport_default: str = "direct-wss"
    transport_challengers: tuple[str, ...] = ("pipecat-smallwebrtc", "livekit-agents", "streamcore")
    vad_default: str = "silero-onnx"
    stt_preferred: str = "moonshine"
    stt_fallback: str = "whisper.cpp"
    stt_quota_lane: str = "groq-whisper"
    tts_preferred: str = "pocket-tts"
    tts_fallback: str = "piper"
    tts_challengers: tuple[str, ...] = ("kokoro", "moss-tts-nano")


TARGETS = SpeechTargets()
