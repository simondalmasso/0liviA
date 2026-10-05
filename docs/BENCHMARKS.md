# Benchmark gates

Architecture is provisional where this file says MEASURE.

## Core

| Gate | Target |
|---|---:|
| idle core RSS | < 150 MB |
| cold start | < 5 s |
| bounded recent-context query | < 20 ms p95 at 20k messages |
| FTS memory recall | < 30 ms p95 at 10k memories |
| restart/session recovery | 100% |
| provider failover before token | < 1 s plus failed-lane network time |
| user cancel | no fallback, no duplicate answer |

## Coding worker

Scenarios:
- unfamiliar repo comprehension;
- one-file bug;
- multi-file feature;
- failing CI diagnosis;
- browser regression;
- interrupted job resume;
- provider loss mid-job.

Record success, retries, wall time, tool calls, human intervention and regression count.

## Voice transport bake-off

Compare on the actual A1:
1. direct WSS;
2. Pipecat SmallWebRTC;
3. StreamCore.

Use the exact same STT/turn/LLM/TTS adapters so the transport is the only variable.

Measure:
- connect/reconnect;
- audio jitter/drop;
- CPU/RAM;
- cancellation latency;
- 60-minute stability;
- mobile/cellular behavior.

Default remains WSS unless a challenger materially wins.

## Speech bake-off

STT:
- Moonshine local;
- Groq Whisper quota lane;
- whisper.cpp local fallback.

TTS:
- Pocket TTS;
- maintained Piper;
- Kokoro;
- MOSS-TTS-Nano if it fits.

Measure Spanish/Rioplatense-specific quality with the same owner-authored script:
- WER/transcription mistakes;
- false endpoint cuts;
- TTFA;
- real-time factor;
- CPU/RAM;
- subjective warmth/naturalness;
- Argentine pronunciation/cadence.

## Acceptance

Do not label voice “Live-like” until:
- first audio p50 <= 1.5 s;
- client barge-in silence <= 150 ms;
- server cancellation <= 300 ms;
- 60-minute soak clean;
- Spanish false-cut rate acceptable to the owner.


## Local model quality floor

A local model is never promoted merely because it is free.

Candidates:
- Meta Muse Glimmer 30B on suitable GPU / high-memory host;
- current small Qwen profiles remain emergency/recovery baselines only.

For an always-on local model to become the normal chat/coding route, record:
- tool-call correctness;
- agent-task completion;
- code benchmark success/regression rate;
- long-context stability;
- es-AR response quality;
- TTFT/tokens-per-second;
- RAM/VRAM footprint and 60-minute stability.

The Oracle A1 2 OCPU / 12 GB profile must not claim Muse Glimmer compatibility unless an actual quantized build fits and passes the same quality/latency gates.
