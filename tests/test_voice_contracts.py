from __future__ import annotations

import struct

from olivia.voice.adapters.endpointing import AdaptiveSilenceEndpoint
from olivia.voice.adapters.transport import DirectWssConfig, WireCodec
from olivia.voice.adapters.vad import EnergyVAD
from olivia.voice.contracts import AudioFrame, VoiceEvent, VoiceEventType
from olivia.voice.locale import LocalePolicy, VoiceCandidate


def pcm(value: int, samples: int = 160) -> bytes:
    return struct.pack("<" + "h" * samples, *([value] * samples))


def test_audio_frame_duration_and_wire_roundtrip():
    frame = AudioFrame("t1", 7, pcm(100, 320), sample_rate=16_000)
    assert frame.duration_ms == 20.0
    assert WireCodec.decode_audio(WireCodec.encode_audio(frame)) == frame


def test_event_wire_roundtrip_preserves_unicode():
    event = VoiceEvent(VoiceEventType.STT_PARTIAL, "t1", seq=3, text="¿Cómo andás?")
    assert WireCodec.decode_event(WireCodec.encode_event(event)) == event


def test_energy_vad_start_end_hysteresis():
    vad = EnergyVAD(start_rms=800, end_rms=350, start_frames=2, end_frames=2)
    quiet = AudioFrame("t", 0, pcm(0))
    loud = AudioFrame("t", 1, pcm(3000))

    assert vad.accept(quiet) == (False, False)
    assert vad.accept(loud) == (False, False)
    assert vad.accept(AudioFrame("t", 2, pcm(3000))) == (True, False)
    assert vad.speaking is True
    assert vad.accept(AudioFrame("t", 3, pcm(0))) == (False, False)
    assert vad.accept(AudioFrame("t", 4, pcm(0))) == (False, True)
    assert vad.speaking is False


def test_endpoint_fires_once_after_real_speech():
    eot = AdaptiveSilenceEndpoint(silence_ms=40, floor_ms=20, ceiling_ms=100)
    assert eot.observe(speaking=False, frame_ms=20) is False
    assert eot.observe(speaking=True, frame_ms=20) is False
    assert eot.observe(speaking=False, frame_ms=20) is False
    assert eot.observe(speaking=False, frame_ms=20) is True
    assert eot.observe(speaking=False, frame_ms=20) is False


def test_es_ar_voice_gate_rejects_generic_spanish_only():
    policy = LocalePolicy()
    generic = VoiceCandidate("generic", "piper", ("es",), True, True)
    exact = VoiceCandidate("rioplatense", "candidate", ("es-AR",), True, True)
    assert policy.voice_accepted(generic) is False
    assert policy.voice_accepted(exact) is True


def test_direct_wss_config_is_small_and_absolute():
    cfg = DirectWssConfig()
    assert cfg.path == "/api/voice/ws"
    assert cfg.max_audio_frame_bytes == 64 * 1024
