# Architecture decisions

Use this file as an append-only ADR index. Do not turn candidate research into a decision without evidence.

## Status

No architecture has been frozen yet.

### ADR-0001 — Thin control plane with replaceable adapters
- Date: 2026-10-04
- Status: proposed
- Context: The repository had no executable implementation. The target is ARM64 Oracle Free Tier at 2 OCPU / 12 GB and recurring USD 0. A monolithic workspace plus multiple always-on speech/vector services risks resource pressure and vendor lock-in.
- Evidence: Official LiveKit Agents, Moonshine, Silero VAD, Kokoro and GitHub MCP documentation was checked on 2026-10-04; see `docs/council/manus-2026-10-04.md` and the fresh-source section in `docs/RESEARCH.md`. The local proof passes two tests for browser/session/SQLite/router/SSE, but does not prove realtime voice or Oracle performance.
- Decision: Keep the core as a small control plane with SQLite/file-backed durable state and explicit adapters for model, tool, browser and voice layers. Run heavyweight speech workers on demand. Use read-only tools by default and persist checkpoints in Git.
- Alternatives: LiveKit Agents as the whole product; Agent Zero/Letta/Tenet/OmO/HarnessRouter as the whole product; vector DB first; GhostCall as AI transport. These remain candidates or references, not accepted core dependencies.
- Resource impact: low idle baseline; one active coding/voice worker by default. Actual A1 measurements are required before freezing.
- Security impact: smaller default attack surface; explicit privilege boundaries; GitHub MCP read-only/toolset allow-list where possible. This ADR does not grant credentials.
- Rollback / replacement path: adapters are independent; replace SQLite with another store, the model provider, or LiveKit without changing session/checkpoint contracts. Revert the ADR and remove `prototype/` if benchmark gates fail.
- Verification: `python3 -m unittest discover -s prototype -p 'test_*.py' -v` and `python3 -m py_compile prototype/server.py` pass locally on 2026-10-04.

## Decision template

### ADR-XXXX — <title>
- Date:
- Status: proposed / accepted / superseded / rejected
- Context:
- Evidence:
- Decision:
- Alternatives:
- Resource impact:
- Security impact:
- Rollback / replacement path:
- Verification:
