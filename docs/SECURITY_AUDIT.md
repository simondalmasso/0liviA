# Security audit reconciliation — 2026-10-04

Source: adversarial read-only Arena Agent report supplied by the owner.

This document records which findings apply to the active integration branch `arch/gpt-synthesis-v1`. Historical branches/prototypes are evidence only and are not production contracts.

## Applies to the active branch

### PUBLIC-PROD-STALE — OPEN / deployment gate
The public Worker was observed serving an older UI/Worker generation. Its exact live SHA and billing plan are not independently verified here. The branch Worker is now disabled by default for chat/read, so an accidental future deploy fails closed; this does not change the unknown state of the currently live historical Worker. Do not claim the public deployment is current, private or guaranteed USD 0 until an exact-SHA canonical deploy and smoke are performed.

### OWNER-REGISTRATION — FIXED IN BRANCH
The canonical Core now uses first-run single-owner registration: email + scrypt password verifier are stored server-side, registration closes after the first owner, remembered sessions are bound to random server-side device IDs, and those devices are revocable from the Session UI. Session-only login leaves no durable trusted-device record. No API key or bearer is entered into the browser UI.

### UI-GATEWAY-CONTRACT — FIXED IN BRANCH
The browser shell detects the canonical core, authenticates with a Secure/HttpOnly/SameSite owner cookie, creates/reuses server-side sessions, migrates cached history through the redacting session API, and streams via `POST /api/chat/{session_id}`. Projects, Chats, Library and Memory now reconcile through authenticated server-side workspace APIs; IndexedDB is cache/migration only in canonical mode.

### CODING-WORKFLOW-INPUTS — FIXED IN BRANCH
Direct `workflow_dispatch` inputs are no longer interpolated into shell commands for diff/ref operations. `base_ref` is passed through an environment variable and validated; checkout credentials are not persisted. Agent execution has repository read permission only. Optional publication is isolated into a second write-capable job that applies a verified patch artifact; the model/NIM credential is not present in that publish job.

### SECRET-EGRESS — FIXED IN BRANCH
The Python core now rejects secret-like durable-memory values and redacts common credential formats before durable message storage or provider egress. Existing historical databases must still be treated as potentially containing pre-fix values.

### WEB-RESEARCH-BOUNDARY — FIXED / gated
The canonical `/read` path uses an SSRF-safe URL reader and injects page text only as ephemeral untrusted model context; fetched page contents are not persisted. `/search` is disabled unless an explicit adapter is configured and its exact route is marked zero-cost verified. No Cloudflare Web Search call occurs by default.

### VOICE-WSS-CONTRACT — FIXED IN BRANCH / speech backend gated
The canonical Gateway now exposes the declared direct-WSS voice route behind owner authentication and session validation. It fails closed with 503 while no approved speech backend factory is configured. Binary audio frames remain bounded by the transport contract. This fixes the old route mismatch without claiming production STT/TTS readiness.

### ZERO-COST-ACCOUNT-PROOF — OPEN / fail closed
A request-count cap is not an account billing guard. Cloudflare account-wide billing status could not be verified with the available token. The transitional Worker runtime is now disabled by default, and provider readiness is false while disabled; no production-cost guarantee is claimed.

## Does not apply to the active branch

### `slice/` DEV-OPEN / shell / query-token / GET-chat findings
These refer to a local historical council slice that is not part of `arch/gpt-synthesis-v1`. The active Python Gateway defaults to `127.0.0.1`, fails authentication closed when no bearer token exists, limits request bodies, and exposes no general shell tool.

### Direct HTTP memory endpoint bypass
The active Gateway has no `POST /api/memory` route. Durable explicit memory promotion is handled in the Agent and now passes through the centralized secret guard.

### Worker SSE newline claim
The active Worker uses JavaScript string/template escape sequences such as `\n\n`; those evaluate to real LF delimiters at runtime. Treat this as a false positive unless a runtime byte-level smoke shows otherwise.

### AUTH-SURFACE-REGRESSION — FIXED / CI-gated
All sensitive API routes are covered by an unauthenticated regression gate. The only intentionally public HTTP surfaces are the static UI, health, registration/login and logout; first-owner registration can additionally require the one-shot setup token. Login throttling state is bounded and purged so hostile IP churn cannot grow the in-memory map without limit.

### SEARCH-BILLING-FALLBACK — FIXED / fail closed
Cloudflare Web Search remains disabled unless zero-cost behavior is explicitly verified. When enabled with BYOK, requests carry both a required `byokAlias` and `cf-aig-no-wholesale: true`, so missing provider credentials fail rather than falling back to AI Gateway wholesale credits.

### SECURITY-BASELINE-CHECKLIST — ENFORCED IN BRANCH
The owner security checklist is now represented by code/tests rather than UI assumptions:
- scrypt password verifiers; no plaintext password storage;
- parameterized SQL only in the durable Store;
- bounded/typed JSON inputs;
- login throttling and no public reset/email-recovery endpoint;
- anti-enumeration: wrong email and wrong password return the same login error;
- expiring Secure/HttpOnly/SameSite session cookies;
- owner authorization is re-checked on every private server route;
- API requests with a foreign Origin fail closed; no wildcard credentialed CORS;
- browser message rendering uses text nodes for untrusted content;
- coding-agent execution has repository read permission only; write permission exists only in a separate post-verification publish job without the model credential;
- durable messages/events/checkpoints are redacted at the Store boundary;
- literal-secret hygiene test covers runtime/deploy/workflow sources;
- encrypted SQLite backup + integrity-checked restore round-trip runs in CI;
- Dependabot is registered for Python and GitHub Actions;
- sanitized owner-only `security.*` event feed exists for incident review.

Operational controls that cannot be truthfully enforced from this repo remain external gates:
- rotate any credential reported as leaked at the provider/account, then update encrypted secret stores;
- enable MFA/2FA on GitHub, Oracle Cloud and any retained Cloudflare/provider control plane;
- periodically rehearse restore on a disposable target;
- investigate sanitized security events after anomalies.

See `docs/SECURITY_OPERATIONS.md`.

## Remaining release blockers

1. Replace/retire the stale public Worker only after an exact-SHA canonical target host passes smoke.
2. Verify provider/account cost guarantees before enabling externally metered production inference or search routes.
3. Verify Oracle A1 capacity plus install/restart/backup/latency/resource gates on the real host.
4. Benchmark and accept a production voice stack on the real target; current Live Voice backend remains provisional.
5. Verify account-level MFA/2FA on every production control plane and rotate any credential with a real exposure alert.
6. Perform a disposable-host encrypted restore rehearsal and retain the evidence.
7. Perform an exact-release production smoke before declaring the public URL current.

The bootstrap now rejects mutable production refs, generates browser owner authentication without exposing the bearer, and verifies pinned SHA-256 digests for llama.cpp and GGUF artifacts.
