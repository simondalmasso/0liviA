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
3. LiveKit Agents/WebRTC;
4. StreamCore.

LiveKit is a challenger only: benchmark its media reliability, reconnect/turn handling and resource footprint without making LiveKit Cloud or any paid service a runtime requirement.

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

## Browser worker smoke

Status: **PASS** for the bounded read-only JavaScript renderer and artifact retrieval. This is not approval for authenticated or write automation.

Verified 2026-10-05 on a standard public-repository GitHub-hosted `ubuntu-latest` runner.

Durable evidence:
- workflow: `0liviA Browser Smoke Once`;
- run: `37257844129`;
- source SHA: `1a2ec658f3142795e53bf522399b5d56bc98ece9`;
- target: `https://example.com/`;
- runtime: Python 3.12 + Playwright 1.55.0 + Google Chrome 154.0.8037.57;
- result: HTTP 200, title `Example Domain`, request_count=2, extracted text <= 30k chars, one public link;
- artifact: `browser-smoke-result`, artifact ID `11323124125`;
- artifact digest: `sha256:677f7d9a0bc00e4cf71565863cd6b6f96853f50e04bb89a977118acd7554779a`;
- downloaded archive contained `browser-result.json` and a valid rendered screenshot.

This closes the controlled public-page JS-rendering/artifact-retrieval gate only. It does not certify login flows, click/write actions, arbitrary-site compatibility or production browser credentials.


## Mobile UI smoke

Status: **PASS** for the current mobile shell, protected first-run registration and fullscreen Voice at both required narrow viewports.

Final durable evidence:
- workflow: `0liviA Mobile UI Smoke Once`;
- run: `37261271848`;
- functional product SHA under test: `85596ea143e3561cc99f3b7cebfba547cd73539e` (the workflow head `76839bcd...` differs only by its trigger file);
- runtime: Python 3.12 + Playwright 1.55.0 + Chromium;
- viewports: `360x800` and `430x900`, mobile/touch context;
- artifact: `olivia-mobile-ui-smoke`, artifact ID `11324552562`;
- artifact digest: `sha256:ce6ad8d63b27fa51788cd61daae2fbecc382e16b9488a0c7538395c4afdfba8a`;
- artifact contains six screenshots plus `report.json`: Session, Voice and protected `Registrate` at both viewports.

Verified geometry:
- document/body width exactly matches the viewport: no horizontal overflow;
- rail is 48 px wide at both target sizes;
- composer remains fully inside the viewport and flush to the bottom;
- Session drawer stays fully inside the viewport;
- Live Voice is exactly fullscreen at both sizes;
- protected first-run `Registrate` card, email/password fields and CTA remain fully inside the viewport;
- setup token is consumed from the URL fragment and the visible hash is cleared;
- zero browser `pageerror` events in both normal and auth pages.

This certifies the current 360–430 px layout and auth/Voice geometry. It does not replace real-device keyboard, safe-area/notch or mobile-network soak testing on the eventual production host.

Latest Live Voice client regression evidence:
- source SHA: `c5dde9c00926f857056c2083f96889b9ae717dea`;
- core CI: PASS;
- mobile UI smoke run: `37273932907` PASS;
- artifact: `olivia-mobile-ui-smoke`, ID `11328992551`;
- this run includes the canonical direct-WSS UI client while preserving the same 360×800 / 430×900 layout gates.
