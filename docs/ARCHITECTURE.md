# 0liviA architecture — synthesis v1

Status: **accepted core / provisional voice components**  
Target: one user, Oracle A1 ARM64 (2 OCPU / 12 GB), recurring infrastructure target USD 0.

## Final shape

`Browser / mobile PWA`
→ direct HTTPS/WSS to Oracle
→ **0liviA Core (Python, one small control plane)**
→ SQLite WAL + FTS5 for operational state
→ curated Markdown/Git for durable human-readable truth
→ direct OpenAI-compatible provider router
→ on-demand workers for coding, browser research and voice.

Cloudflare is not in the chat, model, memory or voice hot path. It remains available for deploying user applications only.

## Core

The core owns identity, sessions, memory, jobs, checkpoints, events, routing and cancellation. It does **not** become a monolithic agent framework.

Persistent operational state:
- SQLite WAL, outside the Git checkout;
- bounded message reads, short transactions and indexed session access;
- FTS5 for lexical recall;
- typed/promoted durable memory with source and confidence;
- jobs/checkpoints that survive restart.

Durable truth:
- GitHub repository for code, architecture, instructions and ADRs;
- Markdown for curated memory, runbooks and project state;
- derived indexes remain rebuildable.

No vector database is required for v1. Add sqlite-vec or embeddings only if a recall benchmark proves FTS5 insufficient.

## Model routing

No provider is “the brain”. 0liviA is the brain; providers are replaceable inference engines.

Router requirements:
- OpenAI-compatible adapters where possible;
- provider registry is configuration, not code;
- daily quota accounting;
- circuit breaker with exponential cooldown;
- first-token watchdog;
- cancellation propagation;
- failover **only before the first token**;
- after the first token, a provider failure returns an explicit partial/error instead of duplicating text through a second model;
- route/model/latency/error telemetry without chain-of-thought or secrets.

A free quota disappearing must cause degradation, rerouting or pause — never hidden spend.

## Coding and repository work

Coding is a worker, not the control plane.

Default design:
- OpenCode-compatible worker launched on demand;
- one isolated Git worktree per job;
- scoped GitHub credentials;
- official GitHub MCP for repository operations;
- checkpoints before/after meaningful mutations;
- tests and verification before push/PR;
- no arbitrary model-written shell in the internet-facing gateway.

A bounded container / bwrap / equivalent sandbox is a deployment gate before autonomous code execution is enabled.

## Research/browser

Playwright is the default browser worker and starts on demand. Research results are untrusted input and must not become instructions merely because a page says so.

## Voice transport

**v1 default: direct WSS Browser ↔ Oracle.**

Reason: one user, one public server, no SFU requirement, minimal moving parts, easiest cancellation/debugging, and strong evidence from the council implementation.

WSS carries control events plus audio frames. Each turn has a turn_id. Barge-in immediately:
1. stops client playback;
2. sends cancel(turn_id);
3. cancels STT/LLM/TTS tasks;
4. drops late audio for that turn.

### Transport escape hatch

Keep transport behind an adapter:
- **Pipecat SmallWebRTC** is the first challenger if TCP head-of-line, mobile jitter or reconnection metrics fail.
- **StreamCore** is the second challenger if its Go media plane materially wins CPU/latency/stability.
- LiveKit is not the initial choice for a single-user 2-OCPU host.

No transport switch may require rewriting session/memory/router logic.

## Voice intelligence

These choices are **benchmark-gated**, not claims:

VAD:
- Silero ONNX baseline.

End of turn:
- adaptive silence policy first;
- SmartTurn is experimental because published Spanish false-cutoff behavior is not good enough to trust blindly;
- accept it only if owner-specific Spanish tests beat the adaptive baseline.

STT:
1. Moonshine local streaming is the preferred unlimited/zero-marginal-cost candidate.
2. Groq Whisper may be a fast quota-limited lane or fallback.
3. whisper.cpp is the local compatibility fallback.

TTS:
1. Pocket TTS is the preferred natural streaming candidate **if** it passes A1 ARM64 Spanish/latency/resource gates.
2. Piper maintained successor is the conservative low-latency fallback.
3. Kokoro/MOSS are quality challengers, not always-on dependencies.

Argentine/Rioplatense voice is a separate acceptance gate: pronunciation, vos cadence, yeísmo and warmth must be A/B tested with an es-AR reference/voice where licensing allows. “Spanish support” alone is not enough.

## Acceptance targets

Text:
- bounded context growth;
- provider failover before first token;
- restart/resume without lost session/job state;
- no secrets in DB logs or Git;
- coding worker isolated from gateway credentials.

Voice target:
- mic-ready <300 ms;
- partial transcript <500 ms p50;
- end-of-turn <500 ms p50 without unacceptable false cuts;
- LLM TTFT <800 ms p50 on the selected free lane;
- first audio target <1.5 s end-to-end;
- perceived barge-in silence <150 ms client-side and <300 ms pipeline cancellation;
- 60-minute session without meaningful RSS growth/drift.

These are gates to measure on the actual Oracle A1, not current PASS claims.

## Explicit exclusions for v1

- Next.js + Postgres as the always-on core;
- vector DB;
- nanobot/Agent Zero/Letta as the product shell;
- LiveKit as the default voice path;
- GhostCall as a dependency (no verified programmable bot API);
- reverse-engineered consumer-session APIs;
- mandatory paid inference;
- Cloudflare in normal 0liviA turns.
