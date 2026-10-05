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

## Local frontier-quality model challengers

### Meta Muse Glimmer
Source: https://dev.meta.ai/models/muse-glimmer

Official Meta documentation (checked 2026-10-04):
- 30B dense multimodal model, text+image input and text output;
- 128K default context, trained across 100+ languages;
- Apache-2.0 weights;
- designed for always-on local agents, tool use, long tasks and failure recovery;
- supported through llama.cpp, vLLM, SGLang and ExecuTorch;
- official published benchmarks include SWE-Bench Verified 76.0, SWE-Bench Pro 51.2, TerminalBench 2.1 51.7 and MCP Atlas 75.5.

Fit for 0liviA:
- **strong local-quality challenger** for a future GPU node / capable owner-supplied host;
- can sit behind the existing OpenAI-compatible provider abstraction, so no core rewrite is required;
- no API key is required after downloading the open weights;
- not suitable as the default Oracle A1 2 OCPU / 12 GB model: the official Q4_K_M text checkpoint is ~16.8 GB and Meta reports ~19 GiB VRAM for text + vision projector + full 128K context;
- do not replace a frontier hosted route with a tiny local model merely to claim availability. Quality floor remains a release gate.

Decision: **benchmark candidate, not A1 default**. If a >=24 GB GPU node or equivalent free/self-owned hardware becomes available, evaluate Muse Glimmer before smaller local fallbacks.

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

## Training / publication workflow patterns

### Homebrew AI
Source: https://github.com/empero-org/homebrew-ai

Useful patterns retained:
- resumable long-running jobs with durable project state;
- explicit confirmation before paid compute, software installation, data upload or publication;
- hardware-aware planning before work starts;
- evaluate the trained artifact before promotion;
- credentials remain outside the chat transcript;
- portable trace/data format for reproducible fine-tuning/evaluation.

Fit for 0liviA:
- **pattern source, not a runtime dependency**;
- could inform a future optional fine-tuning/evaluation worker;
- current training paths often need a capable local/rented GPU, so it does not satisfy the normal USD 0 runtime constraint by itself;
- no reason to add its dependency surface to the always-on Core.

### dev-to-publish
Source: https://github.com/amirmushichge/dev-to-publish

Useful patterns retained:
- artifact → preview → human approval → publish/queue → durable receipt;
- channel-specific packaging from one verified source;
- dry-run first;
- publishing adapter separated from editorial/creative agent logic;
- no assumption of access to unrelated chats/accounts.

Fit for 0liviA:
- **optional future publishing skill/worker**, not core;
- useful if 0liviA later publishes project demos/posts;
- requires an external delivery account/API such as Buffer, so it is not a zero-cost core dependency;
- the review/approval/receipt pattern is worth reusing for any irreversible external action.

## Intern Discovery / InkStone GPU burst lane — 2026-10-04

Public platform evidence:
- Scientific Computing dev machines expose CPU, Ascend 910B and Nvidia A100 resources, including **NvidiaA100-1-80G**.
- Each dev-machine or inference-service run is time-bounded; a single run can be configured for at most **7×24 hours** and consumes platform compute points while running.
- The platform exposes a dedicated **Inference Service** surface that returns a request URL, call credential and call statistics for running services.
- Inference Service currently advertises a **Hugging Face - text-generation** model format. Model source can be a folder in the user's cloud disk or a small local upload package.
- The user's visible account snapshot showed **5,000 compute points** and **30 GB cloud disk**. Public docs confirm the cloud disk can request expansion.

Muse Glimmer fit:
- Meta Muse Glimmer is a 30B dense multimodal agentic model, Apache-2.0, with a 128K default context and published local serving paths.
- Official BF16 weights are about **59.6 GB**. They fit in A100 80 GB VRAM but do **not** fit the current 30 GB persistent cloud disk.
- Meta's official GGUF Q4_K_M is about **16.8 GB** (+ vision projector if needed) and fits the current disk, but the documented InkStone Inference Service runtime is Hugging Face text-generation rather than llama.cpp/GGUF.
- A third-party Red Hat INT4 safetensors build is about **22.2 GB**, which fits the current cloud disk and is structurally closer to vLLM/Transformers serving. It is a challenger only; quality/runtime compatibility must be benchmarked before production use.

Recommended 0liviA role:
- Treat Intern Discovery as an **ephemeral frontier accelerator**, never the only brain.
- Keep the canonical Core/model router elsewhere. When an Intern service is up and explicitly marked `free_hard_cap`, 0liviA may route agentic/coding-heavy turns to Muse; when it stops or points are exhausted, fail over to another verified-free route.
- Do not persist the platform call credential in browser storage, chat, Git, logs or Library/Memory. Store it only server-side.
- Do not auto-start/extend point-consuming GPU sessions from 0liviA until the exact point/hour rate and account policy are known and explicitly approved.
- Prefer the platform Inference Service over an ad-hoc public tunnel from a dev machine because the service provides a documented API endpoint and credential boundary.

Experiment order:
1. In the UI, inspect the A100-1-80G point/hour estimate for a 1-hour dev machine and a 1-hour inference service. Do not create anything yet if the estimate is not clearly covered by the existing 5,000-point grant.
2. Request cloud-disk expansion to >=70 GB if available; this is the cleanest path to official BF16 weights.
3. If expansion is not granted, benchmark the 22.2 GB INT4 safetensors challenger against official Muse on a small fixed coding/agentic set.
4. Create a short-lived inference service and capture only the documented request/response **schema** (never the credential) so 0liviA can implement the exact adapter without guessing.
5. After a successful live smoke, add the provider as disabled-by-default `free_hard_cap` and expose it to the router health/circuit-breaker system.
6. Add automatic provider removal from routing when the service is stopped/expired, so chat never hangs waiting for a dead GPU lane.

### Intern Discovery / Intern InkStone as a GPU burst backend
Source: https://discovery.intern-ai.org.cn/docs/workbench/reasoning/

Official platform documentation confirms:
- cloud development machines can expose CPU/GPU/NPU resources, including NVIDIA-class GPU options, and mount persistent `/data` storage;
- inference services can deploy model folders from the platform cloud drive and expose a callable POST endpoint with a per-service credential;
- Hugging Face text-generation is a supported inference-service model format;
- development machines and inference services consume platform compute points while running, and a single scheduled runtime may be set for up to 7×24 hours;
- stopped resources stop consuming compute points and can later be restarted.

Fit for 0liviA:
- **strong GPU burst candidate** for Muse Glimmer and other heavyweight challengers;
- Muse Glimmer's official Q4_K_M GGUF is ~17 GB, so it is practical on a GPU development machine with llama.cpp when the selected GPU has enough VRAM;
- the documented hosted Inference Service path is preferable for 0liviA because it exposes a remote API, but the platform currently documents Hugging Face text-generation rather than GGUF as the managed serving format;
- do not assume that a llama.cpp server started manually inside a development machine is externally reachable until ingress/networking is proven;
- the outer Inference Service request uses `call_api_path`, `call_api_credential`, and a JSON-string `payload`, so 0liviA must not guess the response schema before a real Muse service is created and tested;
- service credentials belong only in server-side environment/configuration, never browser storage or chat.

Zero-cost status:
- **free/unverified**, not `free_hard_cap` yet;
- official docs prove compute-point accounting and quota requests, but do not establish a no-money/no-overage contract;
- therefore this provider must remain opt-in and excluded by 0liviA's hard-zero-cost router until account-level terms and exhaustion behavior are verified.

Decision: prepare the provider abstraction, but do not activate automatic routing until a real service proves model compatibility, response shape, endpoint reachability, latency, and strict no-overage behavior.

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


## Frontier-free provider audit — 2026-10-04

### DeepSeek V4.1 Flash on NVIDIA NIM

Official NVIDIA catalog evidence currently labels `deepseek-ai/deepseek-v4.1-flash` as a **Free Endpoint** and exposes the OpenAI-compatible hosted base at `https://integrate.api.nvidia.com/v1`.

Important licensing/operational constraint from NVIDIA's own NIM documentation:
- NVIDIA Developer Program access to hosted NIM endpoints is free for prototyping, research, development and testing;
- NVIDIA explicitly defines serving real end users / non-testing activity as production;
- production NIM use requires NVIDIA AI Enterprise licensing.

0liviA therefore integrates this endpoint as a high-priority development/evaluation lane and must not silently claim it is a production-free entitlement. Production enablement needs a compatible entitlement or a different verified-free production provider.

### Cloudflare fallback quality

Cloudflare Workers AI currently offers `@cf/openai/gpt-oss-120b` and `@cf/zai-org/glm-4.7-flash` without the paid-billing-method requirement that applies to its newest frontier models. The Free Workers plan includes 10,000 neurons/day and fails after the free allocation; a Paid Workers account can bill above that allocation.

For the temporary Cloudflare bridge, the ordered fallback is:
1. DeepSeek V4.1 Flash via NVIDIA NIM when explicitly configured;
2. GPT-OSS-120B on Workers AI;
3. GLM-4.7-Flash on Workers AI.

The bridge remains deployment-gated until account-wide Cloudflare billing status is verified. A per-worker request counter alone is not an account-wide no-overage guarantee.

### Catalog/failover patterns retained from free routing projects

Useful mechanisms observed repeatedly across `free-claude-code`, `my-free-code` and similar routers:
- provider catalog separated from transport;
- ordered model fallbacks;
- health/circuit backoff;
- quota/rate-limit awareness;
- stable product identity independent of provider;
- failover only before visible output;
- no restart of the user's turn when an upstream fails before output.

0liviA already implements these mechanisms in its Python router and mirrors the same pre-output failover rule in the temporary Worker bridge.

### Sources rejected as production dependencies

The GitHub `free-gpt-api` topic contains multiple reverse proxies that reuse consumer/session credentials or reverse-engineer private product surfaces. These violate 0liviA's explicit rule against reverse-engineered consumer-session APIs and are not eligible providers.

Other reviewed projects:
- `tw93/pake`: useful later to package the web client as a lightweight Tauri desktop shell; not a model/runtime dependency.
- `alibaba/page-agent`: useful reference for DOM-level browser agents and accessibility, but its demo LLM is evaluation-only and it is not the server-side browser worker.
- `JCodesMore/ai-website-cloner-template`: useful visual-reconstruction/QA methodology; not a runtime dependency.
- `openark/orchestrator`: MySQL HA tooling; unrelated to 0liviA's agent orchestration.
- Omarchy: useful product/agent-OS inspiration, but violates the cloud-first/no-owner-PC runtime constraint as a core dependency.


### Cloudflare account guard audit result

A dedicated GitHub Actions audit was executed from `simondalmasso/simon` using the already-existing Cloudflare deploy credentials.

Result:
- credentials were present;
- `GET /accounts/{account_id}/subscriptions` returned HTTP 403;
- therefore the deploy token lacks the Billing Read permission needed to prove the account plan;
- the audit records `ACCOUNT_ZERO_COST_VERIFIED=NO` and `REASON=billing_read_permission_unavailable`.

Consequence: the latest inference bridge must not be deployed under a claim of account-wide zero-cost safety until billing-plan evidence is available. Production remains unchanged.
