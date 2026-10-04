# 0liviA 🌠

**0liviA is a personal super-AI for one owner.** It is a persistent cloud intelligence for conversation, coding, repositories, research, tools, memory, autonomous work and realtime voice — not a generic SaaS workspace and not a wrapper around one model.

## Hard target

- cloud-only normal operation; the user's PC may be off;
- Oracle A1 ARM64: **2 OCPU / 12 GB RAM**;
- recurring infrastructure target: **USD 0**;
- GitHub is durable source of truth;
- Cloudflare is **deploy-only**, not the chat/voice/memory path;
- models/providers are replaceable;
- no reverse-engineered consumer-session APIs;
- no secrets in Git, prompts or durable memory.

## Architecture v1

`browser / mobile`
→ direct HTTPS/WSS
→ **small Python 0liviA Core**
→ SQLite WAL + FTS5
→ direct multiprovider router
→ on-demand workers (OpenCode / Playwright / voice)
→ GitHub MCP + Git worktrees.

Voice begins with **direct WSS**. Pipecat SmallWebRTC and StreamCore are benchmark challengers, not mandatory dependencies.

See:
- [Final architecture](docs/ARCHITECTURE.md)
- [Council synthesis](docs/COUNCIL_SYNTHESIS.md)
- [Benchmark gates](docs/BENCHMARKS.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Canonical super-order](SUPER_ORDER_END_TO_END.md)

## Repository map

`olivia/` — thin control-plane package  
`tests/` — core behavior and regression gates  
`docs/` — architecture, research, decisions and council evidence  
`web/` — browser client (next implementation slice)  
`voice/` — speech/transport adapters and A1 benchmarks (next slice)  
`deploy/` — Oracle systemd/TLS/backup material (after core gates)

## Current branch

Active integration branch: `arch/gpt-synthesis-v1`.

Implemented in the first synthesis slice:
- SQLite WAL/FTS5 state with DB outside repo by default;
- bounded message history;
- promoted memory with source/confidence and supersession;
- durable jobs/checkpoints/events;
- provider state/quota counters;
- OpenAI-compatible streaming router;
- exponential circuit breaker;
- first-token watchdog;
- failover only before first token;
- partial/cancel-safe agent persistence;
- unit tests and cloud CI definition.

Not yet claimed:
- Oracle A1 benchmark PASS;
- production voice;
- Argentine/Rioplatense voice quality;
- autonomous shell/coding sandbox;
- production deployment.

## Local development

    python -m venv .venv
    . .venv/bin/activate
    pip install -e '.[dev]'
    pytest

Runtime state defaults to `~/.local/share/0livia`. Never place conversation/memory SQLite files inside the repository.

## Build rule

Council artifacts are evidence, not merge targets. 0liviA absorbs mechanisms that survive its own interfaces, tests and target-host benchmarks.


## Zero-cost invariant

0liviA defaults to `OLIVIA_HARD_ZERO_COST=1`. A provider is routable only when its configuration is explicitly tagged `cost_mode=local` or `cost_mode=free_hard_cap`. Routes tagged `free_unverified` or `paid` are blocked before use. An advertised free tier is not considered safe if the upstream account can automatically bill overages.

If every verified-free route is exhausted, 0liviA becomes degraded/unavailable instead of spending money.
