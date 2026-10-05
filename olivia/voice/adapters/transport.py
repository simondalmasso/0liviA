from __future__ import annotations

import json
import struct
from typing import Any

from aiohttp import WSMsgType, web

from ..contracts import AudioFrame, VoiceEvent, VoiceEventType

_HEADER = struct.Struct(">I")
_MAX_HEADER = 16 * 1024


class DirectWssConfig:
    """Configuration for the default direct Browser <-> Oracle WSS transport."""

    def __init__(
        self,
        path: str = "/api/voice/ws",
        max_audio_frame_bytes: int = 64 * 1024,
        ping_interval_s: float = 20.0,
        receive_timeout_s: float = 45.0,
    ) -> None:
        self.path = path
        self.max_audio_frame_bytes = int(max_audio_frame_bytes)
        self.ping_interval_s = float(ping_interval_s)
        self.receive_timeout_s = float(receive_timeout_s)
        self.validate()

    def validate(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("voice WSS path must be absolute")
        if self.max_audio_frame_bytes < 1024:
            raise ValueError("audio frame limit too small")
        if self.ping_interval_s <= 0 or self.receive_timeout_s <= 0:
            raise ValueError("timeouts must be positive")


class WireCodec:
    """Direct Browser <-> Oracle WSS wire format."""

    @staticmethod
    def encode_audio(frame: AudioFrame) -> bytes:
        header = json.dumps(
            {
                "turn_id": frame.turn_id,
                "seq": frame.seq,
                "sample_rate": frame.sample_rate,
                "channels": frame.channels,
                "client_ts_ms": frame.client_ts_ms,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        if len(header) > _MAX_HEADER:
            raise ValueError("audio header too large")
        return _HEADER.pack(len(header)) + header + frame.pcm_s16le

    @staticmethod
    def decode_audio(payload: bytes) -> AudioFrame:
        if len(payload) < _HEADER.size:
            raise ValueError("audio frame too short")
        (size,) = _HEADER.unpack_from(payload)
        if size <= 0 or size > _MAX_HEADER:
            raise ValueError("invalid audio header size")
        end = _HEADER.size + size
        if end > len(payload):
            raise ValueError("truncated audio header")
        try:
            meta: dict[str, Any] = json.loads(payload[_HEADER.size:end].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid audio header JSON") from exc
        try:
            return AudioFrame(
                turn_id=str(meta["turn_id"]),
                seq=int(meta["seq"]),
                sample_rate=int(meta.get("sample_rate", 16_000)),
                channels=int(meta.get("channels", 1)),
                client_ts_ms=(
                    None if meta.get("client_ts_ms") is None else float(meta["client_ts_ms"])
                ),
                pcm_s16le=payload[end:],
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid audio header fields") from exc

    @staticmethod
    def encode_event(event: VoiceEvent) -> str:
        return json.dumps(
            {
                "type": event.type.value,
                "turn_id": event.turn_id,
                "seq": event.seq,
                "text": event.text,
                "detail": event.detail,
                "meta": event.meta,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def decode_event(payload: str) -> VoiceEvent:
        try:
            raw = json.loads(payload)
            event_type = VoiceEventType(str(raw["type"]))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise ValueError("invalid voice event") from exc
        return VoiceEvent(
            type=event_type,
            turn_id=str(raw.get("turn_id") or ""),
            seq=None if raw.get("seq") is None else int(raw["seq"]),
            text=None if raw.get("text") is None else str(raw["text"]),
            detail=None if raw.get("detail") is None else str(raw["detail"]),
            meta=dict(raw.get("meta") or {}),
        )


class AiohttpWebSocketTransport:
    """Concrete direct-WSS media transport; no speech/model dependency."""

    def __init__(
        self,
        ws: web.WebSocketResponse,
        *,
        max_audio_frame_bytes: int = 64 * 1024,
    ):
        self.ws = ws
        self.max_audio_frame_bytes = max_audio_frame_bytes

    async def recv(self):
        async for message in self.ws:
            if message.type == WSMsgType.TEXT:
                yield WireCodec.decode_event(str(message.data))
            elif message.type == WSMsgType.BINARY:
                payload = bytes(message.data)
                if len(payload) > self.max_audio_frame_bytes + _MAX_HEADER + _HEADER.size:
                    raise ValueError("audio frame too large")
                yield WireCodec.decode_audio(payload)
            elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
                return

    async def send_event(self, event: VoiceEvent) -> None:
        await self.ws.send_str(WireCodec.encode_event(event))

    async def send_audio(self, frame: AudioFrame) -> None:
        await self.ws.send_bytes(WireCodec.encode_audio(frame))

    async def close(self) -> None:
        await self.ws.close()
