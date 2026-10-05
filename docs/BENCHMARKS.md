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

Status: **PASS** for the current shell at the two required narrow viewports.

Durable evidence:
- workflow: `0liviA Mobile UI Smoke Once`;
- run: `37258626574`;
- source SHA: `afcdce10193e77cb91333fc314d9c27dcc431d8b`;
- runtime: Python 3.12 + Playwright 1.55.0 + Google Chrome 154.0.8037.57;
- viewports: `360x800` and `430x900`, mobile/touch context;
- assertions: no horizontal document/body overflow, rail width within 44–54 px, composer flush to viewport bottom, Session rail button opens drawer, final drawer bounds remain within viewport;
- artifact: `mobile-ui-smoke`, artifact ID `11323133397`;
- artifact digest: `sha256:35a0b1deb570cb73c8125aa323935b0e2536ac24cc284a8838dd2caae2cf7290`;
- artifact contains `mobile-ui-smoke.json` plus screenshots for both viewports.

The first smoke exposed a real closed-drawer pointer interception bug; the UI was fixed with closed/open pointer-event isolation. A second smoke exposed only a test timing issue during the 220 ms drawer transition; the final stable-position smoke above passed.
