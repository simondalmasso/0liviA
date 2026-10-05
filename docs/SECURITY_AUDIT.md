# Security audit reconciliation — refreshed 2026-10-05

Source: adversarial read-only Arena Agent report supplied by the owner.

This document records which findings apply to canonical `main`. Historical branches/prototypes are evidence only and are not production contracts.

## Applies to the active branch

### PUBLIC-SHELL-STALE — FIXED / canonical backend still gated
The historical public Worker was stale and model-capable. It has now been replaced by an exact-SHA **inert public shell** built from `4ad53fdfd6e1664763c73ea5847582ba2ed99157`. Core CI run `37266316863` and mobile Playwright run `37266316851` passed. Public-shell deploy run `37266503642` passed with Cloudflare version `6648267c-f2fb-418a-9340-1fff63771ce8`, `PUBLIC_SHELL_OK=YES`, `INFERENCE_DISABLED=YES`, `bridge_enabled:false`, `provider_ready:false`, and `/api/chat` verified as `503 bridge_disabled`.

This fixes the stale/shared-inference exposure of the **public shell**. It does **not** mean the canonical Python Core is deployed; authenticated durable chat/memory/voice still require the canonical host.

### OWNER-REGISTRATION — FIXED IN BRANCH
The canonical Core now uses first-run single-owner registration: email + scrypt password verifier are stored server-side, registration closes after the first owner, remembered sessions are bound to random server-side device IDs, and those devices are revocable from the Session UI. Session-only login leaves no durable trusted-device record. Internet-facing bootstrap also generates a one-shot registration token; it is delivered through a URL fragment from root-only bootstrap state, consumed in-memory by the browser and immediately removed from the address bar, so it is not sent in HTTP requests or access logs. No API key or bearer is entered into the browser UI.

### UI-GATEWAY-CONTRACT — FIXED IN BRANCH
The browser shell detects the canonical core, authenticates with a Secure/HttpOnly/SameSite owner cookie, creates/reuses server-side sessions, migrates cached history through the redacting session API, and streams via `POST /api/chat/{session_id}`. Projects, Chats, Library and Memory now reconcile through authenticated server-side workspace APIs; IndexedDB is cache/migration only in canonical mode.

### CODING-WORKFLOW-INPUTS — FIXED IN BRANCH
Direct `workflow_dispatch` inputs are no longer interpolated into shell commands for diff/ref operations. `base_ref` is passed through an environment variable and validated; checkout credentials are not persisted. Agent execution has repository read permission only. Optional publication is isolated into a second write-capable job that applies a verified patch artifact; the model/NIM credential is not present in that publish job.

### SECRET-EGRESS — FIXED IN BRANCH
The Python core redacts common credential formats before provider egress and again at the SQLite Store boundary for messages, projects, Library, Memory, events and job checkpoints. A future endpoint forgetting its own redaction therefore cannot trivially persist the covered credential formats. Explicit forget now physically deletes all durable versions of a memory key instead of only deactivating it. Existing historical databases must still be treated as potentially containing pre-fix values.

### WEB-RESEARCH-BOUNDARY — FIXED / gated
The canonical `/read` path uses an SSRF-safe URL reader and injects page text only as ephemeral untrusted model context; fetched page contents are not persisted. `/search` is disabled unless an explicit adapter is configured and its exact route is marked zero-cost verified. No Cloudflare Web Search call occurs by default.

### BROWSER-WORKER-ISOLATION — FIXED IN BRANCH / write automation gated
The canonical Core exposes `/browse` only through an opt-in GitHub Actions burst worker. URL validation rejects private/reserved targets and sensitive query parameters, the runner performs bounded read-only GET/HEAD navigation, artifacts are size-bounded, and external page content does not become durable chat/model state automatically. Owner-approved click/write automation remains intentionally unimplemented.

### VOICE-WSS-CONTRACT — FIXED IN BRANCH / speech backend gated
The canonical Gateway now exposes the declared direct-WSS voice route behind owner authentication and session validation. It fails closed with 503 while no approved speech backend factory is configured. Binary audio frames remain bounded by the transport contract. This fixes the old route mismatch without claiming production STT/TTS readiness.

### CHATGPT-PLAN-OAUTH — IMPLEMENTED / LIVE CONNECTION GATED
The router supports the official Sign in with ChatGPT plan-usage transport without an API key: protected server-side OAuth profile, serialized refresh-token rotation, `earliest_refresh_at` enforcement and direct Responses API streaming with `store:false`. The one-time local onboarding helper implements PKCE/state/nonce, OpenID discovery, JWKS signature validation, issuer/audience/nonce checks, stable host ID, model discovery and atomic mode-0600 profile writes. Explicit disconnect discovers OpenAI's revocation endpoint, attempts bounded refresh-token revocation, removes the local profile, and reports whether remote revocation was confirmed. VM activation validates the grant/model, requires an explicit no-credit-overage assertion, preserves other providers and rolls back configuration/profile if the Core fails health after restart. No production owner connection is claimed until the real OAuth/account Usage controls and one bounded inference turn are smoked.

### ZERO-COST-ACCOUNT-PROOF — OPEN / fail closed
A request-count cap is not an account billing guard. Cloudflare account-wide billing status could not be verified with the available token. The public Cloudflare surface is now an inert static shell with API routes disabled, and provider readiness is false; no production-cost guarantee is claimed.

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

1. Deploy the canonical Python Core only after an exact-SHA target host passes install/restart/backup/latency/resource smoke; the public shell is already current and inert.
2. Complete a real owner Sign in with ChatGPT connection, verify the app cannot consume paid credits, and smoke the included-plan route on the target Core; separately verify provider/account cost guarantees for any other external inference/search route.
3. Verify Oracle A1 capacity plus install/restart/backup/latency/resource gates on the real host.
4. Benchmark and accept a production voice stack on the real target; current Live Voice backend remains provisional.
5. Verify account-level MFA/2FA on every production control plane and rotate any credential with a real exposure alert.
6. Perform a disposable-host encrypted restore rehearsal and retain the evidence.
7. Perform an exact-release **canonical Core** smoke before declaring authenticated chat/memory/voice production-ready; the public URL shell itself is already exact-SHA verified.

The bootstrap now rejects mutable production refs, generates browser owner authentication without exposing the bearer, and verifies pinned SHA-256 digests for llama.cpp and GGUF artifacts.


### RUNTIME-ZERO-COST-GUARD — FIXED IN BRANCH
The product runtime now forces hard-zero-cost mode on even if an environment variable attempts to disable it. `plan_included` is accepted only for the official `chatgpt_plan` provider kind, where `no_credit_overage_verified=true` is mandatory. Generic OpenAI-compatible routes cannot self-label as subscription-included to bypass the zero-cost filter.
