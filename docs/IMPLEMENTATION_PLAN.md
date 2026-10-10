# Implementation plan — productization checkpoint

Branch: `main`

This file is the current execution checkpoint. Architecture choices live in `docs/DECISIONS.md`; historical council prompts live under `docs/history/`.

## 2026-10-10 UTC — demo safety and deployment-control checkpoint

- Main integration commit: `1c87b8dbeb0aea60a7c72fa89d074473e099c257` (PR #80). Branch CI for Python 3.11/3.12, static security, 360/430-px mobile smoke and mocked local E2E were GREEN; post-merge CI, mobile and local E2E also passed.
- Public demo: POST `/api/demo-chat` requires exact matching `Origin` and JSON bodies bounded by actual bytes (max 16 KiB), even without `Content-Length`. Origin is not owner authentication and can be forged server-side.
- Metering truth: when Workers AI demo is enabled, `/healthz` reports `hard_zero_cost:false` and `demo_cost_guaranteed:false`; 25 shared daily requests is not an account/provider spending limit.
- Public UI now distinguishes the anonymous demo from the private Core; canonical chat, projects, memory and privileged tools remain unavailable on the public Worker.
- `.github/workflows/deploy-public-shell.yml` is **manual `workflow_dispatch` only**, with an explicit `confirm_account_no_overage=true` approval gate before external actions. The merge did not trigger a Cloudflare Wrangler deploy.
- No Cloudflare account/API/inference/deploy action was performed during this work. The public production URL is **not** claimed to run this SHA. Provider account no-overage evidence, authorized exact-SHA deploy and production smoke remain pending.
- Next product gate: recover trusted privileged SSH access to existing recurring-$0 OCI micro VM and validate the canonical Core, rather than enabling unverified shared inference.

## 2026-10-09 Core readiness continuation

- `main@5d3bc113df3ee67142c89efb3932f0fab87324fd` is the last verified public Worker deployment; full CI, live browser chat E2E, exact `/healthz.release_sha` and security headers passed. This is **not** the authenticated Python Core.
- OCI micro Core host remains `PRIVILEGED_HOST_ACCESS_PENDING`. Local read-only recheck found no new authorized SSH material and no OCI CLI executable in the checked PATH; no privileged access was claimed, no host mutation was attempted.
- Prepared workflow safety improvement: manual canonical deploy now defaults to non-mutating SSH/preflight-only mode; actual deploy must be explicitly opted into after owner recovers trusted privileged access. The release smoke rejects empty, error-bearing, malformed and mixed-provider streams even if they include a `done` event.
- No Qwen paid/unverified production entitlement was enabled; provider and account-level $0 proof remain separate gates.

## What is already integrated

- Python control plane with sessions, projects, library, memory, jobs, checkpoints and events.
- Persistent provider-health state with quota admission, circuit breaker, half-open recovery, cancellation and redacted telemetry.
- One-time Sign in with ChatGPT OAuth onboarding helper is implemented with PKCE/state/nonce, OIDC/JWKS validation, protected 0600 profiles, model discovery and transactional/reversible VM activation.
- Failover only before validated visible output; partial answers are preserved rather than silently replayed through another provider.
- Browser/API gateway with first-run single-owner registration, email/password login, remembered-device revocation, login throttling, bounded bodies and one active turn per session.
- Authenticated server-side workspace API backed by SQLite; Projects/Chats/Library/Memory sync into browser cache when the canonical core is active.
- Current browser product shell with Chats/Projects/Library/Memory/Config/Session rail navigation, first-run auth UI, remembered-device management, fullscreen Live Voice, contextual slash commands and compact in-chat durable job state. Mobile layouts are smoke-verified at 360×800 and 430×900 with no horizontal overflow, stable composer placement and functional Session drawer.
- Canonical SSRF-safe `/read` tool with page content kept ephemeral and explicitly untrusted.
- Replaceable `/search` adapter contract, disabled unless an exact route is configured and zero-cost verified.
- Capability-aware provider catalog (`chat/research/vision/code/review`) with backwards-compatible chat defaults; research tools prefer a research-capable route and safely fall back to chat when none is configured.
- Isolated GitHub Actions coding worker with durable job IDs, exact base refs, `implement/repair/review` modes and deterministic post-agent verification.
- Isolated JS browser burst worker with `/browse`, JavaScript rendering, read-only GET/HEAD enforcement, public-network egress guards and bounded artifacts; `/inspect <job_id>` explicitly analyzes a finished render as ephemeral untrusted research context without persisting page text into chat/memory.
- Review mode may only create/update `AGENT_REVIEW.md`; any product mutation fails the job.
- Authenticated `/api/voice/ws` direct-WSS endpoint plus a browser/mobile WSS client, voice contracts/pipeline/sequence/cancel tests and benchmark recorder. The UI selects canonical WSS only when `/healthz` reports `voice_backend_configured=true`; otherwise it keeps the existing browser speech path as a provisional fallback. The WSS endpoint itself still fails 503 until an approved speech backend factory is configured.
- Production bootstrap source/artifact pinning, first-run registration bootstrap and Caddy hardening.
- Manual exact-SHA canonical SSH deploy workflow (`.github/workflows/deploy-canonical.yml`) with pinned host trust, password SSH disabled, fail-closed host preflight, rollback-capable bootstrap and loopback canonical/hard-zero-cost health verification; a real recurring-$0 OCI host now exists, but the workflow remains unexecuted until privileged SSH and the four deploy secrets are established.
- Exact production smoke gate: target must report the requested 40-hex build SHA, `api_mode=canonical`, `hard_zero_cost=true`, completed owner registration, at least one available `local/free_hard_cap/plan_included` provider, and a routed+completed streamed chat turn.
- Repository hygiene tests preventing stale build claims and active-doc duplication.
- **2026-10-08 live public-demo evidence (not a canonical Core release):** the permanent public Worker URL returned HTTP 200 and `/healthz` reported `api_mode=public_shell`, `demo_provider_ready=true`, `demo_model=@cf/zai-org/glm-4.7-flash`, `hard_zero_cost=true`. An actual `POST /api/demo-chat` returned a Spanish answer and the declared model. `tester-army/e2e v0.18.0` passed **1/1** against the permanent URL with `OLIVIA_E2E_LIVE=1`, no mocks, Chromium mobile, exact source checkout `c9066a16c1d78281185fcb0e259125af42d85566`; E2E process exited 0, test duration 28.52s. This verifies the public chat *path* at that time, not persistent authenticated features.
- **Deployment drift:** live HTML bytes (93,821; SHA-256 `fc09a3ff7080b16367acf1f35a8f4cfe9da307c0a1878764175f2dbdad9e57f5`) matched the committed `web/index.html` blob at `f178a3579d7a68ea6915b38403e6fae5d9eddd23`, not the newer `main@c9066a1` UI blob (93,895 bytes; SHA-256 `a0b1422e56ea2859dc8f16a4cf059cbe7cb9e7563d972f939ea62064b73efc16`). Therefore the #69 error-display fix is **not proven deployed**. Backend exact SHA/version is unknown; no exact-SHA production claim is justified.
- **Remaining deploy gate:** GitHub Actions public-shell run `37797435212` failed before deployment in `Require Cloudflare deployment credentials` (secret token/account ID and/or the explicit zero-cost verification variable). A manual/out-of-band deployment may be serving the live demo, but the canonical GitHub release workflow cannot currently promote current `main`. Verify real account billing/overage safety independently; the Worker health flag alone is not a billing audit. Cloudflare remains an isolated demo, not the Python Core.

Runtime-call discipline:
- public shell has no periodic polling loop;
- focus changes do not trigger health/sync calls;
- health state is cached for five minutes;
- retries are event-driven (`online`) or tied to explicit user actions.

## Productization gates

### 1. Canonical cloud runtime
The roomy preferred target remains Oracle A1 ARM64 (2 OCPU / 12 GB), but it is not a production prerequisite. The current recurring-$0 candidate is `olivia-text-free`, Ubuntu 24.04 x86_64 on `VM.Standard.E2.1.Micro` (1 OCPU / 1 GB); the bootstrap supports x86_64/ARM64 and creates swap for the <2 GB micro path. Do not claim production runtime until a candidate host passes privileged preflight, install, restart, backup/restore and latency/resource smoke tests.

### 2. Workspace durability
The canonical Python Core is now the durable source of truth for Projects/Chats/Library/Memory. IndexedDB is a disposable cache/migration layer when canonical mode is available. The temporary Cloudflare bridge remains non-durable by design and must not be presented as multi-device persistence.

### 3. Stable zero-cost model routing
Provider routing must remain catalog-driven and fail closed:
- hard-zero-cost is a product invariant; runtime ENV cannot turn this guard off;
- never move to a paid/unverified route silently;
- `plan_included` is reserved for the official `chatgpt_plan` transport and requires explicit no-credit-overage verification;
- official ChatGPT-plan usage is the preferred frontier-quality lane for eligible Plus/Pro owners once OAuth onboarding exists and no-credit-overage is explicitly verified; exhaustion must fail/degrade rather than use credits silently;
- DeepSeek V4.1 Flash/NVIDIA NIM remains development/evaluation-only unless explicit production entitlement exists;
- canonical Cloudflare inference/read stays disabled; only the isolated public demo may use Workers AI, and only after account-wide zero-cost behavior is independently verified and the server-side daily cap is active;
- local inference is allowed as a zero-cost fallback but is not the quality target for normal chat;
- Intern Discovery / Intern InkStone is a promising GPU burst lane for Muse Glimmer, but remains `free_unverified` until its account-level point exhaustion/no-overage behavior and a real service response contract are proven.

### 4. Research/browser
Implemented:
- `/read`: SSRF-safe public URL reader, redirect/IP/body bounded, injected only as ephemeral untrusted context.
- `/search`: replaceable search contract, disabled by default, refuses routes without explicit zero-cost verification.
- `/research`: bounded search+read orchestration (max 3 results) using the same fail-closed search gate and SSRF-safe reader; external content remains ephemeral.

Still gated:
- authenticated browsing;
- owner-approved write/click automation remains a separate future capability.

Implemented in branch:
- `/browse`: opt-in GitHub Actions burst worker using a dedicated private GitHub repository, pinned Playwright, JavaScript rendering, reserved/private-network egress blocks, no third-party browser secrets, bounded requests/text/artifacts, Core-side repository-privacy preflight, and external page content kept out of durable chat/model context until explicitly requested.

### 5. Live Voice
The UI, authenticated direct-WSS Gateway route, browser/mobile WSS client and Python pipeline now exist; production speech engines do not. The route is capability-gated and returns 503 until a backend is configured. Benchmark direct WSS + candidate VAD/STT/TTS on the actual target host for es-AR quality, TTFT/TTFA, barge-in and 60-minute stability before promotion. LiveKit Agents and Pipecat remain challengers, not defaults.

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
- exact production smoke using the repository gate; the gate exists, but no canonical production host has passed it yet.

## Repository discipline

- `main` is the canonical integration branch. Use isolated feature/agent branches for mutations and merge only verified changes.
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
2. Historical browser smoke rendered a controlled public page successfully, but the old public-repository artifact path is superseded. Production `/browse` now requires a dedicated private GitHub repository plus explicit zero-cost verification; rerun the smoke on that private boundary before calling browser work production-ready. Keep `/browse` read-only; owner-approved click/write automation remains separate.
3. Run target-host voice benchmarks and compare Direct WSS, Pipecat and LiveKit challenger paths.
4. Certify the existing recurring-$0 `olivia-text-free` host first: recover/pin privileged `ubuntu` SSH without disturbing existing access, pass `deploy/preflight.sh`, add only the four deploy secrets (`OLIVIA_DEPLOY_HOST`, `OLIVIA_DEPLOY_USER`, `OLIVIA_DEPLOY_SSH_KEY`, `OLIVIA_DEPLOY_KNOWN_HOSTS`) in GitHub, and run the manual exact-SHA canonical workflow. Then run install/restart/encrypted-backup/restore/latency/resource gates. A1 remains an optional roomier migration target when capacity exists.
5. Complete one real owner Sign in with ChatGPT connection, confirm the selected account/model catalog, verify ChatGPT Usage controls prevent credit overage, transfer the protected profile to the target Core, and smoke one bounded Responses turn.
6. Muse Glimmer remains a parked OpenAI-compatible challenger: no new Core module is needed. Promote only when a recurring-free/self-owned host with adequate GPU memory is proven; current public inference-provider availability does not satisfy that gate.
7. Evaluate the Intern Discovery GPU burst lane only as a challenger: read point/hour estimates before creating resources and implement an adapter only after a real no-overage/account gate exists.
8. Verify production entitlement/cost for every retained model/coding route and account-level MFA/2FA.
9. Keep the public shell non-canonical. A demo deployment is acceptable only after exact-SHA smoke plus live E2E; independently, deploy the **canonical Python Core** only after the remaining host/provider/voice gates and smoke the authenticated product end to end.
