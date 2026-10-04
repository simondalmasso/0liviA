# Voice contract v1

Status: **contracts integrated; production speech adapters not yet selected**.

The default realtime path is direct WSS between the browser and Oracle. The browser is only a microphone/playback/UI client; no local filesystem, shell, extension, localhost agent, or background service is part of 0liviA.

Every microphone frame carries `turn_id` + monotonic `seq`. The server rejects foreign, duplicate, late and gap frames before STT. Cancellation is terminal for the active turn, so late STT/TTS/audio cannot leak into the next turn.

Speech engines remain adapters and are benchmark-gated on the actual A1:
- VAD: Silero ONNX target.
- STT: Moonshine preferred local candidate; whisper.cpp fallback; Groq Whisper quota lane.
- TTS: Pocket TTS preferred candidate; Piper fallback; Kokoro/MOSS challengers.
- Locale acceptance is explicit `es-AR`, not generic Spanish.

Transport challengers remain Pipecat SmallWebRTC and StreamCore. They replace only the transport adapter if measured mobile/jitter/latency results beat direct WSS.

Required benchmark marks are represented by `VoiceBenchmark`: connect, partial STT, EOT, LLM TTFT, TTS TTFA, cancellation latency, RSS and CPU samples. A 60-minute soak on Oracle is still required before production voice is declared ready.


## Pipeline contract

`VoicePipeline` now connects the contracts without choosing heavy speech engines. It:
- shares the normal text `Agent` through `AgentVoiceLLM`, so voice and text use the same session/memory/router;
- accepts only the active `turn_id` and exact monotonic audio sequence;
- makes cancellation terminal and cancels pending response/TTS work;
- treats barge-in as immediate cancellation, then requires a fresh client turn;
- emits transcript, LLM text, TTS audio and completion as typed events;
- never makes the owner's PC part of the compute/storage plane.

`EnergyVAD` and `AdaptiveSilenceEndpoint` are dependency-free baselines for tests/bring-up only. Production VAD/STT/TTS remain benchmark-gated.
