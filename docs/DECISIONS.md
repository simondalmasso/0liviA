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

## ADR-0007 — Cloudflare is not the canonical Core
- Date: 2026-10-04
- Status: **accepted; clarified 2026-10-07**
- Decision: Cloudflare may host/deploy the thin public frontend, but normal authenticated 0liviA chat, durable memory, projects, research/tools and voice do not depend on Workers, Tunnel, DO, Containers or AI Gateway.
- Narrow exception: the public shell may expose an explicitly non-canonical, no-account demo chat through Workers AI when account-level zero-cost behavior is independently verified. The demo must be stateless server-side, globally hard-capped, reject slash/tool commands, report separate demo readiness, and leave canonical `/api/chat` fail-closed.


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


## ADR-0011 — Bounded public intelligence, optional Qwen demo, compact responsive shell
- Date: 2026-10-09
- Status: **implementation proposed / production gated**
- `/intel` is an authenticated, on-demand, deterministic Core command; it only reads fixed public USGS and NASA EONET HTTPS JSON feeds (no redirect, arbitrary URL, background poll, agent permission or additional inference spend).
- Every item is tied to an official source; failure is an explicit data gap and a short stale fallback is labeled. Public data is not independently authenticated.
- Do not transplant the whole `world-intel-mcp` Python/MCP runtime, Qdrant, collector daemon or military feeds into the Core without separate review.
- Cloudflare public demo remains an isolated Worker, not the durable Core. Its Qwen model is opt-in with a **separate** account-level verified no-overage gate and the same Durable Object daily allowance; unapproved requests fail before consuming quota.
- Browser UI keeps its strict lightweight asset budget; drawer is invisible when closed, compact rail is used on medium screens, and actual inference model identifiers are exposed to users.
- Rollback: omit Qwen gate, remove the optional `/intel` command, or revert the UI stylesheet without schema migrations.


## ADR-0012 — Public security headers without always-on Worker invocations
- Date: 2026-10-09
- Status: **implemented in source / live production verification pending**
- Workers static assets are normally served without executing the Worker. Applying response headers only in `cloudflare/worker.mjs` would leave the homepage unprotected. Use `web/_headers` for assets, and the Worker `hardened(response)` wrapper for API and health routes, preserving the static assets free-tier optimization.
- CSP forbids framing, objects, external origins and insecure requests; it temporarily permits inline JavaScript and CSS because the current <96 KB product shell embeds them. A future dedicated CSP-hash or external-asset change is required to remove `unsafe-inline` without breaking the UI.
- An exact immutable `OLIVIA_RELEASE_SHA` injected by the deployment workflow is returned by public `/healthz`; the release smoke gate compares this with the checked-out canonical SHA. This stamp has no credentials or private runtime metadata.
- Production header and desktop/mobile behavior must be checked after the canonical deployment. No Qwen billing approval is implied.
- Sources: [Cloudflare Workers Static Asset Headers](https://developers.cloudflare.com/workers/static-assets/headers/) and [Routing / run_worker_first](https://developers.cloudflare.com/workers/static-assets/binding/).


## ADR-0013 — Correct Qwen3.8 model; NVIDIA NIM trial cannot power the public site
- Date: 2026-10-09.
- Cloudflare's requested model is **`@cf/qwen/qwen3.8-27b`**, not the earlier Qwen3 30B alias. The public demo uses the accurate model ID and identity label. The model has a separate `OLIVIA_DEMO_QWEN_ZERO_COST_CONFIRMED=1` fail-closed release gate because an account-level no-billing policy cannot be inferred from a model card. Worker Free includes 10,000 neurons/day and fails on exhaustion, subject to the account remaining genuinely on Workers Free and not Unified Billing. To limit its budget, Qwen output is capped at 512 tokens and `reasoning_effort=low`. Both models share the global 25-request daily Durable Object allowance.
- NVIDIA Build NIM `deepseek-ai/deepseek-v4.1-flash` has the documented OpenAI-compatible `https://integrate.api.nvidia.com/v1/chat/completions` endpoint and accepts an `NVIDIA_API_KEY`. A GitHub Actions secret being present does **not** prove model entitlement, remaining trial credits, no-overage, or legal production rights. NVIDIA's public API Trial Terms (sections 1.2/1.4) limit API Catalog trial service to internal testing/evaluation and prohibit production without a separate subscription.
- Therefore NVIDIA may only be tested through the manual `nvidia-nim-eval.yml` workflow with explicit acknowledgement and a separate `NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED=1` gate; one canned non-personal prompt, 64 output tokens, no retries, no logging secrets/output, no public proxy, no keys in the Worker. No permanent production adapter until both contractual permission and zero-charge billing boundary are proven.
- References: [Cloudflare Qwen3.8 27B](https://developers.cloudflare.com/workers-ai/models/qwen3.8-27b/), [Cloudflare Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), [NVIDIA DeepSeek V4.1 Flash API](https://docs.api.nvidia.com/nim/reference/nvidia-deepseek-v4_1-flash-infer), [NVIDIA trial terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf).


## ADR-0014 — Muse Glimmer is open-weight; no "Lite" or trial-to-production shortcut
- Date: 2026-10-09
- Status: **evaluation path implemented / production prohibited without entitlement**
- Meta publishes Muse Glimmer 30B weights under Apache 2.0; official Q4 GGUF ~16.8 GB; DFlash drafter ~1.6 GB is **not** standalone. Community lower-bit quants exist, but quality and security are not certified.
- The operator may download official weights for a suitable GPU host; no heavyweight downloads inside GitHub Actions or Cloudflare, no model loading on OCI Micro and no dependence on the owner's PC during normal operation.
- NVIDIA hosts `meta/muse-glimmer-30b` for prototype use. Extend only the **existing manual NIM evaluation** allowlist to support Muse, requiring a separate cost verification, explicit trial consent and a single synthetic/harmless request. Provider credentials are never available to the public shell.
- NVIDIA API Trial Terms §§1.2 and 1.4 explicitly disallow production. Never route live user chats through NVIDIA trial or claim $0 simply because the model is offered under a "Free Endpoint" banner.
- Existing canonical `OpenAICompatibleProvider` remains sufficient to connect a future compliant production endpoint; new router forks are unnecessary.
- Detailed evidence, legal downloads and footprint boundaries: `docs/MUSE_GLIMMER.md`.


## ADR-0015 — Atomic, opt-in job leases; portable sandbox infrastructure only when cost-certified
- Date: 2026-10-09
- Status: **SQLite primitive implemented; coding/browser call-site migration and OpenShell runtime gated**
- [CopilotKit/OpenMuse](https://github.com/CopilotKit/OpenMuse) informs the CAS-lease design, but its CopilotKit Intelligence service, external thread persistence, Node 24/pnpm stack and optional browser/computer services are **not** imported. `Store` adds lease-aware atomic claim, checkpoint, renew and finish operations for future workers.
- Unlike blind replay, expired in-progress leases **must not be automatically reclaimed** after an uncertain side effect. Owners reconcile the external run receipt first. Historical unleased jobs retain their behavior; leased tokens are never exposed through `get_job`.
- [NVIDIA/OpenShell](https://github.com/NVIDIA/OpenShell) is the preferred future *optional* policy-enforcing sandbox challenger for code/browser workers. The current OCI micro's privileged access, RAM and kernel/runtime requirements remain unverified, so neither its gateway nor Docker is deployed now. A stable pinned runtime and fail-closed capability proof are prerequisites.
- InternAI A100 dev machines can be evaluated for short-lived, synthetic Muse Glimmer benchmarks when credit points are confirmed; DigitalOcean MicroVMs charge for compute/storage/egress, Dame is paid, MillionSend depends on email infrastructure, and neither DEV-OS nor getvmio supplies useful $0 compute.
- Detailed source evidence, pricing and integration sequence: `docs/OSS_COMPUTE_INTEGRATION_2026-10-09.md`.


## ADR-0016 — OpenShell readiness + OpenMuse leases in real dispatch; evidence over agent self-claims
- Date: 2026-10-09
- Status: **code integrated on branch; release gated by tests**
- OpenMuse: `Store` lease primitives from ADR-0015 now govern actual coding/browser Actions dispatch, via atomic claim, own-token checkpoint, conditional acknowledged handoff and terminal failure receipt. Expired/uncertain remote dispatch is not automatically retried. Successful status requires an attributable external `remote_run_id`.
- OpenShell: optional, **non-mutating** host readiness inspection and narrow GitHub read-only REST policy added. Running OpenShell on any machine remains blocked pending verified machine resources, signed/pinned release, credential broker, kernel enforcement, sandbox negative tests, account billing no-overage and owner authorization. Neither CI nor the public site can automatically start it.
- MiniAGI: legacy 2023 agent with unrestricted shell and Python execution; its real advantage is a separate critic perspective but extra LLM calls could consume allowances and merely claim task success. Adopt zero-cost deterministic outcome verification based on trusted GitHub receipt, **not** its runner or prompting.
- InternAI: 7-day runtime is a **per-session** cap, not a quota refill. Restart on existing stopped machine is supported manually, preserving only `/data` and consuming available points. Do not automate repeated sessions until an official authorized management API is confirmed and a non-billable quota guard is in place.
- Pocket coder candidates Qwen2.5-Coder-0.5B, Qwen3.5-0.8B, Liquid LFM2.5-1.2B are **benchmarks only**; do not present a 398MB GGUF as a hosted model or presume fit in 1GB without actual peak RSS.
- Source references and acceptance: `docs/POCKET_CODER_AND_AGENT_GATES_2026-10-09.md`.
