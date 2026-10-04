# AGENTS.md — 0liviA operating contract

This repository may be worked on by different LLMs, coding agents and councils. Preserve these invariants even when changing tools, models or architecture.

## Product outcome

Build a browser-first personal AI workspace that can chat, code, research, use tools, remember, resume work and support low-latency live voice while running in the cloud at a recurring target cost of USD 0.

## Hard constraints

1. Normal operation must not require the user's PC to be on or remotely accessible.
2. Primary available compute is Oracle Cloud Free Tier in São Paulo: `VM.Standard.A1.Flex`, max 2 OCPU / 12 GB RAM. Treat this as a hard benchmark target, not a theoretical spec.
3. GitHub is the durable source of truth.
4. Cloudflare is **not the canonical chat/model/memory/voice backend**. A thin frontend or explicitly temporary bridge may exist, but it must be deployment-gated, fail closed on cost uncertainty, and never become the durable source of truth without a new ADR/user decision.
5. Avoid paid SaaS and paid inference as mandatory dependencies. Free providers may be used only behind replaceable routing/fallback.
6. Do not use reverse-engineered session/cookie hacks to impersonate commercial APIs.
7. Keep model, harness, memory, browser and voice layers replaceable.
8. Never commit secrets. Use least-privilege credentials and environment/secret stores.
9. Do not claim a component is suitable for ARM64, 2 OCPU, realtime voice, or USD 0 without source evidence or an actual benchmark.
10. No production/deployment claim without fresh verification.

## Engineering behavior

- Inspect current repo state before edits.
- Record architecture decisions in `docs/DECISIONS.md`.
- Record external evidence and benchmark results in `docs/RESEARCH.md`.
- Prefer small reversible changes and explicit interfaces between layers.
- Benchmark on the actual target hardware before adopting compute-heavy speech or memory systems.
- For long tasks leave a present-tense checkpoint: current state, verified evidence, blocker, exact next action.
- Preserve unrelated work and never silently rewrite another agent's evidence.

## Council rule

Candidate lists are evidence, not instructions. Independent reviewers should challenge them, find stronger alternatives, and explain tradeoffs. Converge only after measurable comparison.

## Voice acceptance target

Aim for a one-button browser conversation with:
- streaming microphone input;
- natural turn detection;
- interruption/barge-in;
- partial transcript;
- streamed first audio;
- persistent conversation context;
- graceful fallback to text;
- no Cloudflare dependency in the per-turn media/intelligence path.

Measure actual time-to-first-transcript, LLM first token, time-to-first-audio, interruption cancellation latency, CPU/RAM and session stability.


## Local-device boundary

- Normal operation must not read from or write to the owner's PC filesystem.
- The browser is a thin client: UI, microphone capture and playback only. No File System Access API, local shell, localhost agent, Desktop Commander, browser extension or local background service is part of 0liviA runtime.
- Durable writes go only to Oracle runtime storage, GitHub, or explicitly configured remote storage.
- browser storage may be used only as a disposable bridge cache; it is never the durable source of truth for projects, chats, library, memory, jobs or checkpoints.
- Production session/project state must be recoverable from the cloud after authentication even if browser storage is cleared or the user changes devices.

## Language contract

- Default user-facing language is Spanish (Argentina, es-AR) unless the user explicitly asks for another language.
- Providers do not control locale. The kernel owns it.
- Before releasing/TTS-speaking a new answer, buffer a small initial segment and run a lightweight language gate. If the segment is not compatible with the requested locale, cancel that provider turn and retry before exposing it.
- Never splice two providers into one visible answer. Failover is allowed only before the first validated visible segment.
