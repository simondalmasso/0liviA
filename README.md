# 0liviA 🎲

**0liviA is a self-hosted agentic AI workspace for chat, coding agents, web research, durable memory, projects and live voice.** It is privacy-first, mobile-ready, multi-model and **zero-cost-first**: the runtime prefers local inference or provider routes with a verified hard-free boundary and fails closed instead of silently spending.

0liviA is public software, not a shared hosted account. Every installation owns its own identity, data, provider configuration, GitHub integration and optional infrastructure.

## Why 0liviA

- **Private AI workspace** — Projects/Chats/Library/Memory durable server-side in the canonical Core.
- **Agentic coding** — isolated `/code`, `/repair` and `/review` jobs with deterministic verification and no auto-merge.
- **Live web research** — safe `/read`, fail-closed `/search`, and bounded `/research` with untrusted web content kept ephemeral.
- **Multi-model routing** — replaceable OpenAI-compatible providers, quota admission, circuit breakers and pre-output failover.
- **Live Voice architecture** — browser/mobile voice shell, barge-in/cancel contracts and benchmark-gated speech backends.
- **Mobile-first UI** — Chats, Projects, Library, Memory, Config and Session in a responsive left rail; hardened for 360–430 px viewports.
- **Self-hosted identity** — first-run registration, email + password, secure cookies and revocable remembered devices.
- **No API keys in the UI** — provider credentials remain server-side.

## Public-product isolation

A public clone does **not** use the maintainer's Cloudflare account, model account, GitHub token, runtime database or private data.

Each installation:

1. creates its own runtime state outside the Git checkout;
2. creates its own gateway/setup secrets;
3. registers its own first owner;
4. configures its own provider routes server-side;
5. optionally configures its own coding repository/token;
6. stores conversations, projects, library and memory in its own SQLite database.

The transitional Cloudflare Worker is **disabled by default** for chat/read and is not the canonical backend. No public deployment should rely on another installation's Cloudflare bindings, Durable Objects, AI allocation or account credentials.

See [Self-hosting](docs/SELF_HOSTING.md), [Privacy](docs/PRIVACY.md) and [Security](SECURITY.md).

## About the "$0" claim

0liviA is **zero-cost-first**, not "free forever" and not a guarantee that third-party services will never charge.

The product can run with:

- local/self-hosted inference (`cost_mode=local`);
- provider routes whose upstream account has a verified hard-free boundary (`cost_mode=free_hard_cap`).

With `OLIVIA_HARD_ZERO_COST=1`, routes marked `free_unverified` or `paid` are rejected before use. If verified-free routes are exhausted, the expected behavior is degraded/unavailable — not hidden overage.

Cloud providers, domains, storage, network egress and model APIs have their own terms and can change. The "$0" posture is therefore an engineering policy and configuration gate, **not a guarantee** about external vendors.

## Canonical architecture

```text
browser / mobile
      │ HTTPS / WSS
      ▼
0liviA Core (Python)
      │
      ├─ SQLite WAL + FTS5
      ├─ provider router
      ├─ research adapters
      ├─ isolated coding worker
      └─ voice transport / speech adapters
```

GitHub is the durable source of truth for code, architecture and engineering checkpoints. Runtime user data belongs to the installation, not to this public repository.

Cloudflare may host a thin frontend or a temporary compatibility bridge, but it is not the canonical chat/memory/voice backend.

## Implemented

- SQLite WAL/FTS5 sessions, projects, library, memories, jobs, checkpoints and events;
- authenticated workspace API with Projects/Chats/Library/Memory durable server-side;
- IndexedDB used only as disposable browser cache/migration in canonical mode;
- first-run single-owner registration protected by a setup token;
- email/password login with Secure/HttpOnly/SameSite cookies;
- remembered devices with server-side random IDs and revocation;
- provider health/quota state, atomic admission and circuit-breaker recovery;
- failover before visible output plus explicit partial-answer behavior;
- centralized durable-store secret redaction;
- SSRF-safe `/read`;
- optional `/search` that stays disabled unless a verified zero-cost route is configured;
- bounded `/research` (search + safe reads, ephemeral untrusted context);
- coding jobs with `implement`, `repair`, `review` and durable status;
- review reports constrained to `AGENT_REVIEW.md`;
- responsive violet/blue/cyan UI with fullscreen Live Voice;
- `olivia/voice/` transport, cancellation and benchmark contracts;
- immutable production source refs and SHA-256-verified model/runtime artifacts;
- Python 3.11/3.12 CI plus JS, Worker and shell syntax gates.

## Quick start — development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
pytest -q
```

Use unique random values for `OLIVIA_GATEWAY_TOKEN` and `OLIVIA_REGISTRATION_TOKEN`. Do not reuse credentials from another installation.

Runtime state defaults to `~/.local/share/0livia`. Never commit runtime databases or secrets.

## Self-hosting

The reference deployment targets a small Linux host and includes an Oracle A1/ARM64 bootstrap because it is a useful zero-cost benchmark profile. It is a reference profile, not an account dependency.

Start here:

- [Self-hosting guide](docs/SELF_HOSTING.md)
- [Reference deployment](deploy/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security model](SECURITY.md)
- [Privacy model](docs/PRIVACY.md)

## Provider and coding configuration

Providers are instance configuration, not product identity. Configure only routes you control.

The coding worker is disabled by default. If enabled, set:

```env
OLIVIA_CODING_REPO=owner/your-repo
OLIVIA_CODING_WORKFLOW=coding-agent.yml
OLIVIA_CODING_BASE_REF=main
```

The public repository does not grant access to the maintainer's GitHub secrets or model-provider credentials.

## Current release gates

Before claiming a production installation is complete:

- benchmark the actual target host;
- verify the selected inference route and its billing boundary;
- verify voice STT/VAD/TTS quality and stability;
- run an exact-SHA deployment smoke;
- keep the transitional Cloudflare inference bridge disabled unless separately audited.

## Canonical documents

- [Architecture](docs/ARCHITECTURE.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Current implementation checkpoint](docs/IMPLEMENTATION_PLAN.md)
- [Security audit reconciliation](docs/SECURITY_AUDIT.md)
- [Research evidence](docs/RESEARCH.md)
- [Benchmark gates](docs/BENCHMARKS.md)
- [Canonical build mandate](SUPER_ORDER_END_TO_END.md)

---

**Search terms:** self-hosted AI assistant, agentic AI workspace, private AI, coding agent, web research agent, durable AI memory, multi-model AI router, live voice AI, mobile AI assistant, zero-cost AI infrastructure.
