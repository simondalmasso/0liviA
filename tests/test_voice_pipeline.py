from __future__ import annotations

import asyncio

import pytest

from olivia.voice import (
    AudioFrame,
    SequenceDecision,
    TurnState,
    TranscriptChunk,
    VoiceEventType,
    VoicePipeline,
)
from olivia.voice.adapters.endpointing import AdaptiveSilenceEndpoint
from olivia.voice.adapters.vad import EnergyVAD


class MemoryTransport:
    def __init__(self):
        self.events = []
        self.audio = []

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
        assert locale == "es-AR"
        self.cancelled = False
        self.frames = 0

    async def accept(self, frame):
        self.frames += 1
        return [TranscriptChunk("ho", False)] if self.frames == 1 else []

    async def finish(self):
        return TranscriptChunk("hola", True)

    async def cancel(self):
        self.cancelled = True


class FakeTTS:
    def __init__(self):
        self.cancelled = False

    async def stream(self, text, *, turn_id, locale, voice=None):
        assert locale == "es-AR"
        async for token in text:
            yield ("audio:" + token).encode()

    async def cancel(self):
        self.cancelled = True


class FakeLLM:
    async def stream(self, text, *, turn_id, locale):
        assert text == "hola"
        assert locale == "es-AR"
        yield "respuesta"


class SlowLLM:
    def __init__(self):
        self.started = asyncio.Event()

    async def stream(self, text, *, turn_id, locale):
        self.started.set()
        await asyncio.sleep(10)
        yield "late"


def frame(turn_id, seq, value=0):
    sample = int(value).to_bytes(2, "little", signed=True)
    return AudioFrame(turn_id=turn_id, seq=seq, pcm_s16le=sample * 160)


def make_pipeline(llm=None):
    transport = MemoryTransport()
    stt = FakeSTT()
    tts = FakeTTS()
    pipe = VoicePipeline(
        transport=transport,
        vad=EnergyVAD(
            start_rms=500,
            end_rms=200,
            start_frames=1,
            end_frames=1,
        ),
        endpoint=AdaptiveSilenceEndpoint(
            silence_ms=20,
            floor_ms=20,
            ceiling_ms=100,
        ),
        stt=stt,
        tts=tts,
        llm=llm or FakeLLM(),
    )
    return pipe, transport, stt, tts


@pytest.mark.asyncio
async def test_pipeline_runs_shared_turn_to_audio_completion():
    pipe, transport, stt, tts = make_pipeline()
    await pipe.start_turn("t1")
    assert await pipe.accept_audio(frame("t1", 0, 1000)) is SequenceDecision.ACCEPT
    assert await pipe.accept_audio(frame("t1", 1, 0)) is SequenceDecision.ACCEPT
    assert await pipe.accept_audio(frame("t1", 2, 0)) is SequenceDecision.ACCEPT
    assert pipe._generation is not None
    await pipe._generation

    kinds = [event.type for event in transport.events]
    assert VoiceEventType.STT_PARTIAL in kinds
    assert VoiceEventType.STT_FINAL in kinds
    assert VoiceEventType.LLM_DELTA in kinds
    assert kinds[-1] == VoiceEventType.TURN_COMPLETED
    assert pipe._turn is not None and pipe._turn.state == TurnState.COMPLETE
    assert len(transport.audio) == 1


@pytest.mark.asyncio
async def test_sequence_is_exact_and_late_or_gap_audio_drops():
    pipe, transport, stt, tts = make_pipeline()
    await pipe.start_turn("t1")
    assert await pipe.accept_audio(frame("wrong", 0)) is SequenceDecision.WRONG_TURN
    assert await pipe.accept_audio(frame("t1", 1)) is SequenceDecision.OUT_OF_ORDER
    assert await pipe.accept_audio(frame("t1", 0)) is SequenceDecision.ACCEPT
    assert await pipe.accept_audio(frame("t1", 0)) is SequenceDecision.OUT_OF_ORDER
    assert pipe.dropped_audio == 3


@pytest.mark.asyncio
async def test_cancel_propagates_and_blocks_late_audio():
    slow = SlowLLM()
    pipe, transport, stt, tts = make_pipeline(slow)
    await pipe.start_turn("t1")
    await pipe.accept_audio(frame("t1", 0, 1000))
    await pipe.accept_audio(frame("t1", 1, 0))
    await pipe.accept_audio(frame("t1", 2, 0))
    assert pipe._generation is not None
    await asyncio.wait_for(slow.started.wait(), timeout=1)

    assert await pipe.cancel_turn("t1") is True
    assert stt.cancelled is True
    assert tts.cancelled is True
    assert pipe._turn is not None and pipe._turn.state == TurnState.CANCELLED
    assert transport.events[-1].type == VoiceEventType.CANCELLED
    assert await pipe.accept_audio(frame("t1", 3)) is SequenceDecision.CANCELLED


@pytest.mark.asyncio
async def test_starting_new_turn_cancels_previous():
    pipe, transport, stt, tts = make_pipeline()
    await pipe.start_turn("old")
    await pipe.start_turn("new")
    assert pipe.active_turn_id == "new"
    assert tts.cancelled is True
    assert stt.cancelled is False
