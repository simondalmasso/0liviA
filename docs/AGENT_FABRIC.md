# Agent Fabric — PR-A: model admission and budgets

Status: **opt-in harness primitives only; NOT enabled on canonical chat or Cloudflare demo**.

AUD master plan: [issue #97](https://github.com/simondalmasso/0liviA/issues/97#issuecomment-6099758456). The existing `ProviderPool`, SQLite Core, coding worker and browser worker remain canonical; PR-A does **not** replace them or enable any provider.

## Trust and data flow

1. Operator first verifies the **actual account** entitlement and records an attestation in a **private, trusted, server-side** source; account ID is a nonsecret opaque label. An issue link is a review pointer, not independent proof of billing safety. This PR does **not** mint attestations automatically, verify billing accounts, run inference canaries, or enable any cloud provider.
2. `ModelRegistry` has an empty attestation set by default. `admit(provider,capability,max_input,max_output,parent_budget)` rejects unknown models, forbidden Nemotron routes, unverified cost/production rights, expired attestations, local endpoints that are not loopback, unsupported capabilities, missing quotas, and exceeded token budgets. Only `local` and `free_hard_cap` are eligible for **this new agent fabric** (existing Core `plan_included` route remains unchanged pending independent audit).
3. `BudgetGuard` uses `BEGIN IMMEDIATE` reservations in the existing SQLite database file with separate table names. It atomically increments a parent-to-root chain and per-account/per-model/day counters **before** any provider call. A duplicate request ID is never returned for execution, even after restart, timeout or uncertain stream outcome; no refund on uncertainty. Scope declarations cannot be enlarged or reparented. Existing `ProviderHealth` quota/breakers still apply when later connected via adapter.
4. `guarded_stream` demonstrates one *single* provider call with admission and reservation, and no automatic retries. The adapter for the existing router/fallback policy is PR-C; **do not call `ProviderPool.stream` without the eventual registry gateway from Agent Fabric**. Do not deploy until tests/audit prove complete gate coverage.

These are **defense-in-depth software budgets**, not account-side spending caps. Estimated input tokens and declared output limits do not bound a provider's invoice; hard USD 0 requires separate, current, external no-overage evidence and usage-rights confirmation. Never claim a promotional credit is recurring-free. Never use Nemotron.

## PR-B boundaries

Durable AgentSpec/AgentRun, parent-child permission intersection, approval and cancellation, idempotency and explicit uncertain state, checkpoints/receipts, and SQLite lease orchestration. All new agents begin as **draft** and cannot invoke any model/tool without explicit owner-approved policy. No default auto-spawn or automatic retry.
