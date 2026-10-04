"""Realtime voice contracts for 0liviA.

The package is intentionally dependency-light. Concrete speech engines are
optional adapters selected only after Oracle A1 benchmarks.
"""

from .contracts import (
    AudioFrame,
    TurnState,
    VoiceEvent,
    VoiceEventType,
    VoiceTransport,
    VoiceVAD,
    VoiceEndpointing,
    VoiceSTT,
    VoiceTTS,
)
from .locale import DEFAULT_LOCALE, VoiceProfile
from .state import VoiceTurnGate

__all__ = [
    "AudioFrame",
    "TurnState",
    "VoiceEvent",
    "VoiceEventType",
    "VoiceTransport",
    "VoiceVAD",
    "VoiceEndpointing",
    "VoiceSTT",
    "VoiceTTS",
    "DEFAULT_LOCALE",
    "VoiceProfile",
    "VoiceTurnGate",
]
