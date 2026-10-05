# AGENTS.md — 0liviA engineering contract

This public repository may be worked on by different LLMs, coding agents and human maintainers. Preserve these invariants even when changing models, providers or deployment targets.

## Product outcome

Build a browser-first, self-hosted agentic AI workspace that can chat, code, research, use tools, remember, resume work and support low-latency live voice.

Each installation is isolated and owns its own identity, runtime data, provider configuration and optional integrations.

## Hard constraints

1. Normal operation must not require the operator's desktop/laptop to stay online.
2. The reference low-cost benchmark profile is a small Linux host comparable to Oracle A1 ARM64, 2 OCPU / 12 GB RAM. It is a benchmark target, not a mandatory vendor/account dependency.
3. Git is the durable source of truth for source code, architecture, tests and engineering checkpoints.
4. Runtime user data belongs to the installation and must remain outside the Git checkout.
5. Cloudflare is **not the canonical chat/model/memory/voice backend**. The transitional bridge is disabled by default and may only be enabled after explicit identity/cost review.
6. Avoid paid SaaS and paid inference as mandatory dependencies.
7. Do not use reverse-engineered consumer-session/cookie hacks as APIs.
8. Keep model, router, harness, memory, browser and voice layers replaceable.
9. Never commit secrets, runtime databases, setup tokens, cookies or private user content.
10. Never claim USD 0, realtime voice quality, hardware fit or production readiness without verifiable evidence.

## Public-product isolation

- Never hardcode a maintainer's email, provider account, Cloudflare account, API token or private deployment URL.
- Provider credentials are per installation and server-side only.
- The coding worker is disabled by default and must target a repository/token configured by the operator.
- Public forks do not inherit repository Actions secrets.
- A clone must not silently call a maintainer-controlled backend.
- Any optional cloud adapter must fail closed if its identity/cost boundary is unverified.

## Engineering behavior

- Inspect current repo state before edits.
- Record material architecture decisions in `docs/DECISIONS.md`.
- Record source-backed external evidence in `docs/RESEARCH.md`.
- Prefer small reversible changes and explicit interfaces.
- Test touched behavior and run repository gates.
- Preserve unrelated work and historical evidence.
- Leave a present-tense checkpoint after long tasks.

## Voice acceptance target

Aim for a one-button browser conversation with:
- streaming microphone input;
- natural turn detection;
- interruption/barge-in;
- partial transcript;
- streamed first audio;
- shared text/voice session context;
- graceful fallback to text;
- no mandatory Cloudflare dependency in the per-turn intelligence/media path.

Benchmark time-to-first-transcript, LLM first token, time-to-first-audio, cancellation latency, CPU/RAM and long-session stability.

## Local-device boundary

- Normal operation must not read/write the operator's local filesystem.
- The browser is a thin client: UI, microphone capture and playback only.
- No local shell, localhost agent, browser extension or background desktop service is part of the default runtime.
- Durable writes go to the configured self-hosted runtime, Git, or explicitly configured remote storage.
- browser storage may be used only as a disposable bridge cache; it is never the durable source of truth for projects, chats, library, memory, jobs or checkpoints.
- Canonical session/project state must be recoverable after browser storage is cleared or the user changes devices.

## Language contract

- The current default user-facing locale is Spanish (Argentina, es-AR); deployments may make locale configurable without handing policy control to the model provider.
- Providers do not control locale. The kernel owns it.
- Never splice two providers into one visible answer.
- Failover is allowed only before the first validated visible segment.
