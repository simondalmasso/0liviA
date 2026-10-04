# Implementation plan — productization checkpoint

Branch: `arch/gpt-synthesis-v1`

This file is the current execution checkpoint. Architecture choices live in `docs/DECISIONS.md`; historical council prompts live under `docs/history/`.

## What is already integrated

- Python control plane with sessions, messages, memory, jobs, checkpoints and events.
- Persistent provider-health state with quota admission, circuit breaker, half-open recovery, cancellation and redacted telemetry.
- Failover only before validated visible output; partial answers are preserved rather than silently replayed through another provider.
- Browser/API gateway with auth, bounded bodies and one active turn per session.
- Current browser product shell with rail navigation, projects, library, memory, config and fullscreen Live Voice UI.
- Temporary Cloudflare bridge with read-only URL ingestion, SSRF/redirect/body limits and fail-closed provider eligibility.
- Isolated GitHub Actions coding worker with durable job IDs, exact base refs and deterministic post-agent verification.
- Voice contracts/pipeline/sequence/cancel tests and benchmark recorder.
- Repository hygiene tests preventing stale build claims and active-doc duplication.

## Productization gates

### 1. Canonical cloud runtime
Target remains Oracle A1 ARM64 (2 OCPU / 12 GB). Do not claim production runtime until an actual host is available and passes install, restart, backup and latency/resource smoke tests.

### 2. Durable multi-device workspace
The temporary bridge UI still uses IndexedDB for Projects/Chats/Library/Memory. Treat it as disposable cache. Move these surfaces behind authenticated server APIs backed by canonical durable storage before calling persistence complete.

### 3. Stable zero-cost model routing
Provider routing must remain catalog-driven and fail closed:
- never move to a paid/unverified route silently;
- DeepSeek V4.1 Flash/NVIDIA NIM remains development/evaluation-only unless explicit production entitlement exists;
- Cloudflare Workers AI remains unavailable to the bridge until account-wide zero-cost behavior is independently verified;
- local inference is allowed as a zero-cost fallback but is not the quality target for normal chat.

### 4. Research/browser worker
Read-only URL ingestion is implemented. General search, JS-heavy browsing and browser automation still require an isolated on-demand worker with prompt-injection boundaries and no arbitrary gateway shell.

### 5. Live Voice
The UI and Python contracts exist; production speech engines do not. Benchmark direct WSS + candidate VAD/STT/TTS on the actual target host for es-AR quality, TTFT/TTFA, barge-in and 60-minute stability before promotion.

### 6. Coding worker
The GitHub Actions worker is implemented but remains opt-in:
- secrets server-side only;
- no auto-merge;
- exact base ref;
- isolated agent branch;
- final deterministic verification required;
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

1. Finish repo/product cleanup and rerun all gates.
2. Add authenticated server-side workspace APIs and migrate the browser cache contract.
3. Add the isolated research/browser worker.
4. Provision/verify an Oracle A1 host when capacity exists; run the target-host benchmark matrix.
5. Only after those gates, reconcile/remove the temporary Cloudflare bridge and prepare a production release.
