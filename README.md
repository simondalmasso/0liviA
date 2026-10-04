# 0liviA 🌠

**0liviA is a cloud-first personal AI for one owner.** It combines conversation, coding, repositories, research, tools, durable memory, resumable jobs and live voice behind replaceable providers. It is not a generic SaaS workspace and not a wrapper around one model.

## Product invariants

- normal operation does not depend on the owner's PC;
- recurring infrastructure target: **USD 0**;
- if no verified-free route is available, fail/degrade before spending;
- GitHub is the durable source of truth for code, architecture and checkpoints;
- runtime conversation/memory state belongs server-side;
- providers, browser workers, coding workers and voice engines remain replaceable;
- no reverse-engineered consumer-session APIs;
- no secrets in Git, prompts or durable memory;
- default user-facing locale: **es-AR**.

## Canonical architecture

`browser / mobile`
→ direct HTTPS/WSS
→ **small Python 0liviA Core**
→ SQLite WAL + FTS5
→ direct provider router
→ isolated on-demand workers for coding, research/browser and voice
→ GitHub for durable engineering state.

Cloudflare may host a thin public shell or temporary bridge, but it is not the canonical chat/memory/voice backend. The current Worker bridge is explicitly deployment-gated and must fail closed when zero-cost entitlement is not proven.

## Repository map

- `olivia/` — canonical Python control plane, router, memory/jobs and voice contracts
- `olivia/voice/` — transport/speech contracts and benchmark scaffolding
- `web/` — current violet/blue/cyan browser product shell
- `cloudflare/` — temporary public bridge; not durable product state
- `deploy/` — Oracle A1 deployment/runtime material
- `.github/workflows/coding-agent.yml` — isolated burst coding worker
- `tests/` — behavioral, security and repository-hygiene gates
- `docs/` — architecture, decisions, research and current implementation state
- `docs/history/` — superseded council/build prompts preserved as evidence

## Implemented

- SQLite WAL/FTS5 sessions, messages, memories, jobs, checkpoints and events;
- provider health/quota state with circuit breaker, half-open recovery and redacted telemetry;
- pre-visible-output failover with cancellation/partial-answer safety;
- aiohttp browser/API gateway with bounded request bodies and auth;
- violet/blue/cyan rail UI with projects, library, memory, config and fullscreen Live Voice shell;
- read-only URL ingestion with SSRF/redirect/body limits in the temporary Worker bridge;
- isolated GitHub Actions coding jobs with deterministic verification;
- voice transport/pipeline contracts, sequence/cancel/barge-in tests and benchmark recorder;
- CI on Python 3.11 and 3.12 plus JS/Worker syntax gates.

## Still gated

- Oracle A1 production availability and target-host benchmarks;
- durable multi-device Projects/Library/Memory migration out of browser cache;
- production browser/research worker beyond read-only URL ingestion;
- production STT/VAD/TTS selection and es-AR voice acceptance;
- production entitlement for the preferred DeepSeek NIM route;
- any Cloudflare deployment until account-wide zero-cost behavior is independently verified.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

Runtime state defaults to `~/.local/share/0livia`. Never place conversation/memory SQLite files inside the repository.

## Canonical documents

- [Architecture](docs/ARCHITECTURE.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Current implementation checkpoint](docs/IMPLEMENTATION_PLAN.md)
- [Research evidence](docs/RESEARCH.md)
- [Benchmark gates](docs/BENCHMARKS.md)
- [Canonical build mandate](SUPER_ORDER_END_TO_END.md)
