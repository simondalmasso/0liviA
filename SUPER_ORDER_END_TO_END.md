# SUPER ORDER — 0liviA 🌠
## Independent Council + End-to-End Build Order

Repository: https://github.com/simondalmasso/0liviA

You are one independent senior architecture + engineering council member. You are **not** being asked to validate somebody else's design. Treat the repository as the only durable shared state, inspect it from zero, and improve it.

Your job is to discover and build the strongest possible version of **0liviA**, even if that means rejecting every candidate currently mentioned in the repo and replacing the architecture with something better.

Do not ask the user to copy/paste intermediate work. If your environment has GitHub write access, work directly in the repository. If you need isolation, create your own branch named `council/<your-model>`, commit your work, and leave it reviewable. Do not overwrite another council member's evidence.

## Mission

Build a cloud-only personal AI workspace that can remain available with the user's PC turned off and can:

- chat naturally and quickly;
- write, inspect, test, repair and ship software;
- research the live web;
- use GitHub and MCP/tools safely;
- maintain durable memory and project context;
- resume after crashes, restarts and context compaction;
- run long autonomous engineering/research tasks without loop-slop;
- use more than one model/provider and fail over cleanly;
- learn durable user/project patterns without corrupting source-of-truth state;
- expose a browser UI;
- provide one-button **live voice conversation** with low latency, streamed speech, partial transcript, natural turn-taking and barge-in/interruption;
- deploy user applications to Cloudflare only when explicitly requested;
- target recurring cost of **USD 0**.

The desired behavior is: fast, opportunistic and hard to stall; persistent across long work; experimentally curious; clever with tools; but measured, falsifiable and stable under pressure.

Do not imitate personalities. Translate those qualities into engineering properties, routing rules, recovery behavior, benchmarks and tests.

## Hard facts / constraints

Current always-on compute available:

- Oracle Cloud Free Tier
- region: `sa-saopaulo-1`
- `VM.Standard.A1.Flex`
- **2 OCPU / 12 GB RAM**
- ~153 GB free block storage
- ~20 GiB free Object Storage
- 0 compute instances currently running

Normal operation must be cloud-only. The user's PC may be completely off.

GitHub is the durable source of truth for code, architecture, agent instructions, decisions and checkpoints.

**Cloudflare is not part of the normal chat/voice/memory/runtime path.**
Use Cloudflare only for deploying user applications when requested. A normal 0liviA message/voice turn must not require a Worker/Tunnel/Durable Object/proxy call.

No mandatory paid API/SaaS.

No reverse-engineered cookie/session hacks that pretend commercial web sessions are APIs.

No secrets in git, prompts or long-term memory.

Everything important should be replaceable: model, router, harness, memory, browser/tool layer, speech components and UI.

## Do not inherit the candidate list

The repo contains candidate projects and research. Treat them only as leads.

You must independently search current 2026 sources and answer:

1. Is there a materially better agent/harness/orchestrator than the candidates already listed?
2. Is there a better multi-model router or free-provider abstraction?
3. What is the strongest durable memory/context/relearning design that fits this hardware?
4. What stack gives the best long-horizon coding autonomy with verification, retry, recovery and resume?
5. What browser/MCP/GitHub integration is safest and least brittle?
6. What is the best live-voice architecture that can plausibly feel close to modern realtime assistants at USD 0?
7. Can GhostCall be used programmatically for an AI participant, or is it only useful as a UX/WebRTC reference?
8. Which components are too heavy, immature, archived, unmaintained, GPU-bound, x86-only, license-risky or operationally fragile for 2 OCPU / 12 GB ARM64?
9. Can a stronger architecture be built by combining fewer components instead of stacking frameworks?
10. What should run permanently on Oracle, and what should be burst/ephemeral elsewhere?

Search beyond everything already named. If you find something better, **use it**.

## Voice requirement

The user wants to touch one button and immediately talk to 0liviA from a browser, with the feel of a fast live conversation.

Required behaviors:

- microphone starts quickly;
- streaming input;
- low-latency VAD / end-of-turn;
- partial transcript;
- response generation begins before the entire answer is complete;
- streamed first audio;
- natural cadence;
- interruption/barge-in;
- stop/cancel propagates through LLM and TTS;
- text and voice share the same conversation memory/context;
- voice can fall back to text without losing the session;
- no Cloudflare dependency per turn;
- no user-PC compute dependency.

Investigate WebRTC, direct browser transports, LiveKit/Pipecat/StreamCore-class frameworks, GhostCall, current STT/VAD/end-of-turn/TTS models, and any better 2026 alternatives you find.

Do not pick a speech component from reputation. Benchmark or provide a falsifiable benchmark plan for:
- time-to-first-transcript;
- endpoint/turn-detection latency;
- LLM first-token latency;
- time-to-first-audio;
- barge-in cancellation latency;
- sustained 30–60 minute stability;
- CPU/RAM;
- Spanish quality;
- voice warmth/naturalness.

## Engineering standard

Before architecture freeze:

- inspect the repo;
- verify current official sources;
- inspect licenses;
- verify ARM64 support;
- calculate/measure idle RAM and CPU;
- reject redundant layers;
- benchmark the actual target host where possible;
- define failure/fallback behavior;
- define security boundaries;
- define backup/recovery;
- define observability;
- define migration/replacement paths.

For coding work:

- inspect before edit;
- protect unrelated work;
- use small reversible commits;
- test the touched behavior;
- run repo gates;
- verify real browser/runtime behavior when relevant;
- commit and push;
- do not claim PASS from stale evidence;
- leave a current checkpoint.

## Autonomy

Do not stop at a recommendation if you can safely prove it.

If your research identifies a clearly stronger foundation:
- scaffold it;
- integrate the smallest end-to-end slice;
- add tests/benchmarks;
- document the evidence;
- commit the result.

Prefer a thin vertical proof over a huge speculative implementation.

A useful first vertical slice would prove:
`browser → session → agent/model → durable context → tool/repo action → streamed response`

A useful voice slice would prove:
`browser mic → realtime transport → VAD/STT → same session/context → LLM → streaming TTS → browser audio → barge-in`

But you are free to design a better proof.

## Council output

Write your independent report to:

`docs/council/<your-model>.md`

Include:

- strongest architecture you found;
- why;
- runner-up;
- better discoveries beyond the repo;
- rejected candidates and exact reason;
- $0 assumptions and which could expire;
- estimated always-on resource envelope;
- security model;
- memory/context strategy;
- model-routing strategy;
- live-voice design;
- benchmark matrix;
- smallest implementation proving the architecture;
- what you actually changed;
- fresh verification evidence;
- unresolved risks.

If you change architecture materially, propose or append an ADR in `docs/DECISIONS.md`.

Update `docs/RESEARCH.md` only with source-backed facts.

Do not erase other council members' reports.

## Stop condition

You are done only when the repository is objectively more useful than when you opened it.

A pure opinion essay is insufficient if your environment allows implementation.

Do not deploy paid infrastructure.
Do not create costs.
Do not expose secrets.
Do not fake completion.
Do not wait for another model's approval.
Find the best design you can, falsify it, improve it, and leave the evidence in GitHub.
