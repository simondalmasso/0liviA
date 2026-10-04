import pytest

from olivia.voice import AudioFrame, TurnState, VoiceEventType, VoiceProfile, VoiceTurnGate
from olivia.voice.locale import is_argentine_spanish
from olivia.voice.targets import TARGETS
from olivia.voice.transport import DirectWssConfig


def frame(turn_id, seq):
    return AudioFrame(turn_id=turn_id, seq=seq, pcm_s16le=b"\x00\x00" * 160)


def test_voice_profile_is_explicit_es_ar():
    VoiceProfile().validate()
    assert is_argentine_spanish("es_AR")
    with pytest.raises(ValueError):
        VoiceProfile(locale="es-ES").validate()


def test_direct_wss_is_default_but_challengers_are_replaceable():
    assert TARGETS.transport_default == "direct-wss"
    assert TARGETS.transport_challengers == ("pipecat-smallwebrtc", "streamcore")
    DirectWssConfig().validate()


def test_sequence_gate_accepts_only_exact_monotonic_frames():
    gate = VoiceTurnGate()
    gate.start("t1")
    assert gate.accept(frame("t1", 0)).type == VoiceEventType.FRAME_ACCEPTED
    assert gate.accept(frame("t1", 0)).detail == "duplicate_or_late_seq"
    gap = gate.accept(frame("t1", 2))
    assert gap.type == VoiceEventType.FRAME_DROPPED
    assert gap.detail == "seq_gap_expected_1"
    assert gate.accept(frame("t1", 1)).type == VoiceEventType.FRAME_ACCEPTED


def test_foreign_and_old_turn_audio_is_dropped():
    gate = VoiceTurnGate()
    gate.start("new")
    event = gate.accept(frame("old", 0))
    assert event.type == VoiceEventType.FRAME_DROPPED
    assert event.detail == "late_or_foreign_turn"


def test_cancel_is_terminal_and_drops_late_audio():
    gate = VoiceTurnGate()
    gate.start("t1")
    gate.accept(frame("t1", 0))
    event = gate.cancel("t1")
    assert event.type == VoiceEventType.TURN_CANCELLED
    assert gate.state == TurnState.CANCELLED
    late = gate.accept(frame("t1", 1))
    assert late.type == VoiceEventType.FRAME_DROPPED
    assert late.detail == "turn_cancelled"
    with pytest.raises(RuntimeError):
        gate.complete("t1")


def test_new_turn_resets_sequence_space():
    gate = VoiceTurnGate()
    gate.start("one")
    gate.accept(frame("one", 0))
    gate.complete("one")
    gate.start("two")
    assert gate.accept(frame("two", 0)).type == VoiceEventType.FRAME_ACCEPTED
