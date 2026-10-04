from __future__ import annotations

import asyncio
import struct
from collections.abc import AsyncIterator

import pytest

from olivia.voice.adapters.endpointing import AdaptiveSilenceEndpoint
from olivia.voice.adapters.vad import EnergyVAD
from olivia.voice.contracts import AudioFrame, SequenceDecision, TranscriptChunk, VoiceEvent
from olivia.voice.pipeline import VoicePipeline


def pcm(value: int, samples: int = 160) -> bytes:
    return struct.pack("<" + "h" * samples, *([value] * samples))


class MemoryTransport:
    def __init__(self):
        self.events: list[VoiceEvent] = []
        self.audio: list[AudioFrame] = []

    async def recv(self):
        if False:
            yield None

    async def send_event(self, event):
        self.events.append(event)

    async def send_audio(self, frame):
        self.audio.append(frame)

    async def close(self):
        pass


class FakeSTT:
    def __init__(self):
        self.cancelled = False
        self.frames = 0

    async def start(self, turn_id, *, locale):
        self.cancelled = False
        self.frames = 0

    async def accept(self, frame):
        self.frames += 1
        return [TranscriptChunk("hola", False)] if self.frames == 2 else []

    async def finish(self):
        return TranscriptChunk("hola mundo", True)

    async def cancel(self):
        self.cancelled = True


class FakeTTS:
    def __init__(self):
        self.cancelled = False

    async def stream(self, text, *, turn_id, locale, voice=None):
        async for _token in text:
            await asyncio.sleep(0)
        yield pcm(50)

    async def cancel(self):
        self.cancelled = True


async def llm_stream(text: str, locale: str) -> AsyncIterator[str]:
    assert text == "hola mundo"
    assert locale == "es-AR"
    yield "qué"
    await asyncio.sleep(0)
    yield " tal"


def make_pipeline():
    transport = MemoryTransport()
    stt = FakeSTT()
    tts = FakeTTS()
    pipe = VoicePipeline(
        transport=transport,
        vad=EnergyVAD(start_rms=500, end_rms=200, start_frames=1, end_frames=1),
        endpoint=AdaptiveSilenceEndpoint(silence_ms=20, floor_ms=20, ceiling_ms=100),
        stt=stt,
        tts=tts,
        llm_stream=llm_stream,
    )
    return pipe, transport, stt, tts


@pytest.mark.asyncio
async def test_sequence_gate_rejects_wrong_duplicate_and_late_frames():
    pipe, transport, stt, tts = make_pipeline()
    await pipe.start_turn("a")

    assert await pipe.accept_audio(AudioFrame("wrong", 0, pcm(0))) is SequenceDecision.WRONG_TURN
    assert await pipe.accept_audio(AudioFrame("a", 0, pcm(1000))) is SequenceDecision.ACCEPT
    assert await pipe.accept_audio(AudioFrame("a", 0, pcm(1000))) is SequenceDecision.OUT_OF_ORDER

    assert await pipe.cancel_turn("a") is True
    assert await pipe.accept_audio(AudioFrame("a", 1, pcm(0))) is SequenceDecision.CANCELLED
    assert pipe.dropped_audio == 3


@pytest.mark.asyncio
async def test_end_to_end_turn_emits_text_audio_and_completion():
    pipe, transport, stt, tts = make_pipeline()
    await pipe.start_turn("a")
    await pipe.accept_audio(AudioFrame("a", 0, pcm(1000)))
    await pipe.accept_audio(AudioFrame("a", 1, pcm(1000)))
    await pipe.accept_audio(AudioFrame("a", 2, pcm(0)))
    await pipe.accept_audio(AudioFrame("a", 3, pcm(0)))

    assert pipe._generation is not None
    await pipe._generation

    kinds = [event.type.value for event in transport.events]
    assert "speech_started" in kinds
    assert "speech_ended" in kinds
    assert "stt_partial" in kinds
    assert "stt_final" in kinds
    assert kinds.count("llm_delta") == 2
    assert kinds[-1] == "turn_completed"
    assert len(transport.audio) == 1


@pytest.mark.asyncio
async def test_cancel_propagates_to_stt_tts_and_stops_generation():
    pipe, transport, stt, tts = make_pipeline()
    await pipe.start_turn("a")
    assert await pipe.cancel_turn("a") is True
    assert stt.cancelled is True
    assert tts.cancelled is True
    assert transport.events[-1].type.value == "cancelled"
