# Research notes

Last updated: 2026-10-04

This file records externally verified facts that can affect architecture. Candidate status is not approval.

## Target infrastructure

Oracle Cloud Free Tier account inspection reported:

| Resource | Available |
|---|---:|
| Region | `sa-saopaulo-1` |
| Ampere A1 | 2 OCPU / 12 GB RAM free |
| E2.1.Micro | up to 2 × 1 OCPU / 1 GB |
| Block storage | 153 GB free of 200 GB |
| Object Storage | ~20 GiB free |
| Existing compute | 0 VMs |

Immediate physical A1 capacity was **not verifiable read-only**. Administrative quota is available.

## Voice transport

### GhostCall
Source: https://www.ghostcall.space/

Verified public claims:
- free browser voice calls;
- no signup / phone number;
- WebRTC peer-to-peer audio;
- audio advertised as direct between peers;
- 1:1 and small group calls.

Research did **not** find a documented public API, bot SDK, official source repository, or self-host contract for `ghostcall.space`. Treat programmatic agent participation as **UNVERIFIED** until proven by source or protocol inspection.

### LiveKit Agents
Source: https://github.com/livekit/agents

Official README states:
- open-source agent framework for realtime programmable participants;
- mix-and-match STT / LLM / TTS / realtime APIs;
- WebRTC clients;
- semantic turn detection;
- MCP support;
- built-in testing;
- entire LiveKit stack can be self-hosted.

This is a mature transport/framework candidate, but resource usage on the target 2-OCPU ARM VM still needs measurement.

### StreamCore
Source: https://github.com/streamcoreai/streamcore-server

Current project positions itself as a self-hostable Go realtime voice server with:
- WebRTC / WHIP;
- Opus media;
- streaming STT → LLM → TTS;
- barge-in;
- plugins/skills;
- built-in STUN/TURN;
- browser clients;
- provider-pluggable agent endpoint.

Potential advantage: small Go hot path. Maturity and ARM64 production behavior need benchmarking.

## Speech recognition / turn detection

### Moonshine Voice
Source: https://github.com/moonshine-ai/moonshine

Official README:
- real-time voice toolkit;
- optimized for live streaming;
- CPU/on-device operation;
- Python, JS/WASM, mobile, Linux, Windows and Raspberry Pi support;
- MIT code and most current model releases.

This is a strong CPU-first STT candidate for 0liviA.

### faster-whisper
Source: https://github.com/SYSTRAN/faster-whisper

Strong mature Whisper implementation. Community streaming layers exist, but the core project is primarily optimized transcription rather than a complete realtime turn-taking stack. Keep as accuracy/fallback baseline unless it wins actual latency tests.

### Silero VAD
Source: https://github.com/snakers4/silero-vad

Official README reports:
- ~2 MB model;
- processing of a 30+ ms chunk in under 1 ms on one CPU thread;
- ONNX support;
- MIT license.

Good candidate for cheap speech/no-speech gating. Do not confuse VAD with semantic end-of-turn detection.

## Text-to-speech

### MOSS-TTS-Nano
Source: https://github.com/OpenMOSS/MOSS-TTS-Nano

Official README states:
- ~100M parameters;
- multilingual;
- realtime streaming goal;
- CPU operation without GPU;
- ONNX CPU version;
- voice cloning path;
- Apache-2.0 project.

This is one of the most interesting active CPU-oriented TTS candidates. The upstream examples discuss smooth operation on more CPU than 0liviA's 2 OCPU in some scenarios, so **benchmark on A1 before adoption**.

### Kokoro
Source: https://github.com/hexgrad/kokoro

Official project:
- 82M parameters;
- Apache-licensed weights;
- lightweight;
- multiple languages;
- CPU-capable.

Quality/size are attractive, but public CPU first-audio measurements vary materially by hardware/wrapper. Target-machine benchmark required.

### Supertonic 3
Original project state: https://github.com/supertone-oss-archive/supertonic

The original official repo is now archived. It remains useful as a benchmark/reference but should not become a new core dependency without a maintained fork/successor and licensing review.

### Piper
Original repo: https://github.com/rhasspy/piper

The original repo is archived. Do not choose it as the default simply because it is lightweight; verify the maintained successor first.

### Fish Speech / OpenVoice / CosyVoice
Sources:
- https://github.com/fishaudio/fish-speech
- https://github.com/myshell-ai/OpenVoice
- https://github.com/QwenAudio/CosyVoice

High-quality candidates for richer voice/cloning, but likely heavier than the smallest CPU-first options. Measure hardware requirements before considering them on the always-on A1 node.

## Agent / harness / orchestration candidates

### OmO
Source: https://github.com/code-yeongyu/oh-my-openagent

Current README describes:
- multi-model execution;
- graph/DAG work;
- persistent git-backed memory;
- model-specific prompts;
- skills;
- restart/resume behavior.

Promising for aggressive multi-model work. Verify license and resource profile before core adoption.

### Tenet
Source: https://github.com/JeiKeiLim/tenet

Current README describes:
- long autonomous development loops;
- spec → DAG → execute → independent critics;
- durable project doctrine;
- crash recovery and retries;
- Claude Code / OpenCode / Codex support.

Interesting candidate for reliable long-run software tasks; not necessarily the end-user chat shell.

### HarnessRouter
Source: https://github.com/HarnessRouter/harnessrouter

Current README describes:
- browser console;
- persistent sessions/files/workspaces;
- pluggable harness backends;
- OpenAI Responses-compatible API;
- self-hosted Community Edition;
- Docker footprint around 4 GB disk;
- custom skills/MCP.

Strong candidate for a neutral harness control plane.

### Letta Code
Source: https://github.com/letta-ai/letta-code

Current README describes:
- stateful agents;
- memory/identity over time;
- agents can rewrite memory/skills/prompts;
- MemFS tracked through git;
- subagents;
- schedules and long-lived agents;
- browser/mobile access through Letta services and local/backend modes.

Strong memory/relearning reference. Determine what remains fully self-hosted/free before using cloud-dependent features.

### Monomind
Source: https://github.com/monoes/monomind

Current README describes:
- MCP server for codebase knowledge graph;
- persistent memory;
- multi-agent coordination;
- many agents/skills;
- SQLite-backed local state;
- Apache-2.0.

Possible memory/code-graph layer rather than primary UI.

### Agent Zero
Source: https://github.com/agent0ai/agent-zero

Broad browser-first agent platform with projects, tools, memory and computer/browser capabilities. Strong turnkey candidate; compare footprint and UX against more composable stacks.

### DeepSeek Harness
Source: https://github.com/deepseek-ai/deepseek-harness

Plugin-first coding harness with web UI. Keep in comparison matrix; verify preview/stability status before core adoption.

### free-claude-code
Source: https://github.com/Alishahryar1/free-claude-code

Potential model/provider routing layer rather than the agent itself. Its free-provider claims depend on upstream quotas that can change, so the architecture must never assume permanent free capacity from any one provider.

## GitHub / MCP

### GitHub MCP Server
Source: https://github.com/github/github-mcp-server

Official GitHub MCP implementation. Prefer official scoped GitHub access over ad-hoc credential exposure.

Third-party ToolCheck snapshot observed a caution score rather than an unconditional trust verdict; its report itself was stale for this repository, so use official source/security review and least privilege as primary evidence.

### mobile-mcp
Source: https://github.com/mobile-next/mobile-mcp

Potential mobile automation tool, but not required for 0liviA core. ToolCheck snapshot: caution 72/100 at time checked; review permissions and attack surface before any use.

## Required benchmarks before architecture freeze

Measure on the actual Oracle A1 VM:
- idle RAM/CPU per service;
- cold and warm start;
- STT partial transcript latency;
- end-of-turn latency;
- LLM first-token latency by provider;
- TTS first-audio latency;
- barge-in cancellation latency;
- sustained 30/60 minute voice stability;
- code task success rate / retries / wall time;
- memory recall precision and context growth;
- restart/recovery success;
- full stack RAM under concurrent voice + coding task.

Architecture should remain provisional until these numbers exist.

## Fresh official-source verification — 2026-10-04

- LiveKit Agents README: programmable realtime participants; interchangeable STT/LLM/TTS/realtime integrations; WebRTC clients; semantic turn detection; MCP; built-in tests; self-hostable LiveKit stack. Source: https://github.com/livekit/agents/blob/main/README.md. This is capability evidence, not an A1 resource benchmark.
- Moonshine Voice README: on-device operation, live streaming focus, Python/JS-WASM and Linux/Raspberry Pi support, MIT licensing with an explicit legacy non-English model exception. Source: https://github.com/moonshine-ai/moonshine/blob/main/README.md. Spanish ARM64 latency remains unmeasured here.
- Silero VAD README: approximately 2 MB JIT model; under 1 ms for a 30+ ms chunk on one CPU thread; ONNX path; MIT. The README's Python examples list x86-64/AVX requirements, so ARM64 adoption must use an actual ONNX/runtime test rather than extrapolation. Source: https://github.com/snakers4/silero-vad/blob/master/README.md.
- Kokoro README: Kokoro-82M; Apache-licensed weights; Spanish pipeline example (`lang_code='e'`). First-audio latency and memory on Oracle A1 remain unmeasured. Source: https://github.com/hexgrad/kokoro/blob/main/README.md.
- GitHub MCP Server README: explicit read-only mode, toolset/tool allow-lists, environment-based PAT configuration and minimum-permission guidance. Lockdown mode is best-effort filtering, not an authorization boundary. Source: https://github.com/github/github-mcp-server/blob/main/README.md.

No current source above proves that 0liviA can run realtime voice on 2 OCPU / 12 GB ARM64 at USD 0. That remains an explicit benchmark gate.
