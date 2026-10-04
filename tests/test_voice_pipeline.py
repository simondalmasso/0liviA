import asyncio
from collections.abc import AsyncIterator

import pytest

from olivia.voice import AudioFrame, TurnState, VoiceEvent, VoiceEventType, VoicePipeline
from olivia.voice.baseline import AdaptiveSilenceEndpoint


class MemTransport:
    def __init__(self):
        self.events = []
        self.closed = False
        self.incoming = asyncio.Queue()

    async def recv(self):
        while True:
            item = await self.incoming.get()
            if item is None:
                return
            yield item

    async def send_event(self, event):
        self.events.append(event)

    async def close(self):
        self.closed = True


class ScriptVAD:
    def __init__(self):
        self.n = 0

    def process(self, frame):
        self.n += 1
        return (self.n == 1, self.n == 2)

    def reset(self):
        self.n = 0


class ScriptEndpoint:
    def __init__(self):
        self.calls = 0

    def update(self, *, speaking, now_ms):
        if speaking:
            return False
        self.calls += 1
        return self.calls >= 1

    def reset(self):
        self.calls = 0


class ScriptSTT:
    def __init__(self):
        self.reset_count = 0

    async def push(self, frame):
        return "ho" if frame.seq == 0 else None

    async def finalize(self):
        return "hola"

    async def reset(self):
        self.reset_count += 1


class ScriptTTS:
    def __init__(self):
        self.cancel_count = 0

    async def stream(self, text, *, locale):
        assert locale == "es-AR"
        yield ("audio:" + text).encode()

    async def cancel(self):
        self.cancel_count += 1


class ScriptLLM:
    async def stream(self, text, *, turn_id):
        assert text == "hola"
        yield "respuesta"


class SlowLLM:
    def __init__(self):
        self.started = asyncio.Event()

    async def stream(self, text, *, turn_id):
        self.started.set()
        await asyncio.sleep(10)
        yield "late"


def frame(turn_id, seq):
    return AudioFrame(turn_id=turn_id, seq=seq, pcm_s16le=b"\x00\x00" * 160)


@pytest.mark.asyncio
async def test_pipeline_turn_uses_typed_events_and_completes():
    transport = MemTransport()
    pipeline = VoicePipeline(
        transport, ScriptVAD(), ScriptEndpoint(), ScriptSTT(), ScriptTTS(), ScriptLLM()
    )
    await pipeline.start_turn("t1")
    await pipeline.handle_frame(frame("t1", 0))
    await pipeline.handle_frame(frame("t1", 1))
    await pipeline.wait_response()

    kinds = [event.type for event in transport.events]
    assert VoiceEventType.STT_PARTIAL in kinds
    assert VoiceEventType.STT_FINAL in kinds
    assert VoiceEventType.LLM_TEXT in kinds
    assert VoiceEventType.TTS_AUDIO in kinds
    assert kinds[-1] == VoiceEventType.TURN_COMPLETED
    assert pipeline.gate.state == TurnState.COMPLETED

    late = await pipeline.handle_frame(frame("t1", 2))
    assert late.type == VoiceEventType.FRAME_DROPPED


@pytest.mark.asyncio
async def test_cancel_propagates_and_prevents_late_completion():
    transport = MemTransport()
    tts = ScriptTTS()
    llm = SlowLLM()
    pipeline = VoicePipeline(
        transport, ScriptVAD(), ScriptEndpoint(), ScriptSTT(), tts, llm
    )
    await pipeline.start_turn("t1")
    await pipeline.handle_frame(frame("t1", 0))
    await pipeline.handle_frame(frame("t1", 1))
    await asyncio.wait_for(llm.started.wait(), timeout=1)

    event = await pipeline.cancel("t1")
    assert event.type == VoiceEventType.TURN_CANCELLED
    assert pipeline.gate.state == TurnState.CANCELLED
    assert tts.cancel_count >= 1
    assert VoiceEventType.TURN_COMPLETED not in [e.type for e in transport.events]

    late = await pipeline.handle_frame(frame("t1", 2))
    assert late.type == VoiceEventType.FRAME_DROPPED


@pytest.mark.asyncio
async def test_starting_new_turn_cancels_previous_turn():
    transport = MemTransport()
    tts = ScriptTTS()
    pipeline = VoicePipeline(
        transport, ScriptVAD(), ScriptEndpoint(), ScriptSTT(), tts, ScriptLLM()
    )
    await pipeline.start_turn("old")
    await pipeline.start_turn("new")
    assert pipeline.active_turn_id == "new"
    assert tts.cancel_count == 1
    old = await pipeline.handle_frame(frame("old", 0))
    assert old.type == VoiceEventType.FRAME_DROPPED
    assert old.detail == "late_or_foreign_turn"


def test_adaptive_endpoint_never_fires_immediately_after_reset():
    eot = AdaptiveSilenceEndpoint(silence_ms=100)
    assert eot.update(speaking=False, now_ms=0) is False
    assert eot.update(speaking=False, now_ms=99) is False
    assert eot.update(speaking=False, now_ms=100) is True
    assert eot.update(speaking=False, now_ms=200) is False
    eot.reset()
    assert eot.update(speaking=False, now_ms=1000) is False
