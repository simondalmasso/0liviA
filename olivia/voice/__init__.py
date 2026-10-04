"""Dependency-light realtime voice kernel for 0liviA."""

from .contracts import (
    AdapterTarget,
    AudioFrame,
    SequenceDecision,
    TranscriptChunk,
    TurnState,
    VoiceEvent,
    VoiceEventType,
)
from .llm import AgentVoiceLLM, VoiceLLM
from .locale import (
    DEFAULT_LOCALE,
    ES_AR,
    LocalePolicy,
    VoiceCandidate,
    VoiceProfile,
    is_argentine_spanish,
)
from .pipeline import VoicePipeline

__all__ = [
    "AdapterTarget",
    "AudioFrame",
    "SequenceDecision",
    "TranscriptChunk",
    "TurnState",
    "VoiceEvent",
    "VoiceEventType",
    "VoiceLLM",
    "AgentVoiceLLM",
    "DEFAULT_LOCALE",
    "ES_AR",
    "LocalePolicy",
    "VoiceCandidate",
    "VoiceProfile",
    "is_argentine_spanish",
    "VoicePipeline",
]
