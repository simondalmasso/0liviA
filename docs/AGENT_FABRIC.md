# Agent Fabric — PR-A: model admission and budgets

Status: **opt-in harness primitives only; NOT enabled on canonical chat or Cloudflare demo**.

AUD master plan: [issue #97](https://github.com/simondalmasso/0liviA/issues/97#issuecomment-6099758456). The existing `ProviderPool`, SQLite Core, coding worker and browser worker remain canonical; PR-A does **not** replace them or enable any provider.

## Trust and data flow

1. Operator first verifies the **actual account** entitlement and records an attestation in a **private, trusted, server-side** source; account ID is a nonsecret opaque label. An issue link is a review pointer, not independent proof of billing safety. This PR does **not** mint attestations automatically, verify billing accounts, run inference canaries, or enable any cloud provider.
2. `ModelRegistry` has an empty attestation set by default. `admit(provider,capability,max_input,max_output,parent_budget)` rejects unknown models, forbidden Nemotron routes, unverified cost/production rights, expired attestations, local endpoints that are not loopback, unsupported capabilities, missing quotas, and exceeded token budgets. Only `local` and `free_hard_cap` are eligible for **this new agent fabric** (existing Core `plan_included` route remains unchanged pending independent audit).
3. `BudgetGuard` uses `BEGIN IMMEDIATE` reservations in the existing SQLite database file with separate table names. It atomically increments a parent-to-root chain, per-account/per-model/day counters **and a shared per-account billing pool/day ledger** before any provider call. All Qwen/GPT-OSS/GLM attempts within one Cloudflare account must draw from the same `workers_ai` pool in pessimistically estimated neurons. Each attestation needs the exact endpoint, a verified UTC usage day, external-consumption floor, conservative per-million input/output neuron rates, an operator-approved account-level daily budget, output-cap verification, and evidence of no concurrent unknown writers; otherwise admission is denied. A duplicate request ID is never returned for execution, even after restart, timeout or uncertain stream outcome; no refund on uncertainty. Scope declarations cannot be enlarged or reparented. Existing `ProviderHealth` quota/breakers still apply when later connected via adapter.
4. `guarded_stream` demonstrates one *single* provider call with admission and reservation, and no automatic retries. The adapter for the existing router/fallback policy is PR-C; **do not call `ProviderPool.stream` without the eventual registry gateway from Agent Fabric**. Do not deploy until tests/audit prove complete gate coverage.

These are **defense-in-depth software budgets**, not account-side spending caps. Estimated input tokens and declared output limits do not bound a provider's invoice; hard USD 0 requires separate, current, external no-overage evidence and usage-rights confirmation. Never claim a promotional credit is recurring-free. Never use Nemotron.

## PR-B boundaries

Durable AgentSpec/AgentRun, parent-child permission intersection, approval and cancellation, idempotency and explicit uncertain state, checkpoints/receipts, and SQLite lease orchestration. All new agents begin as **draft** and cannot invoke any model/tool without explicit owner-approved policy. No default auto-spawn or automatic retry.

## AUD P1 gates (2026-10-10)

- **P1.1 shared pool:** A per-model request counter is not enough for Cloudflare Workers AI. `fabric_shared_pool_limits` keys by UTC day, account ID and product pool, **not model**. The implementation reserves ceiling-rounded, worst-case input+output neurons. The shared daily cap can only tighten across attestations; external usage floor only increases. Reservations are retained on errors, timeouts, cancellation and uncertain results. Daily reset uses UTC. The externally reported 10K Workers Free neurons is **not** our approved usable allowance; leave headroom for other usage and do not treat Paid plans as no-overage.
- **P1.2 output bound:** Legacy `provider.stream(messages)` is categorically rejected by the new `guarded_stream`. The future adapter must prepare an exact serialized provider request, bind its model, complete messages and vendor cap (`max_tokens`, `max_completion_tokens`, or `max_output_tokens`), prove that cap includes reasoning, and transmit those **same prepared bytes**. The admission validates a conservative UTF-8 byte upper bound for all serialized input, including tools, before reservation. Until an adapter is separately audited and attached, **no remote model call can use PR-A**.
- **Three selected candidates are OFF:** `@cf/qwen/qwen3.8-27b`, `@cf/openai/gpt-oss-120b` (shared Workers AI account neurons, pending account-specific billing proof and bounded adapters) and NVIDIA `deepseek-ai/deepseek-v4.1-flash` (existing manual one-request evaluation workflow only; never this production router). GLM 4.7 Flash stays as previously implemented and disabled on the static demo. Nemotron is forbidden.

This module has no trusted production attestation loaded by default. All positive test attestations are **synthetic fixtures**, never evidence of a real account entitlement.


## PR-B: durable agents and run-state (control plane only)

**No automatic execution is possible in PR-B.** `AgentFabric` in
`olivia/harness/agents.py` is not wired to an HTTP endpoint, canonical chat,
GitHub Actions, SentinelX, a model, or an MCP service.

- Every `propose(...)` creates a **draft** agent. A planning LLM may propose an
  agent, but it cannot approve it. Reuse of the exact proposal key and immutable
  spec is idempotent; conflicting changes are rejected.
- `approve(agent_id, proof)` needs a separate, trusted Core owner-verification
  callback. With no callback, it always denies. The callback must check
  authenticated owner context and a one-time approval proof against the exact
  stored proposal SHA; **passing a string is not authentication**. Never expose
  arbitrary callback injection through HTTP, prompts, or tool arguments.
- Children may be proposed only below already approved parents and inherit
  **strict subsets** of their tool permissions and token/call ceilings. Each
  child still requires its own owner approval. Budget scope creation and
  approval are one SQLite transaction. Draft agents have no usable PR-A scope.
- Queuing a run consumes a permanent call slot across **all ancestor agents**,
  atomically, even if that run later fails, is cancelled or expires. A separate
  PR-A budget reservation still applies to actual model inference and shared
  account limits. This over-reservation is intentional until end-to-end
  accounting is audited.
- A distinct trusted executor verifier must authorize a **single** lease.
  Workers cannot claim based only on knowing a job ID. Expired leases transition
  to `uncertain`; no scheduler or automatic retries are implemented. Sequential
  checkpoints are stored durably and readable only through owner verification.
- Cancelling an agent recursively revokes its children. Queued runs become
  cancelled; already leased runs become `cancellation_requested`, **not**
  falsely reported as stopped. They require a matching lease acknowledgment,
  or expire to `uncertain`.
- An uncertain run is only reconciled manually with owner verification and
  a 64-character SHA-256 evidence digest. No replay or new dispatch is implied.
- Audit events are immutable structured names and timestamps; they intentionally
  omit prompts, API keys and raw approval proofs.

**Pending PR-C:** bind authenticated Core owner and executor identities to
these callbacks, implement tool/action approvals and safe adapters, check live
provider admission with PR-A, and verify a real bounded workflow in an isolated
sandbox. Do **not** expose these internal methods as unauthenticated API routes.
The cloud public shell remains static-only, and OCI admin access remains blocked
under issue #43.


## PR-C1: Tool Gateway control plane (NO live adapters)

`olivia/harness/tools.py` provides an opt-in gate for run-scoped tools.
Nothing registers automatically. With an empty adapter registry every attempt
is rejected; PR-C1 contains **no** real GitHub Actions, browser, MCP, shell or
SentinelX adapter and cannot invoke a model. It is not an authenticated HTTP
surface and is not deployed to Cloudflare.

Authorization is enforced in one SQLite `BEGIN IMMEDIATE` reservation:

1. A run must be claimed with a valid unexpired PR-B executor lease, its
   agent must remain approved, and cancellation must not be pending.
2. The tool must be explicitly registered as `ToolRule`, present in the
   agent's inherited approved `allowed_tools`, and the requested action
   must be in its exact action allowlist.
3. Read-only registrations accept only `get/list/inspect/search/head`. This
   is **not** a URL/egress sanitizer; a live browser adapter must still check
   URL schemes, redirects, DNS/IP destinations and private-network access.
4. Every write action requires separate authenticated owner action proof,
   bound to the exact **request ID, run ID, tool, action and SHA-256 of the
   prepared arguments**. A separate trusted sandbox verifier must attest the
   exact isolation environment and tool capability. The callbacks are
   injected only by privileged Core code and deny by default. Proof strings
   themselves are not security credentials unless a trusted verifier validates
   and consumes them; the gateway never fabricates an approval.
5. Maximum actions per run is 4 by default (absolute supported ceiling 16),
   with permanently consumed slots and a unique action ID. The action receipt
   is inserted **before** calling the registered adapter. On any error or
   unknown outcome, state becomes `uncertain`; a crash can leave `reserved`
   and that identity is still unreplayable. A remote `accepted` receipt is
   not mislabeled `completed`. Manual owner reconciliation requires an
   evidence SHA; no automatic resubmission.
6. Structured audit events contain event type, IDs and timestamps only, not
   raw prompts, secret tokens, approval proofs or tool payloads.

**PR-C2 work remaining:** inspect and adapt the existing coding and browser
GitHub Actions workers plus authenticated SentinelX/MCP bridges; verify
sandbox creation, job receipts, safe read-only URL rules, tool-specific
idempotency keys, write-scope and worktree isolation and cancellation
propagation with negative integration tests. In particular, an adapter
must prove the `args_sha256` matches the actual sealed arguments sent, not
merely trust a hash string from an LLM.

**PR-D still pending:** Core auth/approval API, mobile-first agent workbench,
ACP/MCP/AG-UI interfaces and a user-visible cost ledger. The public home is
still static/no-inference; do not claim a working multi-agent system until the
real adapter chain, provider billing and privileged OCI Core access pass their
acceptance gates.


## PR-C2a: sealed read-only GitHub status worker adapter

The existing `GitHubActionsCodingWorker.status(job_id)` and
`GitHubActionsBrowserWorker.status(job_id)` are usable through an opt-in
`GitHubStatusAdapter` using the PR-C1 `ToolGateway`. The adapter invokes
**status only**; it has no dispatch or artifact/result download path.

- The trusted Core control plane must create an immutable
  `PreparedStatusQuery(request_id,job_id,worker_kind,repo,args_sha256)` for
  one exact request, with a canonical digest binding all those fields.
- The gateway checks an approved agent, explicit `github.read` or
  `browser.read` capability, `get` action and valid run lease before
  invoking the adapter. The adapter checks query digest and the pinned
  worker repository again immediately before the read.
- Only sanitized workflow ID/status/conclusion/head SHA enter the audit
  digest. `None` (not observed) and a nonterminal run are marked
  `accepted`, never `completed`. Malformed status and network failures
  become `uncertain`, and the action ID is never replayed.
- The adapter is **not registered or called in the deployed Core**; all
  tests are synthetic fakes. Status queries may consume GitHub API quota
  when later enabled, but PR-C2a creates no GitHub jobs or Cloudflare AI
  requests and performs no background polling.

Write-capable coding dispatch, browser navigation/results, MCP/ACP,
SentinelX operations, real sandboxes and approval UI remain **not wired**.
They require tool-specific permission, private-repo and egress checks,
verified sandbox proof, owner review of mutations and no-effect replay
contracts before any production rollout.
