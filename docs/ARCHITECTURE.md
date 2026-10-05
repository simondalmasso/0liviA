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

Cloudflare is not part of the canonical chat, memory or voice hot path. It may host a thin frontend or a temporary compatibility bridge, but such a bridge must remain deployment-gated and must not become durable product state.

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

A free quota or included-plan allowance disappearing must cause degradation, rerouting or pause — never hidden spend.

### ChatGPT plan lane

For eligible Plus/Pro owners, the router supports the official **Sign in with ChatGPT** plan-usage path as a first-class provider:
- `kind=chatgpt_plan`;
- official `https://api.openai.com/v1/responses` transport only;
- `store:false` and streaming Responses;
- OAuth access/refresh credentials live in a server-side profile file mode 0600;
- no OpenAI API key is accepted or exposed in the browser;
- system/developer policy is sent through `instructions`, not as unsupported system input items;
- the provider is eligible under hard-zero-cost policy only when `no_credit_overage_verified=true`.

That flag is an owner/account assertion, not a billing API proof. It must only be set after the owner verifies ChatGPT app credit use cannot create overage—for example by leaving app credit use disabled and/or setting this app's usage limit below 100%. If the plan/app limit is exhausted, the route fails and the normal provider failover policy applies before visible output.

## Coding and repository work

Coding is a worker, not the control plane.

Current implemented design:
- coding is dispatched as a durable job from the Python core;
- GitHub Actions executes the burst worker away from the internet-facing gateway;
- each run starts from an explicit validated ref and works on an isolated agent branch;
- Aider is the current bounded coding harness, with DeepSeek V4.1 Flash available only in development/evaluation when the required NIM entitlement/key is present;
- `implement` and `repair` allow at most two bounded agent passes and finish with deterministic compile/test/JS/Worker checks;
- `review` is mutation-constrained: it may only produce `AGENT_REVIEW.md`; touching product code/config/tests/workflows fails the job;
- the agent-execution job has read-only repository permission and does not persist checkout credentials;
- an optional second job receives only a verified patch artifact and is the only job with repository write permission;
- publication is optional and never merges automatically;
- gateway credentials never grant arbitrary shell execution.

The harness is replaceable. OpenCode/other coding agents remain challengers, not permanent dependencies.

## Temporary production bridge

`cloudflare/worker.mjs` exists as a transitional public bridge because Oracle A1 capacity has not yet been proven available for production. The bridge runtime is **disabled by default** and intentionally duplicates only a narrow subset of the canonical core:

- stateless message history supplied by the browser;
- provider catalog/failover before visible output;
- read-only URL ingestion with SSRF/redirect/body limits;
- a local request guard.

It is **not** the source of truth for Projects, Library, Memory or jobs. Its current account-level zero-cost status is unverified and it has no canonical owner-account store, so chat/read routes remain disabled until both identity and zero-cost/account guards are explicitly proven. This bridge may be removed without changing the canonical Python state formats.

When the canonical Python Core is active, Projects, Chats, Library and Memory are server-side SQLite state and the browser reconciles them through authenticated workspace/session APIs. IndexedDB remains only a disposable cache and one-shot migration layer. In temporary bridge mode, workspace state remains local-only and must not be presented as durable multi-device state.

## Owner identity

The canonical Core is a single-owner installation:
- first access exposes **Registrate** only when no owner exists;
- registration stores one normalized owner email plus a scrypt password verifier in SQLite;
- subsequent registration attempts fail closed;
- login issues Secure/HttpOnly/SameSite cookies;
- **Recordarme** binds a persistent cookie to a random server-side trusted-device ID;
- remembered devices are listed/revocable from the Session surface;
- session-only logins create no durable trusted-device row;
- no OAuth, third-party identity provider, browser fingerprinting or API-key input is required in the UI.

Existing deployments may seed a legacy owner from environment variables once; new bootstrap flow uses first-run registration.

## Voice transport gate

The canonical Gateway registers authenticated `GET /api/voice/ws?session_id=...` using the direct-WSS wire format. The route:
- requires the same owner auth boundary as chat;
- validates that the target chat session exists;
- remains unavailable with HTTP 503 unless a server-side `VoicePipeline` factory is explicitly configured;
- uses bounded binary frames and the existing sequencing/cancel/barge-in pipeline.

The browser/mobile shell now implements that same wire contract:
- it opens same-origin WSS only when `/healthz` reports `voice_backend_configured=true`;
- microphone audio is resampled to 16 kHz PCM16 and framed with `turn_id`/sequence metadata;
- server STT/LLM/TTS events drive the existing cyan fullscreen voice surface;
- server PCM is streamed back through Web Audio;
- microphone frames remain active during playback so server-side VAD can perform spoken barge-in;
- completed turns rehydrate the same durable chat session;
- browser SpeechRecognition/SpeechSynthesis remains only a provisional fallback while the server speech backend is gated.

Production VAD/STT/TTS promotion still requires target-host es-AR quality, latency and 60-minute stability evidence.

## Research/browser

Implemented in the canonical core:
- `/read` uses an SSRF-safe server-side URL reader with DNS/IP revalidation, redirect bounds, MIME/body limits and no browser credentials;
- fetched page content is injected only as ephemeral **untrusted** model context and is not persisted to SQLite;
- `/search` is a replaceable adapter contract, disabled by default and fail-closed unless the exact provider route is explicitly configured and verified zero-cost;
- `/research` composes bounded search + safe reads while keeping external content ephemeral;
- `/browse` dispatches a JavaScript-capable Playwright job to an isolated private GitHub Actions repository. The private boundary is mandatory because the bounded result includes page text and an optional screenshot artifact. The runner accepts only public HTTP(S), enforces GET/HEAD-only requests, blocks reserved/private network egress, disables downloads/service workers, bounds requests/text/artifacts, and the Core preflights repository privacy before dispatch.

The Core never embeds a privileged browser. Browser result text is shown from the job result and is not persisted into chat/model context automatically.

Still gated:
- authenticated browsing;
- owner-approved click/write automation;
- autonomous multi-page agents;
- production smoke of the isolated browser workflow.

Research/browser content remains **data**, never instructions merely because a page says so.

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


## Stability and locale invariants

0liviA is designed to degrade instead of stall:
- one active turn per session;
- bounded context reads and explicit backpressure;
- provider TTFT watchdog + circuit breaker;
- failover only before first validated output;
- turn IDs and sequence numbers for reconnect/resume;
- partial output is checkpointed instead of silently discarded;
- process supervision restarts failed services, while SQLite/Git preserve state.

Language is a kernel policy, not a model preference:
- default locale is **es-AR**;
- the first short output segment is buffered and language-checked locally before it is displayed or sent to TTS;
- unexpected language drift causes cancellation/retry, not German/English text leaking into the session;
- a user request for another language overrides the guard for that turn.

The owner's PC is not part of the compute plane. The browser captures microphone/input and renders output only; it does not grant 0liviA local filesystem, shell or background-agent access. Browser persistence, where present in the temporary bridge UI, is disposable cache and never durable truth.
