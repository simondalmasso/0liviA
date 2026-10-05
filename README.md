# 0liviA 🎲

**Self-hosted agentic AI workspace for chat, coding, web research, long-term memory, projects and voice.**  
Provider-agnostic, privacy-first and designed to run with **verified zero-cost routes** without silently falling back to paid usage.

**Keywords:** self-hosted AI assistant · agentic AI · AI coding agent · web research agent · private AI workspace · long-term memory · voice assistant · LLM router · local AI · zero-cost AI

## Why 0liviA

0liviA is built as a product you run for yourself or your own team infrastructure — not as a hosted account tied to the maintainer.

- **Your deployment, your identity, your providers.** First-run registration creates the owner of that installation.
- **No maintainer credentials or shared cloud account.** Provider keys and cloud accounts are supplied by the deployer and remain server-side.
- **Agentic by design.** Chat, code, repair, review, URL reading, research, jobs and durable workspace state share one control plane.
- **Fail closed on cost.** Unverified or paid routes are blocked when hard-zero-cost mode is enabled.
- **Replaceable models.** The product is not coupled to one model or one provider.
- **Mobile-first shell.** Chats, Projects, Library, Memory, Config and Session live in a compact responsive rail.

## Core capabilities

- durable **Chats / Projects / Library / Memory** backed by SQLite WAL + FTS5;
- authenticated single-owner installation with **email + password**, secure cookies and revocable remembered devices;
- provider router with health state, quota reservation, circuit breaker and pre-visible-output failover;
- **/read** for SSRF-safe public URL reading with ephemeral untrusted context;
- **/search** adapter contract that stays disabled until a verified-safe route is configured;
- **/research** for bounded search + safe source reads;
- isolated coding jobs with **/code**, **/repair**, **/review** and durable **/job** status;
- senior review mode constrained to a report artifact instead of mutating product code;
- fullscreen Live Voice UI and voice transport/pipeline contracts;
- responsive UI hardened for 360–430 px mobile viewports;
- first-run protected setup link for production installs;
- transitional Cloudflare inference/read bridge **disabled by default**.

## Ownership and privacy model

Every installation is isolated.

- The repository ships with **no maintainer API keys, Cloudflare account IDs, personal email, provider tokens or shared credentials**.
- The canonical Core does not require the maintainer's infrastructure.
- Runtime data stays in the deployment's SQLite database.
- External model/search providers are contacted only when the deployer explicitly configures them.
- Secrets are referenced by environment-variable name, redacted at persistence boundaries and never requested in the browser UI.
- The public Cloudflare bridge is not the canonical backend and its inference/read routes are disabled by default.

See [SECURITY.md](SECURITY.md) and [Self-hosting](docs/SELF_HOSTING.md).

## $0 mode — precise claim

0liviA is **zero-cost capable**, not a promise that every third-party service is free forever.

With `OLIVIA_HARD_ZERO_COST=1` (the default):

- `local` routes are allowed;
- `free_hard_cap` routes are allowed only when the deployer has verified that the upstream cannot bill beyond its free boundary;
- `free_unverified` routes are blocked;
- `paid` routes are blocked;
- when all verified-free routes are unavailable or exhausted, 0liviA degrades/fails instead of silently spending money.

That is the product claim: **no silent paid fallback**. Provider pricing, quotas and account entitlements remain the responsibility of each deployment.

## Architecture

```text
browser / mobile
      ↓ HTTPS / WSS
0liviA Python Core
      ↓
SQLite WAL + FTS5
      ↓
replaceable model / search / coding / voice adapters
      ↓
your own local runtime or your own provider accounts
```

GitHub is the source of truth for code and engineering checkpoints. Runtime conversations, memory and projects are server-side state, not browser-only state.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

Copy `.env.example`, configure only the providers you actually want, and keep `OLIVIA_HARD_ZERO_COST=1` unless you deliberately choose otherwise.

For a real deployment, use the protected first-run registration flow documented in [docs/SELF_HOSTING.md](docs/SELF_HOSTING.md).

## Product status

The canonical Python Core, durable workspace, auth, safe web read/research contracts, coding jobs, mobile shell and CI gates are implemented.

Still gated before a universal production claim:

- verified target-host capacity and benchmarks;
- production-grade JS browser automation;
- accepted production STT/VAD/TTS path;
- explicit entitlement for any metered external model/search route;
- exact-SHA deployment + smoke on the target environment.

## Repository map

- `olivia/` — control plane, auth, router, memory, research, jobs
- `olivia/voice/` — voice contracts, adapters and benchmarks
- `web/` — responsive product shell
- `deploy/` — self-host deployment material
- `cloudflare/` — disabled-by-default transitional bridge
- `.github/workflows/coding-agent.yml` — isolated burst coding worker
- `tests/` — behavior, security, mobile and repository-hygiene gates
- `docs/` — architecture, research, decisions and implementation state

## Documentation

- [Self-hosting](docs/SELF_HOSTING.md)
- [Security](SECURITY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Implementation checkpoint](docs/IMPLEMENTATION_PLAN.md)
- [Security audit reconciliation](docs/SECURITY_AUDIT.md)
- [Research evidence](docs/RESEARCH.md)
- [Benchmark gates](docs/BENCHMARKS.md)

---

**Suggested GitHub About description:**  
`Self-hosted agentic AI workspace for chat, coding, web research, memory, projects and voice — provider-agnostic, privacy-first and zero-cost capable.`
