# Implementation plan — active synthesis

Branch: `arch/gpt-synthesis-v1`

This file is the orchestration checkpoint. Architecture decisions remain in `docs/DECISIONS.md`.

## Integration rules

- Agents work in isolated branches/workspaces; no direct work on `main`.
- We absorb mechanisms, not whole sandboxes.
- Every imported component is reviewed against the current interfaces and retested here.
- No code may add local-PC filesystem/shell/background-agent access.
- Default user-facing locale is `es-AR`; provider language drift is a kernel/gateway concern.
- Cloudflare is not in the normal chat/voice/memory path.

## Active workers

### Manus — browser/API gateway
Status: **integrated** via PR #2 into `arch/gpt-synthesis-v1`; integrator then hardened SSE parsing, es-AR drift detection, and removed browser persistence.

Source branch: `impl/manus-gateway-v1`

Scope:
- aiohttp gateway + minimal browser client;
- explicit cancel endpoint / disconnect cleanup;
- one active turn per session;
- static UI served safely;
- non-persistent bearer token;
- pluggable es-AR first-segment guard;
- gateway tests.

### DeepSeek — router reliability
Status: **integrated and CI-verified** in `arch/gpt-synthesis-v1`.

Integrated:
- persistent per-provider health state;
- CLOSED → OPEN → HALF_OPEN recovery with probe lease;
- quota-aware admission and day rollover;
- TTFT watchdog and optional stream-idle watchdog;
- cancellation without failover;
- failover only before first visible segment;
- no duplicate provider attempt per turn;
- redacted telemetry/events and attempt metrics;
- dedicated reliability/config/health regression tests.

Verification:
- GitHub Actions run `37179846028`: Python 3.11 PASS + Python 3.12 PASS.
- Full suite: **45 passed**.

### MiniMax — voice contracts
Workspace/branch: `impl/minimax-voice-contracts-v1` if write access exists.

Scope:
- direct WSS contract first;
- pluggable VAD/EOT/STT/TTS interfaces;
- turn_id/sequence/cancel/late-frame rejection;
- benchmark harness;
- es-AR voice acceptance metadata;
- no heavy media framework dependency.

## Integrator checklist

1. Review each worker branch/patch.
2. Port only compatible changes into `arch/gpt-synthesis-v1`.
3. Run compile + tests after each integration.
4. Keep runtime state outside Git.
5. Keep provider secrets env-only.
6. Do not deploy until core + gateway + router gates pass.
7. Voice remains benchmark-gated on actual Oracle A1.


## Current verification

- GitHub Actions `core-ci`: Python 3.11 PASS + Python 3.12 PASS.
- Latest verified suite at this checkpoint: **45 passed**.
- Browser/API gateway is integrated.
- DeepSeek router reliability is integrated and CI-verified; MiniMax voice contracts remain isolated until reviewed.
