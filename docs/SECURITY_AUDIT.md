# Security audit reconciliation — 2026-10-04

Source: adversarial read-only Arena Agent report supplied by the owner.

This document records which findings apply to the active integration branch `arch/gpt-synthesis-v1`. Historical branches/prototypes are evidence only and are not production contracts.

## Applies to the active branch

### PUBLIC-PROD-STALE — OPEN / deployment gate
The public Worker was observed serving an older UI/Worker generation. Its exact live SHA and billing plan are not independently verified here. Do not claim the public deployment is current, private or guaranteed USD 0 until an exact-SHA deploy and smoke are performed.

### UI-GATEWAY-CONTRACT — FIXED IN BRANCH
The browser shell detects the canonical core, authenticates with a Secure/HttpOnly/SameSite owner cookie, creates/reuses server-side sessions, imports local history through the redacting session API, reconciles unknown server sessions into its disposable cache, and streams via `POST /api/chat/{session_id}`.

### CODING-WORKFLOW-INPUTS — FIXED IN BRANCH
Direct `workflow_dispatch` inputs are no longer interpolated into shell commands for diff/ref operations. `base_ref` is passed through an environment variable and validated; checkout credentials are not persisted. The GitHub token is exposed only to the final optional publish step.

### SECRET-EGRESS — FIXED IN BRANCH
The Python core now rejects secret-like durable-memory values and redacts common credential formats before durable message storage or provider egress. Existing historical databases must still be treated as potentially containing pre-fix values.

### ZERO-COST-ACCOUNT-PROOF — OPEN / fail closed
A request-count cap is not an account billing guard. Cloudflare account-wide billing status could not be verified with the available token. Worker provider readiness therefore remains gated; no production-cost guarantee is claimed.

## Does not apply to the active branch

### `slice/` DEV-OPEN / shell / query-token / GET-chat findings
These refer to a local historical council slice that is not part of `arch/gpt-synthesis-v1`. The active Python Gateway defaults to `127.0.0.1`, fails authentication closed when no bearer token exists, limits request bodies, and exposes no general shell tool.

### Direct HTTP memory endpoint bypass
The active Gateway has no `POST /api/memory` route. Durable explicit memory promotion is handled in the Agent and now passes through the centralized secret guard.

### Worker SSE newline claim
The active Worker uses JavaScript string/template escape sequences such as `\n\n`; those evaluate to real LF delimiters at runtime. Treat this as a false positive unless a runtime byte-level smoke shows otherwise.

## Remaining release blockers

1. Replace/retire the stale public Worker only after an exact-SHA canonical target host passes smoke.
2. Verify provider/account cost guarantees before enabling externally metered production routes.
3. Verify Oracle A1 capacity plus restart/backup/latency/resource gates on the real host.
4. Perform an exact-release production smoke before declaring the public URL current.

The bootstrap now rejects mutable production refs, generates browser owner authentication without exposing the bearer, and verifies pinned SHA-256 digests for llama.cpp and GGUF artifacts.
