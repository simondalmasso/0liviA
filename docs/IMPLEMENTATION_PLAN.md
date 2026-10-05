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

1. Re-audit the current green branch for stale docs/dead paths and keep repository hygiene green.
2. Add the isolated JS-capable browser worker only if a zero-cost runtime path is available.
3. Run target-host voice benchmarks and compare Direct WSS, Pipecat and LiveKit challenger paths.
4. Provision/verify an Oracle A1 host when capacity exists; run install/restart/backup/latency/resource gates.
5. Verify production entitlement/cost for the preferred model/coding routes.
6. Only after those gates, keep the transitional Worker disabled or retire it, then prepare an exact-SHA canonical production release.
