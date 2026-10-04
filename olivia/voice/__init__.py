"""Realtime voice contracts for 0liviA.

The package deliberately contains no heavyweight speech-model dependency.
Adapters for Silero, Moonshine, Pocket TTS, Piper and Kokoro are deployment
choices that must pass Oracle A1 + es-AR benchmarks before becoming defaults.
"""

from .contracts import (
    AdapterTarget,
    AudioFrame,
    SequenceDecision,
    TranscriptChunk,
    TurnState,
    VoiceEvent,
    VoiceEventType,
)
from .locale import ES_AR, LocalePolicy, VoiceCandidate
from .pipeline import VoicePipeline

__all__ = [
    "AdapterTarget",
    "AudioFrame",
    "SequenceDecision",
    "TranscriptChunk",
    "TurnState",
    "VoiceEvent",
    "VoiceEventType",
    "ES_AR",
    "LocalePolicy",
    "VoiceCandidate",
    "VoicePipeline",
]
