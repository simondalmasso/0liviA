"""Realtime voice contracts for 0liviA.

This package is deliberately dependency-light. It keeps both the core pipeline
contract and the transport/speech adapter contract stable while engines remain
benchmark-gated on Oracle A1.
"""

from .contracts import (
    AdapterTarget,
    AudioFrame,
    SequenceDecision,
    TranscriptChunk,
    TurnState,
    VoiceEndpointing,
    VoiceEvent,
    VoiceEventType,
    VoiceSTT,
    VoiceTTS,
    VoiceTransport,
    VoiceVAD,
)
from .locale import (
    DEFAULT_LOCALE,
    ES_AR,
    LocalePolicy,
    VoiceCandidate,
    VoiceProfile,
    is_argentine_spanish,
)
from .pipeline import VoicePipeline
from .state import VoiceTurnGate

__all__ = [
    "AdapterTarget",
    "AudioFrame",
    "SequenceDecision",
    "TranscriptChunk",
    "TurnState",
    "VoiceEndpointing",
    "VoiceEvent",
    "VoiceEventType",
    "VoiceSTT",
    "VoiceTTS",
    "VoiceTransport",
    "VoiceVAD",
    "DEFAULT_LOCALE",
    "ES_AR",
    "LocalePolicy",
    "VoiceCandidate",
    "VoiceProfile",
    "is_argentine_spanish",
    "VoicePipeline",
    "VoiceTurnGate",
]
