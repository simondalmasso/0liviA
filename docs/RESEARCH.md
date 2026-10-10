# Research notes

Last updated: 2026-10-09

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

Sources:
- https://discovery.intern-ai.org.cn/docs/workbench/developer/
- https://discovery.intern-ai.org.cn/docs/workbench/reasoning/
- https://dev.meta.ai/docs/muse-glimmer/llama-cpp

Verified platform facts:
- development machines offer CPU/GPU/NPU configurations, with NVIDIA A100 shown as an available resource family;
- persistent files belong under `/data`; other development-machine storage is ephemeral;
- running machines and inference services consume platform compute points and can be stopped/restarted;
- a single configured runtime is capped at 7×24 hours;
- Inference Service supports `Hugging Face - text-generation`, model folders from cloud storage, and exposes a callable POST endpoint plus per-service credential and usage statistics;
- the outer call contract wraps the model payload with `call_api_path`, `call_api_credential`, and a JSON-string `payload`.

Muse Glimmer fit:
- Meta Muse Glimmer is a 30B Apache-2.0 agentic/coding model;
- Meta publishes an official ~16.8 GB Q4_K_M GGUF text checkpoint for llama.cpp plus optional vision/speculative assets;
- GGUF is a good fit for a GPU development machine using llama.cpp, but the managed Inference Service documentation currently advertises Hugging Face text-generation rather than GGUF/llama.cpp;
- therefore a manually started llama.cpp server is useful for benchmarking, but must not be assumed externally reachable until ingress is proven;
- for the managed API path, prefer a compatible Hugging Face-format Muse checkpoint/runtime and capture the service's actual request/response schema before implementing an adapter.

0liviA role:
- treat Intern Discovery as an **ephemeral GPU accelerator**, never the only brain;
- keep the canonical Core/router independent so a stopped/expired GPU lane simply disappears from routing;
- keep the service credential server-side only; never place it in browser storage, chat, Git, logs, Library or Memory;
- never auto-start or auto-extend point-consuming resources without an explicit owner action;
- do not guess the response envelope: implement the tiny adapter only after a real service smoke exposes its exact schema.

Zero-cost status:
- **free/unverified**, not `free_hard_cap`;
- official docs prove compute-point accounting and quota management, but do not establish a no-money/no-overage contract;
- 0liviA's hard-zero-cost router must therefore exclude this route until account-level exhaustion/billing behavior is verified.

Experiment order:
1. Keep worker outputs/checkpoints under `/data`; 0liviA includes `scripts/ephemeral_checkpoint.py` to snapshot/restore bounded worker state without provider APIs or credentials.
2. Read the platform's point/hour estimate for a short GPU development-machine run and inference-service run before creating anything.
3. Benchmark official Muse GGUF on a short-lived GPU development machine if the selected GPU has enough VRAM.
4. Prefer the managed Inference Service for 0liviA once a compatible Muse model format is available.
5. Capture only the request/response **schema** from a successful service smoke; never record the credential in the repo.
6. Add a disabled-by-default provider adapter and only promote it after latency, quality, uptime and strict no-overage gates pass.
7. Do not automate start/extend/restart through UI clicking; only add lifecycle automation after an official management API and account authorization are verified.

## Pocket local fallback candidates — 2026-10-09

### Qwen2.5-Coder-0.5B-Instruct GGUF
Source: https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF

Verified facts:
- official Qwen GGUF repository exists;
- license is Apache-2.0;
- llama.cpp supports the published `Q4_K_M` quantization directly;
- this is a code-specialized sub-1B model and therefore materially below 0liviA's desired primary coding quality floor.

0liviA role:
- **evaluation-only pocket helper**, never the default chat/coding brain;
- eligible tasks are bounded local chores such as diff summarization, error classification, tiny syntax completion or test suggestion;
- not eligible for architecture decisions, autonomous multi-file implementation, security review, final code review or silent fallback from a frontier route;
- activation must be explicit in the provider catalog and must surface degraded capability rather than pretending equivalent quality;
- runtime memory must be measured separately from model-file size because KV cache, tokenizer/buffers and the OS add substantial overhead.

### Qwen3.5-0.8B
Source: https://huggingface.co/Qwen/Qwen3.5-0.8B

Verified facts:
- official Qwen post-trained 0.8B model;
- Apache-2.0;
- multimodal/generalist rather than a dedicated code model.

0liviA role:
- challenger for instruction-following or tiny multimodal/local tasks;
- not a presumed upgrade over Qwen2.5-Coder-0.5B for code;
- benchmark before any use, and keep outside primary routing unless it independently meets a task-specific quality floor.

Pocket-model decision:
- **availability is not allowed to override quality**;
- if no frontier/approved route exists, 0liviA may expose a clearly labeled degraded local helper for narrow tasks or fail closed;
- it must not silently answer serious coding/architecture tasks with a pocket model merely to avoid an outage.

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


### OpenClaw 2026.9.8 / GPT-6 Astra → official Sign in with ChatGPT route

Sources:
- owner-provided screenshots from 2026-10-05;
- https://github.com/openclaw/openclaw
- https://developers.openai.com/siwc/token-sharing-open-source
- https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites
- https://github.com/openai/sign-in-with-chatgpt-devkit

Updated verification:
- the screenshots are consistent with OpenClaw exposing `openai/gpt-6-astra` in a configured environment;
- OpenAI now officially documents **Sign in with ChatGPT** plan usage for open-source tools, and lists OpenClaw among supported examples;
- eligible Plus/Pro owners may authorize supported external tools to consume ChatGPT-plan usage without creating or sharing an OpenAI API key;
- the requested OAuth permission includes `chatgpt.tokens.use.direct`;
- eligible requests use the official Responses API; OpenAI's OSS docs require `store:false` and streaming;
- app usage has owner-controlled limits. Paid ChatGPT credits after included usage are opt-in and are off by default; an app limit below 100% prevents credit use for that app;
- if an app cannot use plan usage or allowed credits, it does not automatically switch to a different paid option.

What the screenshots still do **not** prove:
- that every listed OpenClaw slug is available to every ChatGPT account;
- unlimited/free usage: plan usage is bounded by the connected account's allowance and app limit;
- that 0liviA has completed its own OAuth connection; it has not.

0liviA implementation/decision:
- do **not** import OpenClaw as a runtime dependency;
- use the documented OpenAI path directly behind the existing provider router;
- a native `chatgpt_plan` provider now targets `https://api.openai.com/v1/responses`, keeps OAuth credentials server-side, refreshes them, and uses `store:false`;
- `gpt-6-astra` is a preferred configured slug, not a hardcoded identity claim; actual availability must come from the signed-in account/model catalog;
- under hard-zero-cost mode, this route is blocked unless `no_credit_overage_verified=true`; that remains an owner/account assertion until onboarding can inspect/guide the relevant ChatGPT Usage controls;
- one-time OAuth onboarding mechanics are implemented independently from the DevKit; the remaining gate is a real owner connection, Usage-control verification, secure profile transfer and bounded live smoke. The OpenAI DevKit remains an implementation/security reference, but its noncommercial license means 0liviA does not copy it wholesale.




## 2026-10-05 — Muse Glimmer challenger

Official Meta documentation describes Muse Glimmer as an Apache-2.0, 30B dense multimodal model with a default 128K context, strong tool-use/agentic benchmarks and OpenAI-compatible serving through supported runtimes.

Fit for 0liviA:
- **yes** as a replaceable self-hosted/high-end challenger behind the existing OpenAI-compatible provider contract;
- **no** as the Oracle A1 default: the recommended llama.cpp Q4_K_M text GGUF is ~17 GB before the optional vision projector, so a 12 GB A1 does not provide a safe production fit;
- current llama.cpp bootstrap build b11388 is newer than Meta's documented Muse Glimmer support floor b10353, so no new provider module is required when suitable GPU/RAM hosting becomes available;
- hosted providers remain subject to their own pricing/overage controls and are therefore not admitted to the hard-zero-cost route without account-level proof.

Conclusion: keep Muse Glimmer in the challenger catalog; do not inflate the Core with Muse-specific logic.

## 2026-10-05 — OpenClaw / GPT-6 Astra evidence supplied by owner

The owner supplied screenshots showing an OpenClaw model catalog containing OpenAI model slugs including openai/gpt-6-astra, and a successful response reading “GPT-6 Astra funcionando correctamente.”

What this establishes:
- that the displayed OpenClaw environment can enumerate that model name;
- that a request in that environment returned a successful text response.

What it does **not** establish:
- that the route is official OpenAI plan usage rather than another provider/credential path;
- that the route is recurring-free, no-overage, production-stable or transferable to 0liviA;
- that 0liviA should depend on OpenClaw.

0liviA therefore keeps the native official ChatGPT-plan transport as the preferred plan-included path and treats OpenClaw only as external interoperability evidence.


## External OSS screening — 2026-10-09 (README-level)

### Brewery (formerly Homebrew AI)
Source: https://github.com/empero-org/brewery-ai (former `empero-org/homebrew-ai` redirects).

- Scope: guided text/image fine-tuning (LoRA/QLoRA/SFT/CPT/DPO), datasets, GPU/SSH training and Hugging Face publishing.
- 0liviA fit: research pattern, **not** an inference/coding-core dependency. Reuse ideas for GPU-cost confirmation, checkpointed jobs, reproducible evaluation and licence checks.
- $0 gate: **not a verified zero-cost inference endpoint**. GPU rental and storage can incur costs. Do not provision or integrate by default.
- Licence: README describes a conditional Brewery licence with a revenue threshold. Verify actual terms before copying code.
- Evidence: README and public file tree reviewed; no training, API usage or provider billing verification.

### Dev to Publish
Source: https://github.com/amirmushichge/dev-to-publish

- Scope: optional agent skill for product demos, editorial adaptation, previews, human approval and Buffer API publishing.
- 0liviA fit: future optional publishing workflow, not browser/model routing/coding intelligence. Useful pattern: prepare → approve → execute → receipt → reconcile ambiguous submissions.
- $0 gate: offline dry runs need no account; real delivery depends on Buffer API eligibility, connected channels and the account's terms. No verified recurring-$0 entitlement.
- Decision: do not install as a Core dependency or activate external publication now.
- Evidence: README inspected; no Buffer account connection or live publishing performed.
