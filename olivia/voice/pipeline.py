from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .adapters.base import (
    EndpointDetector,
    SpeechToText,
    TextToSpeech,
    VoiceActivityDetector,
    VoiceTransport,
)
from .contracts import AudioFrame, SequenceDecision, TurnState, VoiceEvent, VoiceEventType
from .llm import VoiceLLM
from .locale import ES_AR


@dataclass
class _Turn:
    turn_id: str
    state: TurnState = TurnState.LISTENING
    last_seq: int = -1
    cancelled: bool = False


class VoicePipeline:
    """Single dependency-light realtime coordinator for 0liviA voice."""

    def __init__(
        self,
        *,
        transport: VoiceTransport,
        vad: VoiceActivityDetector,
        endpoint: EndpointDetector,
        stt: SpeechToText,
        tts: TextToSpeech,
        llm: VoiceLLM,
        locale: str = ES_AR,
        voice: str | None = None,
    ) -> None:
        if locale.strip().lower().replace("_", "-") != "es-ar":
            raise ValueError("voice pipeline locale must be es-AR")
        self.transport = transport
        self.vad = vad
        self.endpoint = endpoint
        self.stt = stt
        self.tts = tts
        self.llm = llm
        self.locale = locale
        self.voice = voice
        self._turn: _Turn | None = None
        self._generation: asyncio.Task[None] | None = None
        self.dropped_audio = 0

    @property
    def active_turn_id(self) -> str | None:
        return self._turn.turn_id if self._turn else None

    async def start_turn(self, turn_id: str) -> None:
        if not turn_id or len(turn_id) > 128:
            raise ValueError("invalid turn_id")
        if self._turn and self._turn.state not in {TurnState.CANCELLED, TurnState.COMPLETE}:
            await self.cancel_turn(self._turn.turn_id)
        self.vad.reset()
        self.endpoint.reset()
        await self.stt.start(turn_id, locale=self.locale)
        self._turn = _Turn(turn_id)
        await self.transport.send_event(VoiceEvent(VoiceEventType.TURN_STARTED, turn_id))

    def sequence_decision(self, frame: AudioFrame) -> SequenceDecision:
        turn = self._turn
        if turn is None or frame.turn_id != turn.turn_id:
            return SequenceDecision.WRONG_TURN
        if turn.cancelled or turn.state == TurnState.CANCELLED:
            return SequenceDecision.CANCELLED
        if frame.seq != turn.last_seq + 1:
            return SequenceDecision.OUT_OF_ORDER
        return SequenceDecision.ACCEPT

    async def accept_audio(self, frame: AudioFrame) -> SequenceDecision:
        decision = self.sequence_decision(frame)
        if decision is not SequenceDecision.ACCEPT:
            self.dropped_audio += 1
            await self.transport.send_event(
                VoiceEvent(
                    VoiceEventType.DROPPED_AUDIO,
                    frame.turn_id,
                    seq=frame.seq,
                    detail=decision.value,
                )
            )
            return decision

        turn = self._turn
        assert turn is not None
        turn.last_seq = frame.seq

        started, ended = self.vad.accept(frame)

        if started and turn.state in {TurnState.THINKING, TurnState.SPEAKING}:
            await self.cancel_turn(turn.turn_id)
            self.dropped_audio += 1
            await self.transport.send_event(
                VoiceEvent(
                    VoiceEventType.DROPPED_AUDIO,
                    frame.turn_id,
                    seq=frame.seq,
                    detail="barge_in_requires_new_turn",
                )
            )
            return SequenceDecision.CANCELLED

        if started:
            await self.transport.send_event(
                VoiceEvent(VoiceEventType.SPEECH_STARTED, turn.turn_id, seq=frame.seq)
            )
        if ended:
            await self.transport.send_event(
                VoiceEvent(VoiceEventType.SPEECH_ENDED, turn.turn_id, seq=frame.seq)
            )

        chunks = await self.stt.accept(frame)
        for chunk in chunks:
            await self.transport.send_event(
                VoiceEvent(
                    VoiceEventType.STT_FINAL if chunk.final else VoiceEventType.STT_PARTIAL,
                    turn.turn_id,
                    seq=frame.seq,
                    text=chunk.text,
                )
            )

        if self.endpoint.observe(speaking=self.vad.speaking, frame_ms=frame.duration_ms):
            final = await self.stt.finish()
            if final.text:
                await self.transport.send_event(
                    VoiceEvent(
                        VoiceEventType.STT_FINAL,
                        turn.turn_id,
                        seq=frame.seq,
                        text=final.text,
                    )
                )
            turn.state = TurnState.THINKING
            self._generation = asyncio.create_task(self._generate(turn.turn_id, final.text))
        return decision

    async def _generate(self, turn_id: str, user_text: str) -> None:
        turn = self._turn
        if turn is None or turn.turn_id != turn_id or turn.cancelled:
            return

        async def text_stream():
            async for token in self.llm.stream(
                user_text,
                turn_id=turn_id,
                locale=self.locale,
            ):
                current = self._turn
                if current is None or current.turn_id != turn_id or current.cancelled:
                    raise asyncio.CancelledError
                await self.transport.send_event(
                    VoiceEvent(VoiceEventType.LLM_DELTA, turn_id, text=token)
                )
                yield token

        try:
            turn.state = TurnState.SPEAKING
            seq = 0
            async for pcm in self.tts.stream(
                text_stream(),
                turn_id=turn_id,
                locale=self.locale,
                voice=self.voice,
            ):
                current = self._turn
                if current is None or current.turn_id != turn_id or current.cancelled:
                    return
                await self.transport.send_audio(
                    AudioFrame(turn_id=turn_id, seq=seq, pcm_s16le=pcm)
                )
                seq += 1
            current = self._turn
            if current and current.turn_id == turn_id and not current.cancelled:
                current.state = TurnState.COMPLETE
                await self.transport.send_event(
                    VoiceEvent(VoiceEventType.TURN_COMPLETED, turn_id)
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            current = self._turn
            if current and current.turn_id == turn_id and not current.cancelled:
                await self.transport.send_event(
                    VoiceEvent(VoiceEventType.ERROR, turn_id, detail=type(exc).__name__)
                )

    async def cancel_turn(self, turn_id: str) -> bool:
        turn = self._turn
        if turn is None or turn.turn_id != turn_id:
            return False
        if turn.cancelled:
            return True
        turn.cancelled = True
        turn.state = TurnState.CANCELLED
        if self._generation and not self._generation.done():
            self._generation.cancel()
            try:
                await self._generation
            except asyncio.CancelledError:
                pass
        await self.stt.cancel()
        await self.tts.cancel()
        await self.transport.send_event(VoiceEvent(VoiceEventType.CANCELLED, turn_id))
        return True

    async def run(self) -> None:
        async for item in self.transport.recv():
            if isinstance(item, AudioFrame):
                await self.accept_audio(item)
            elif item.type == VoiceEventType.TURN_STARTED:
                await self.start_turn(item.turn_id)
            elif item.type == VoiceEventType.CANCELLED:
                await self.cancel_turn(item.turn_id)
