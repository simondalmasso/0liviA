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
