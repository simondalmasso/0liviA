# Implementation plan — productization checkpoint

Branch: `arch/gpt-synthesis-v1`

This file is the current execution checkpoint. Architecture choices live in `docs/DECISIONS.md`; historical council prompts live under `docs/history/`.

## What is already integrated

- Python control plane with sessions, projects, library, memory, jobs, checkpoints and events.
- Persistent provider-health state with quota admission, circuit breaker, half-open recovery, cancellation and redacted telemetry.
- One-time Sign in with ChatGPT OAuth onboarding helper is implemented with PKCE/state/nonce, OIDC/JWKS validation, protected 0600 profiles, model discovery and transactional/reversible VM activation.
- Failover only before validated visible output; partial answers are preserved rather than silently replayed through another provider.
- Browser/API gateway with first-run single-owner registration, email/password login, remembered-device revocation, login throttling, bounded bodies and one active turn per session.
- Authenticated server-side workspace API backed by SQLite; Projects/Chats/Library/Memory sync into browser cache when the canonical core is active.
- Current browser product shell with Chats/Projects/Library/Memory/Config/Session rail navigation, first-run auth UI, remembered-device management, fullscreen Live Voice, 360–430 px responsive hardening, contextual slash commands and compact in-chat durable job state.
- Canonical SSRF-safe `/read` tool with page content kept ephemeral and explicitly untrusted.
- Replaceable `/search` adapter contract, disabled unless an exact route is configured and zero-cost verified.
- Capability-aware provider catalog (`chat/research/vision/code/review`) with backwards-compatible chat defaults; research tools prefer a research-capable route and safely fall back to chat when none is configured.
- Isolated GitHub Actions coding worker with durable job IDs, exact base refs, `implement/repair/review` modes and deterministic post-agent verification.
- Isolated JS browser burst worker with `/browse`, JavaScript rendering, read-only GET/HEAD enforcement, public-network egress guards, bounded artifacts, and no external-page persistence into model/chat context.
- Review mode may only create/update `AGENT_REVIEW.md`; any product mutation fails the job.
- Authenticated `/api/voice/ws` direct-WSS endpoint plus voice contracts/pipeline/sequence/cancel tests and benchmark recorder. The endpoint fails 503 until an approved speech backend factory is configured.
- Production bootstrap source/artifact pinning, first-run registration bootstrap and Caddy hardening.
- Repository hygiene tests preventing stale build claims and active-doc duplication.

## Productization gates

### 1. Canonical cloud runtime
Target remains Oracle A1 ARM64 (2 OCPU / 12 GB). Do not claim production runtime until an actual host is available and passes install, restart, backup and latency/resource smoke tests.

### 2. Workspace durability
The canonical Python Core is now the durable source of truth for Projects/Chats/Library/Memory. IndexedDB is a disposable cache/migration layer when canonical mode is available. The temporary Cloudflare bridge remains non-durable by design and must not be presented as multi-device persistence.

### 3. Stable zero-cost model routing
Provider routing must remain catalog-driven and fail closed:
- never move to a paid/unverified route silently;
- official ChatGPT-plan usage is the preferred frontier-quality lane for eligible Plus/Pro owners once OAuth onboarding exists and no-credit-overage is explicitly verified; exhaustion must fail/degrade rather than use credits silently;
- DeepSeek V4.1 Flash/NVIDIA NIM remains development/evaluation-only unless explicit production entitlement exists;
- the transitional Cloudflare bridge is disabled by default; Workers AI/read routes remain unavailable until both identity and account-wide zero-cost behavior are independently verified;
- local inference is allowed as a zero-cost fallback but is not the quality target for normal chat;
- Intern Discovery / Intern InkStone is a promising GPU burst lane for Muse Glimmer, but remains `free_unverified` until its account-level point exhaustion/no-overage behavior and a real service response contract are proven.

### 4. Research/browser
Implemented:
- `/read`: SSRF-safe public URL reader, redirect/IP/body bounded, injected only as ephemeral untrusted context.
- `/search`: replaceable search contract, disabled by default, refuses routes without explicit zero-cost verification.
- `/research`: bounded search+read orchestration (max 3 results) using the same fail-closed search gate and SSRF-safe reader; external content remains ephemeral.

Still gated:
- authenticated browsing;
- owner-approved write/click automation;
- owner-approved write/click automation remains a separate future capability.

Implemented in branch:
- `/browse`: opt-in GitHub Actions burst worker using a standard public-repo runner, pinned Playwright, JavaScript rendering, reserved/private-network egress blocks, no third-party browser secrets, bounded requests/text/artifacts, and external page content kept out of durable chat/model context until explicitly requested.

### 5. Live Voice
The UI, authenticated direct-WSS Gateway route and Python pipeline now exist; production speech engines do not. The route is capability-gated and returns 503 until a backend is configured. Benchmark direct WSS + candidate VAD/STT/TTS on the actual target host for es-AR quality, TTFT/TTFA, barge-in and 60-minute stability before promotion. LiveKit Agents and Pipecat remain challengers, not defaults.

### 6. Coding worker
The GitHub Actions worker is implemented and opt-in:
- secrets server-side only;
- no auto-merge;
- exact base ref;
- execution job has read-only repo permission;
- publication happens in a separate write-capable job only after deterministic verification;
- maximum two passes for implement/repair;
- review is read-only with respect to product paths and may only write `AGENT_REVIEW.md`;
- provider entitlement/cost must be verified before enabling a model route.

### 7. Security baseline
Implemented and CI-gated:
- first-owner setup token + single-owner registration;
- scrypt password verifiers;
- expiring Secure/HttpOnly/SameSite cookies and remembered-device revocation;
- login throttling with proxy-spoof resistance;
- closed cross-origin API boundary and security headers;
- no public password-reset/email-enumeration endpoint;
- server-side authorization on private resources;
- parameterized Store SQL;
- redaction at durable persistence/log boundaries;
- current-tree and full-history high-confidence secret scans;
- coding agent least privilege;
- encrypted online SQLite backup + integrity-checked restore proven in CI;
- bounded sanitized security-event retention and owner-only Session visibility;
- Dependabot for Python/GitHub Actions, with official Actions moved off deprecated Node 20 majors.

External gates still required before a production-security claim:
- MFA/2FA verified on GitHub/Oracle/any retained Cloudflare/provider account;
- provider-side rotation for any real credential exposure alert;
- disposable-host restore rehearsal;
- exact production smoke.

## Repository discipline

- Work on `arch/gpt-synthesis-v1`; do not overwrite `main` user changes.
- Historical council material is evidence, not active instruction.
- Keep `README.md`, `AGENTS.md`, this checkpoint and `docs/ARCHITECTURE.md` consistent with live code.
- Prefer deletion/archival of superseded scaffolding over parallel implementations.
- Add a dependency only when it replaces more complexity than it introduces.
- Do not deploy until CI is green and the relevant zero-cost/account entitlement gate is proven.

## Verification contract

Every meaningful mutation must preserve:
- `python -m compileall -q olivia tests`
- `bash -n deploy/*.sh`
- browser inline JS syntax check
- `node --check cloudflare/worker.mjs`
- `pytest -q`
- GitHub Actions matrix on Python 3.11 + 3.12

## Exact next engineering gates

1. Keep the branch green and do not regress the security baseline.
2. Browser worker smoke is complete (GitHub Actions run `37257844129`): controlled public page rendered with Chrome, bounded JSON + screenshot artifact uploaded and downloaded successfully. Keep `/browse` read-only; owner-approved click/write automation is a separate future capability and must never embed a privileged browser inside the Core.
3. Run target-host voice benchmarks and compare Direct WSS, Pipecat and LiveKit challenger paths.
4. Provision/verify an Oracle A1 host when capacity exists; run install/restart/encrypted-backup/restore/latency/resource gates.
5. Complete one real owner Sign in with ChatGPT connection, confirm the selected account/model catalog, verify ChatGPT Usage controls prevent credit overage, transfer the protected profile to the target Core, and smoke one bounded Responses turn.
6. Muse Glimmer remains a parked OpenAI-compatible challenger: no new Core module is needed. Promote only when a recurring-free/self-owned host with adequate GPU memory is proven; current public inference-provider availability does not satisfy that gate.
7. Evaluate the Intern Discovery GPU burst lane only as a challenger: read point/hour estimates before creating resources and implement an adapter only after a real no-overage/account gate exists.
8. Verify production entitlement/cost for every retained model/coding route and account-level MFA/2FA.
9. Only after those gates, keep the transitional Worker disabled or retire it, then prepare an exact-SHA canonical production release.
