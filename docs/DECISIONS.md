# Architecture decisions

## ADR-0001 — Thin Python control plane
- Date: 2026-10-04
- Status: **accepted**
- Decision: one small Python control plane owns sessions, memory, jobs, routing and cancellation. Frameworks may be workers/adapters, not the product shell.
- Reason: strongest convergence across independent implementations and lowest operational surface on 2 OCPU / 12 GB.
- Rollback: interfaces permit replacing the core without changing durable Git/SQLite state formats.

## ADR-0002 — SQLite WAL + FTS5 operational state
- Date: 2026-10-04
- Status: **accepted**
- Decision: SQLite WAL + FTS5 is the initial state/memory engine; runtime DB lives outside the Git checkout. Markdown/Git stores curated durable truth.
- Guardrails: bounded reads, short transactions, indexes, source/confidence on promoted memory.
- Revisit: add vector retrieval only if benchmarked recall requires it.

## ADR-0003 — Direct provider router
- Date: 2026-10-04
- Status: **accepted**
- Decision: route directly to configured OpenAI-compatible providers; no always-on LiteLLM/router service.
- Required behavior: quota awareness, circuit breaker, TTFT watchdog, metrics, cancellation, failover only before first token.
- Cost policy: no automatic paid fallback.

## ADR-0004 — Direct WSS is voice transport v1
- Date: 2026-10-04
- Status: **accepted for first implementation**
- Decision: browser ↔ Oracle direct WSS for one-user realtime audio/control.
- Challengers: Pipecat SmallWebRTC first, StreamCore second.
- Gate: switch only if A1/mobile benchmarks materially beat WSS in latency/stability.

## ADR-0005 — Speech stack remains benchmark-gated
- Date: 2026-10-04
- Status: **proposed**
- Decision under test: Silero VAD; adaptive endpointing; Moonshine local STT with Groq Whisper quota lane and whisper.cpp fallback; Pocket TTS candidate with Piper fallback; Kokoro/MOSS challengers.
- Argentine voice: independent acceptance test; generic Spanish support is insufficient.

## ADR-0006 — Coding is an isolated worker
- Date: 2026-10-04
- Status: **accepted**
- Decision: coding runs as a durable GitHub Actions worker, not inside the internet-facing core. The current bounded harness is Aider, started from an explicit validated ref on an isolated agent branch.
- Modes:
  - `implement`: bounded implementation with deterministic verification;
  - `repair`: diagnose-first minimal repair with deterministic verification;
  - `review`: adversarial senior review constrained to `AGENT_REVIEW.md`; product mutations fail the run.
- Security:
  - agent execution has `contents: read` and checkout credentials are not persisted;
  - model/NIM credentials exist only in agent-edit steps and are absent from verification/publish steps;
  - publication, when requested, happens in a separate write-capable job from a verified patch artifact;
  - no auto-merge and no unrestricted model-authored shell in the Gateway.
- Replaceability: Aider/DeepSeek are implementation choices, not product identity; other coding harnesses can challenge behind the same durable job contract.

## ADR-0007 — Cloudflare deploy-only
- Date: 2026-10-04
- Status: **accepted**
- Decision: Cloudflare may host/deploy user applications and a thin frontend if desired, but normal 0liviA chat, memory, model and voice turns do not depend on Workers, Tunnel, DO, Containers or AI Gateway.


## ADR-0008 — Provider catalog + pre-output failover contract
- Date: 2026-10-04
- Status: **accepted**
- Decision: model/provider selection is a catalog with ordered priorities, health state and explicit cost mode. Provider identity never becomes product identity.
- Required behavior:
  - prefer the strongest eligible route;
  - retry/fail over only before the first validated visible segment;
  - circuit-break unhealthy routes;
  - respect provider quota/rate windows;
  - never restart a turn after visible output from another provider;
  - never cross from a verified-free route into paid/unverified capacity silently.
- Current bridge preference: DeepSeek V4.1 Flash (NVIDIA NIM, development/evaluation only under current Developer Program terms) → GPT-OSS-120B → GLM-4.7-Flash.
- Production gate: any provider whose free entitlement is not valid for production or whose account can auto-bill remains deployment-gated.
- Rollback: remove/reorder a catalog entry without changing session, memory or UI contracts.


## ADR-0009 — Research and voice challengers stay adapter-gated
- Date: 2026-10-04
- Status: **accepted**
- Web research:
  - direct `/read` uses the canonical server-side SSRF-safe reader and injects page text only as ephemeral untrusted context;
  - `/search` is a replaceable adapter contract and is disabled unless a route is explicitly configured and verified zero-cost;
  - `/research` composes one bounded search with safe reads of up to three result URLs; all result/page content remains ephemeral untrusted context;
  - Cloudflare Web Search API is an eligible adapter, not a default dependency. Its provider search calls are billable unless the owner supplies a separately verified zero-cost BYOK route, so the core must never consume AI Gateway credits implicitly.
- Live voice:
  - LiveKit Agents is a benchmark challenger for WebRTC transport, turn detection, handoffs and voice-agent orchestration;
  - it is not the canonical voice runtime until target-host benchmarks prove it beats direct WSS/Pipecat on latency, es-AR quality, stability and recurring cost;
  - adopting LiveKit must not move durable state or model/provider policy out of the 0liviA Core.
- Rollback: either adapter can be removed without changing sessions, memory, projects or provider routing.


## ADR-0010 — Native ChatGPT plan usage, not OpenClaw as a dependency
- Date: 2026-10-05
- Status: **accepted / live-connection gated**
- Decision: support OpenAI's official Sign in with ChatGPT plan-usage flow directly behind the existing provider router instead of embedding OpenClaw or another full assistant framework.
- Transport: OAuth bearer → official Responses API with streaming and `store:false`; credentials remain server-side.
- Quality: the account's available model catalog determines eligible models; `gpt-6-astra` is the preferred configured slug only when actually available to the connected account.
- Cost: `cost_mode=plan_included`; under hard-zero-cost policy the route is rejected unless the owner has explicitly verified that app credit overage cannot occur.
- Failure behavior: plan/app limit exhaustion behaves like a quota/rate failure; pre-output failover may continue to another eligible route, otherwise the turn fails/degrades.
- Security: no API key, refresh token or OAuth access token appears in the browser, chat, Library, Memory or Git.
- Reason: uses a documented OpenAI path, preserves provider replaceability, avoids reverse-engineered consumer APIs, and removes an unnecessary full-framework dependency.
- Rollback: delete the catalog entry/provider adapter without changing sessions, memory, UI or other routes.
