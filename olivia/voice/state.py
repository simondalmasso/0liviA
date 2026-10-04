from __future__ import annotations

import secrets
from dataclasses import dataclass

from .contracts import AudioFrame, TurnState, VoiceEvent, VoiceEventType


@dataclass(slots=True)
class _Turn:
    turn_id: str
    expected_seq: int = 0
    state: TurnState = TurnState.LISTENING


class VoiceTurnGate:
    """Small deterministic guard in front of every voice pipeline.

    It prevents old/foreign audio from leaking into a new turn, enforces
    monotonic frame order, and makes cancellation terminal for that turn.
    """

    def __init__(self) -> None:
        self._turn: _Turn | None = None

    @property
    def active_turn_id(self) -> str | None:
        return self._turn.turn_id if self._turn else None

    @property
    def state(self) -> TurnState:
        return self._turn.state if self._turn else TurnState.IDLE

    def start(self, turn_id: str | None = None) -> VoiceEvent:
        turn_id = turn_id or secrets.token_urlsafe(12)
        if not turn_id or len(turn_id) > 128:
            raise ValueError("invalid turn_id")
        self._turn = _Turn(turn_id=turn_id)
        return VoiceEvent(VoiceEventType.TURN_STARTED, turn_id)

    def accept(self, frame: AudioFrame) -> VoiceEvent:
        frame.validate()
        turn = self._turn
        if turn is None:
            return VoiceEvent(
                VoiceEventType.FRAME_DROPPED,
                frame.turn_id,
                seq=frame.seq,
                detail="no_active_turn",
            )
        if frame.turn_id != turn.turn_id:
            return VoiceEvent(
                VoiceEventType.FRAME_DROPPED,
                frame.turn_id,
                seq=frame.seq,
                detail="late_or_foreign_turn",
            )
        if turn.state in {TurnState.CANCELLED, TurnState.COMPLETED}:
            return VoiceEvent(
                VoiceEventType.FRAME_DROPPED,
                frame.turn_id,
                seq=frame.seq,
                detail=f"turn_{turn.state.value}",
            )
        if frame.seq < turn.expected_seq:
            return VoiceEvent(
                VoiceEventType.FRAME_DROPPED,
                frame.turn_id,
                seq=frame.seq,
                detail="duplicate_or_late_seq",
            )
        if frame.seq > turn.expected_seq:
            return VoiceEvent(
                VoiceEventType.FRAME_DROPPED,
                frame.turn_id,
                seq=frame.seq,
                detail=f"seq_gap_expected_{turn.expected_seq}",
            )
        turn.expected_seq += 1
        return VoiceEvent(
            VoiceEventType.FRAME_ACCEPTED,
            frame.turn_id,
            seq=frame.seq,
        )

    def responding(self, turn_id: str) -> None:
        turn = self._require(turn_id)
        if turn.state == TurnState.LISTENING:
            turn.state = TurnState.RESPONDING

    def cancel(self, turn_id: str) -> VoiceEvent:
        turn = self._require(turn_id)
        if turn.state not in {TurnState.CANCELLED, TurnState.COMPLETED}:
            turn.state = TurnState.CANCELLED
        return VoiceEvent(VoiceEventType.TURN_CANCELLED, turn_id)

    def complete(self, turn_id: str) -> VoiceEvent:
        turn = self._require(turn_id)
        if turn.state == TurnState.CANCELLED:
            raise RuntimeError("cancelled turn cannot complete")
        turn.state = TurnState.COMPLETED
        return VoiceEvent(VoiceEventType.TURN_COMPLETED, turn_id)

    def _require(self, turn_id: str) -> _Turn:
        turn = self._turn
        if turn is None or turn.turn_id != turn_id:
            raise KeyError("turn is not active")
        return turn
