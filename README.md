# 0liviA 🎲

**0liviA is a cloud-first personal AI for one owner and a self-hosted agentic AI workspace.** It combines conversation, coding, repositories, research, tools, durable memory, resumable jobs and live voice behind replaceable providers. Each installation owns its identity, runtime data and provider configuration; the public repository is not a shared hosted account.

0liviA is **zero-cost-first**: the runtime fails closed before unverified spending. That is an engineering policy, **not a guarantee** that third-party infrastructure or model providers will remain free forever.

## Product invariants

- normal operation does not depend on the owner's PC;
- recurring infrastructure target: **USD 0**;
- the product runtime cannot disable the hard-zero-cost guard through ENV;
- if no verified-free route is available, fail/degrade before spending;
- GitHub is the durable source of truth for code, architecture and checkpoints;
- runtime conversation/memory/project state belongs server-side;
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

Cloudflare may host a thin public shell or temporary bridge, but it is not the canonical chat/memory/voice backend. The current Worker bridge is disabled by default and remains deployment-gated; inference/read routes stay unavailable until identity and zero-cost/account guards are explicitly proven.

## Repository map

- `olivia/` — canonical Python control plane, router, memory/jobs, research contracts and voice contracts
- `olivia/voice/` — transport/speech contracts and benchmark scaffolding
- `web/` — current violet/blue/cyan browser product shell
- `cloudflare/` — temporary public bridge; not durable product state
- `deploy/` — canonical host deployment/runtime material; Oracle A1 is the roomy preferred target and the existing 1 GB E2 micro path is supported as a constrained fallback
- `.github/workflows/coding-agent.yml` — isolated burst coding worker
- `tests/` — behavioral, security and repository-hygiene gates
- `docs/` — architecture, decisions, research and current implementation state
- `docs/history/` — superseded council/build prompts preserved as evidence

## Implemented

- SQLite WAL/FTS5 sessions, projects, library, memories, jobs, checkpoints and events;
- authenticated canonical workspace API with Projects/Chats/Library/Memory durable server-side and IndexedDB used only as a browser cache/migration layer;
- provider health/quota state with circuit breaker, half-open recovery and redacted telemetry;
- native official ChatGPT-plan provider for eligible Plus/Pro owners: OAuth profile server-side only, Responses API `store:false`, automatic token refresh, and hard-zero-cost admission only after no-credit-overage is explicitly verified;
- one-time local Sign in with ChatGPT OAuth helper with PKCE/state/nonce, OIDC/JWKS validation, stable host ID, account model discovery and protected 0600 credential handoff to the cloud Core;
- pre-visible-output failover with cancellation/partial-answer safety;
- aiohttp browser/API gateway with first-run single-owner registration, email+password login, Secure/HttpOnly/SameSite cookies, login throttling, revocable remembered devices, bounded request bodies and one active turn per session;
- canonical SSRF-safe `/read` command with untrusted page content injected only as ephemeral model context;
- replaceable `/search` contract that is disabled by default and refuses unverified paid routes;
- bounded `/research` tool: one search plus safe reads of up to three results, injected only as ephemeral untrusted context;
- opt-in `/browse` GitHub Actions burst worker with JavaScript rendering, GET/HEAD-only navigation, reserved/private-network egress guards and bounded artifacts; `/inspect <job_id>` can explicitly analyze a completed render as ephemeral untrusted model context without persisting page text into chat/memory;
- violet/blue/cyan rail UI with Chats, Projects, Library, Memory, Config and Session surfaces, plus fullscreen Live Voice; responsive gates cover 360–430 px mobile layouts;
- public-shell runtime is event-driven: periodic 15-second/focus polling was removed, health probes are cached for five minutes, and retries occur only on explicit actions or connectivity recovery;
- isolated GitHub Actions coding jobs with `/code`, `/repair`, `/review`, durable job status and deterministic verification;
- review mode constrained to `AGENT_REVIEW.md`; product mutations fail the job;
- coding execution job has read-only repository permission; optional publication happens in a separate write-capable job after verification;
- authenticated direct-WSS voice endpoint plus browser/mobile WSS client, transport/pipeline contracts, PCM16 streaming, sequence/cancel/barge-in handling and benchmark recorder; the UI uses canonical WSS when a server speech backend is configured and keeps browser speech only as a provisional fallback; speech engines remain capability-gated until benchmarked;
- production bootstrap with immutable source SHA, pinned artifact SHA-256 verification and first-run owner registration;
- CI on Python 3.11 and 3.12 plus shell, JS and Worker syntax gates.

## Still gated

- recurring-$0 production-host certification and target-host benchmarks; the current `olivia-text-free` E2.1.Micro candidate is agent-reachable but still needs privileged SSH/preflight before deployment;
- production smoke of the isolated `/browse` worker and any future owner-approved click/write automation;
- a production `/search` provider only after its exact account/provider route is proven zero-cost;
- production STT/VAD/TTS selection and es-AR voice acceptance;
- a real owner Sign in with ChatGPT connection/smoke plus owner-side verification that app credit use cannot create overage;
- production entitlement for any retained DeepSeek NIM coding/model route;
- exact-SHA **canonical Core** deployment and production smoke; the last verified public inert-shell deployment is source `eee3f26885f13bc14073e3a7c1d7a1851e7a4883` (Worker `c582cf85-0b9e-4841-8392-f6169d1e4cf1`, deploy run `37401620923`), with inference/search disabled and the public composer explicitly offline until the Core exists;
- any Cloudflare inference/search path whose account-level zero-cost behavior is not independently verified.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
olivia
```

Runtime state defaults to `~/.local/share/0livia`. Never place conversation/memory SQLite files inside the repository.

## Canonical documents

- [Architecture](docs/ARCHITECTURE.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Current implementation checkpoint](docs/IMPLEMENTATION_PLAN.md)
- [Security audit reconciliation](docs/SECURITY_AUDIT.md)
- [Security operations](docs/SECURITY_OPERATIONS.md)
- [ChatGPT plan setup](docs/CHATGPT_PLAN.md)
- [Research evidence](docs/RESEARCH.md)
- [Benchmark gates](docs/BENCHMARKS.md)
- [Canonical build mandate](SUPER_ORDER_END_TO_END.md)
