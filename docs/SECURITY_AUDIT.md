# Security audit reconciliation — 2026-10-04

Source: adversarial read-only Arena Agent report supplied by the owner.

This document records which findings apply to the active integration branch `arch/gpt-synthesis-v1`. Historical branches/prototypes are evidence only and are not production contracts.

## Applies to the active branch

### PUBLIC-PROD-STALE — OPEN / deployment gate
The public Worker was observed serving an older UI/Worker generation. Its exact live SHA and billing plan are not independently verified here. Do not claim the public deployment is current, private or guaranteed USD 0 until an exact-SHA deploy and smoke are performed.

### UI-GATEWAY-CONTRACT — OPEN
The browser shell currently targets the temporary stateless bridge at `POST /api/chat`. The canonical Python Gateway exposes authenticated `POST /api/chat/{session_id}` plus server-side sessions. This mismatch is real and blocks calling the browser shell a canonical-core client.

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

1. Replace/retire the stale public Worker deployment only after the target backend/auth model is settled.
2. Unify the browser shell with the canonical authenticated server-side session API.
3. Establish owner authentication that does not put bearer tokens in URLs or browser durable storage.
4. Verify provider/account cost guarantees before enabling any externally metered production route.
5. Pin production bootstrap/deploy refs to immutable SHAs and verify downloaded runtime/model artifacts.
