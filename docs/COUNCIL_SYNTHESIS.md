# Council synthesis — 2026-10-04

This document captures what was worth keeping from the independent builds. It is not a popularity vote.

## Strongest evidence

**Arena Agent Mode**
- strongest minimal Python control-plane proof;
- 18/18 tests, measured low RSS, SQLite/FTS, checkpoint/resume, safe tools;
- strongest argument for direct WSS and for keeping an SFU out of v1.

**DeepSeek v4.1 Flash Max**
- strongest router/operations work: real failover behavior, circuit breaker, half-open recovery, first-token watchdog, cancellation and observability;
- its Next/Postgres implementation is not adopted as the permanent core.

**MiMo V2.6 Pro**
- strongest “Kernel + Media Plane” simplification;
- 16/16 tests and very small core;
- surfaced Pocket TTS as a serious CPU/streaming Spanish candidate and made StreamCore a credible challenger.

**MiniMax M3**
- strongest WebRTC alternative: Pipecat SmallWebRTC rather than a full SFU stack;
- reinforced Moonshine + Pocket TTS as a voice path worth measuring.

**Mistral**
- coherent StreamCore/Moonshine/Silero/Kokoro integration;
- useful deployment decomposition, but seven always-on services are too much for v1.

**Sakana**
- useful independent convergence on a lightweight control plane + StreamCore;
- nanobot is kept only as a benchmark/reference, not the product shell.

**Claude/Sonnet**
- useful typed-memory, tool and UI vertical slice;
- Postgres and browser Web Speech are not the final server architecture.

**Kimi K2.7 Code**
- useful negative result: framework/type churn pushed it toward direct provider HTTP and plain JSON schema tools, reinforcing a small custom core.

**Manus**
- validated the thin-control-plane direction and produced the only real external PR;
- Codex review found P2 issues (runtime DB inside repo, write-only memory, unbounded history reads, long SQLite lock, concurrent stream submission, misleading health provider, stream disconnect handling, query parsing), so the PR is evidence, not a merge target.

## Astra calibration

GPT-6 Astra received only the compressed council evidence and was explicitly told not to audit/search. Its recommendation aligned with:
- minimal Python kernel;
- SQLite WAL+FTS5 + Git/Markdown;
- direct multiprovider router;
- OpenCode/worktree coding worker;
- direct WSS first;
- cautious local/fallback speech components;
- explicit exclusion of Next/Postgres, nanobot, LiveKit, GhostCall and Cloudflare from the hot path.

## Synthesis rule

Absorb proven mechanisms, not entire sandboxes. No council artifact is merged wholesale. Each adopted mechanism must fit the final interfaces and pass 0liviA's own tests.
