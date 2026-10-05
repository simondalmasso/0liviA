# Voice v1 — contract and benchmark gates

Status: **contracts integrated; speech engines and transport deployment remain benchmark-gated**.

## Hot path

Browser microphone → direct WSS → Oracle A1 → VAD → endpointing → STT → existing model router → TTS → WSS audio.

Cloudflare and the owner's PC are not part of this hot path.

## Contract

Every microphone frame carries:
- `turn_id`;
- monotonically increasing `seq`;
- PCM signed-16 little-endian audio;
- sample rate and channel count.

The server rejects frames from the wrong/cancelled turn and rejects duplicate/out-of-order sequence numbers. Barge-in cancels the current generation/STT/TTS pipeline and late frames are ignored.

## Candidates, not dependencies

VAD: Silero ONNX.  
STT: Moonshine local; Groq Whisper quota lane; whisper.cpp fallback.  
TTS: Pocket TTS first challenger; maintained Piper fallback; Kokoro/MOSS quality challengers.

The Python control plane does not import these engines. Each must be an optional adapter so a model/runtime failure cannot take down text chat.

## es-AR acceptance

Generic `es` support is **not** a voice-quality pass. A production voice must be tested for exact `es-AR` suitability, including voseo cadence, pronunciation, yeísmo and perceived warmth. The core locale policy defaults to `es-AR`.

## Transport bake-off

Direct WSS is v1 default. Pipecat SmallWebRTC is challenger A; StreamCore is challenger B.

All transports must run the same speech adapters and script. Record:
- connect/reconnect;
- partial STT latency;
- end-of-turn latency;
- model TTFT;
- TTS TTFA;
- cancel/barge-in latency;
- CPU/RAM;
- 60-minute stability;
- mobile/cellular loss/reconnect behavior.

Do not switch away from WSS unless a challenger materially wins on the actual 2-OCPU / 12-GB A1.

## Targets

- first audio p50 <= 1.5 s;
- client playback stop <= 150 ms;
- server cancellation <= 300 ms;
- 60-minute soak without meaningful RSS growth;
- no cross-turn audio leakage or duplicate output.
