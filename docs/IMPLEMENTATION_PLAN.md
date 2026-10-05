# Implementation plan — productization checkpoint

Branch: `arch/gpt-synthesis-v1`

This file is the current execution checkpoint. Architecture choices live in `docs/DECISIONS.md`; historical council prompts live under `docs/history/`.

## What is already integrated

- Python control plane with sessions, projects, library, memory, jobs, checkpoints and events.
- Persistent provider-health state with quota admission, circuit breaker, half-open recovery, cancellation and redacted telemetry.
- Failover only before validated visible output; partial answers are preserved rather than silently replayed through another provider.
- Browser/API gateway with first-run single-owner registration, email/password login, remembered-device revocation, login throttling, bounded bodies and one active turn per session.
- Authenticated server-side workspace API backed by SQLite; Projects/Chats/Library/Memory sync into browser cache when the canonical core is active.
- Current browser product shell with Chats/Projects/Library/Memory/Config/Session rail navigation, first-run auth UI, remembered-device management, fullscreen Live Voice, and 360–430 px responsive hardening.
- Canonical SSRF-safe `/read` tool with page content kept ephemeral and explicitly untrusted.
- Replaceable `/search` adapter contract, disabled unless an exact route is configured and zero-cost verified.
- Isolated GitHub Actions coding worker with durable job IDs, exact base refs, `implement/repair/review` modes and deterministic post-agent verification.
- Review mode may only create/update `AGENT_REVIEW.md`; any product mutation fails the job.
- Voice contracts/pipeline/sequence/cancel tests and benchmark recorder.
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
- DeepSeek V4.1 Flash/NVIDIA NIM remains development/evaluation-only unless explicit production entitlement exists;
- the transitional Cloudflare bridge is disabled by default; Workers AI/read routes remain unavailable until both identity and account-wide zero-cost behavior are independently verified;
- local inference is allowed as a zero-cost fallback but is not the quality target for normal chat.

### 4. Research/browser
Implemented:
- `/read`: SSRF-safe public URL reader, redirect/IP/body bounded, injected only as ephemeral untrusted context.
- `/search`: replaceable search contract, disabled by default, refuses routes without explicit zero-cost verification.
- `/research`: bounded search+read orchestration (max 3 results) using the same fail-closed search gate and SSRF-safe reader; external content remains ephemeral.

Still gated:
- JS-heavy browsing;
- authenticated browsing;
- browser automation;
- isolated Playwright-class worker and prompt-injection containment beyond text ingestion.

### 5. Live Voice
The UI and Python contracts exist; production speech engines do not. Benchmark direct WSS + candidate VAD/STT/TTS on the actual target host for es-AR quality, TTFT/TTFA, barge-in and 60-minute stability before promotion. LiveKit Agents and Pipecat remain challengers, not defaults.

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
2. Add a JS-capable browser worker only with real process/network isolation and a zero-cost runtime path; do not embed a privileged Playwright browser inside the Core.
3. Run target-host voice benchmarks and compare Direct WSS, Pipecat and LiveKit challenger paths.
4. Provision/verify an Oracle A1 host when capacity exists; run install/restart/encrypted-backup/restore/latency/resource gates.
5. Evaluate the Intern Discovery GPU burst lane: read the A100 point/hour estimate without creating resources; prefer official Muse BF16 if cloud-disk expansion reaches >=70 GB, otherwise benchmark the 22.2 GB INT4 challenger. Implement an adapter only after capturing the real inference-service request/response schema without its credential.
6. Verify production entitlement/cost for the preferred model/coding routes and account-level MFA/2FA.
7. Only after those gates, keep the transitional Worker disabled or retire it, then prepare an exact-SHA canonical production release.
