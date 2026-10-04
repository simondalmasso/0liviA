from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from typing import Callable

from .contracts import (
    AudioFrame,
    TurnState,
    VoiceEndpointing,
    VoiceEvent,
    VoiceEventType,
    VoiceSTT,
    VoiceTTS,
    VoiceTransport,
    VoiceVAD,
)
from .llm import VoiceLLM
from .locale import DEFAULT_LOCALE
from .state import VoiceTurnGate


class VoicePipeline:
    """Dependency-light realtime coordinator.

    It owns sequencing/cancellation only. Media transport and speech engines stay
    replaceable, and the LLM adapter can wrap the normal text Agent so memory is shared.
    """

    def __init__(
        self,
        transport: VoiceTransport,
        vad: VoiceVAD,
        endpointing: VoiceEndpointing,
        stt: VoiceSTT,
        tts: VoiceTTS,
        llm: VoiceLLM,
        *,
        locale: str = DEFAULT_LOCALE,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if locale.lower().replace("_", "-") != "es-ar":
            raise ValueError("voice pipeline locale must be es-AR")
        self.transport = transport
        self.vad = vad
        self.endpointing = endpointing
        self.stt = stt
        self.tts = tts
        self.llm = llm
        self.locale = locale
        self.clock = clock
        self.gate = VoiceTurnGate()
        self._speaking = False
        self._response_task: asyncio.Task[None] | None = None
        self._responding_turn: str | None = None
        self._lock = asyncio.Lock()

    @property
    def active_turn_id(self) -> str | None:
        return self.gate.active_turn_id

    async def start_turn(self, turn_id: str | None = None) -> str:
        async with self._lock:
            if self.active_turn_id and self.gate.state not in {
                TurnState.CANCELLED,
                TurnState.COMPLETED,
            }:
                await self._cancel_unlocked(self.active_turn_id)
            event = self.gate.start(turn_id)
            self.vad.reset()
            self.endpointing.reset()
            await self.stt.reset()
            self._speaking = False
            self._responding_turn = None
            await self.transport.send_event(event)
            return event.turn_id

    async def handle_frame(self, frame: AudioFrame) -> VoiceEvent:
        gate_event = self.gate.accept(frame)
        await self.transport.send_event(gate_event)
        if gate_event.type == VoiceEventType.FRAME_DROPPED:
            return gate_event

        started, ended = self.vad.process(frame)

        if started and self.gate.state == TurnState.RESPONDING:
            # Barge-in is cancellation first. The client then starts a fresh turn_id.
            await self.cancel(frame.turn_id)
            return VoiceEvent(
                VoiceEventType.FRAME_DROPPED,
                frame.turn_id,
                seq=frame.seq,
                detail="barge_in_cancelled_start_new_turn",
            )

        if started:
            self._speaking = True
            self.endpointing.update(speaking=True, now_ms=self.clock() * 1000.0)
            await self.transport.send_event(
                VoiceEvent(VoiceEventType.SPEECH_STARTED, frame.turn_id, seq=frame.seq)
            )

        partial = await self.stt.push(frame)
        if partial:
            await self.transport.send_event(
                VoiceEvent(VoiceEventType.STT_PARTIAL, frame.turn_id, seq=frame.seq, text=partial)
            )

        if ended:
            self._speaking = False
            await self.transport.send_event(
                VoiceEvent(VoiceEventType.SPEECH_ENDED, frame.turn_id, seq=frame.seq)
            )

        eot = self.endpointing.update(
            speaking=self._speaking,
            now_ms=self.clock() * 1000.0,
        )
        if eot and self._responding_turn != frame.turn_id:
            self._responding_turn = frame.turn_id
            self._response_task = asyncio.create_task(self._respond(frame.turn_id))
        return gate_event

    async def cancel(self, turn_id: str) -> VoiceEvent:
        async with self._lock:
            return await self._cancel_unlocked(turn_id)

    async def _cancel_unlocked(self, turn_id: str) -> VoiceEvent:
        event = self.gate.cancel(turn_id)
        task = self._response_task
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.tts.cancel()
        await self.stt.reset()
        self.vad.reset()
        self.endpointing.reset()
        self._speaking = False
        self._responding_turn = None
        await self.transport.send_event(event)
        return event

    async def wait_response(self) -> None:
        task = self._response_task
        if task is not None:
            await task

    async def run(self) -> None:
        async for item in self.transport.recv():
            if isinstance(item, AudioFrame):
                await self.handle_frame(item)
                continue
            if item.type == VoiceEventType.TURN_STARTED:
                await self.start_turn(item.turn_id)
            elif item.type == VoiceEventType.TURN_CANCELLED:
                with contextlib.suppress(KeyError):
                    await self.cancel(item.turn_id)

    async def _respond(self, turn_id: str) -> None:
        try:
            if self.active_turn_id != turn_id or self.gate.state == TurnState.CANCELLED:
                return
            transcript = (await self.stt.finalize()).strip()
            await self.transport.send_event(
                VoiceEvent(VoiceEventType.STT_FINAL, turn_id, text=transcript)
            )
            if not transcript:
                self.gate.complete(turn_id)
                await self.transport.send_event(
                    VoiceEvent(VoiceEventType.TURN_COMPLETED, turn_id)
                )
                return

            self.gate.responding(turn_id)
            async for text_chunk in self.llm.stream(transcript, turn_id=turn_id):
                if self.active_turn_id != turn_id or self.gate.state == TurnState.CANCELLED:
                    return
                if not text_chunk:
                    continue
                await self.transport.send_event(
                    VoiceEvent(VoiceEventType.LLM_TEXT, turn_id, text=text_chunk)
                )
                async for audio in self.tts.stream(text_chunk, locale=self.locale):
                    if self.active_turn_id != turn_id or self.gate.state == TurnState.CANCELLED:
                        return
                    if audio:
                        await self.transport.send_event(
                            VoiceEvent(VoiceEventType.TTS_AUDIO, turn_id, audio=audio)
                        )

            if self.active_turn_id == turn_id and self.gate.state != TurnState.CANCELLED:
                event = self.gate.complete(turn_id)
                await self.transport.send_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self.active_turn_id == turn_id and self.gate.state != TurnState.CANCELLED:
                await self.transport.send_event(
                    VoiceEvent(
                        VoiceEventType.ERROR,
                        turn_id,
                        detail=type(exc).__name__,
                    )
                )
