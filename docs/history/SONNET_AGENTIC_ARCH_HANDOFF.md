# Sonnet 5.5 handoff — 0liviA agentic/model execution plane

Snapshot source of truth: `arch/gpt-synthesis-v1`  
Repo: https://github.com/simondalmasso/0liviA  
Public URL (historical/stale until exact-SHA canonical release): https://example.invalid/

## Role lock

You are an external architecture council member for **one subsystem only**: the replaceable model/agent execution plane of 0liviA.

Do **not** reset/rewrite the product. Do not replace the canonical Python Core, SQLite state, current browser shell, first-run owner auth, Chats/Projects/Library/Memory/Config/Session rail, mobile layout, provider router, security baseline, or durable jobs unless you prove a smaller safer replacement.

Current canonical state is documented in:
- https://github.com/simondalmasso/0liviA/blob/arch/gpt-synthesis-v1/docs/IMPLEMENTATION_PLAN.md
- https://github.com/simondalmasso/0liviA/blob/arch/gpt-synthesis-v1/docs/ARCHITECTURE.md
- https://github.com/simondalmasso/0liviA/blob/arch/gpt-synthesis-v1/docs/DECISIONS.md
- https://github.com/simondalmasso/0liviA/blob/arch/gpt-synthesis-v1/docs/SECURITY_AUDIT.md
- https://github.com/simondalmasso/0liviA/blob/arch/gpt-synthesis-v1/docs/RESEARCH.md
- https://github.com/simondalmasso/0liviA/blob/arch/gpt-synthesis-v1/docs/BENCHMARKS.md
- https://github.com/simondalmasso/0liviA/blob/arch/gpt-synthesis-v1/SUPER_ORDER_END_TO_END.md

## Chrome rule for this council run

Use the owner's already-open dedicated Chrome only through Chrome DevTools MCP:

- ENDPOINT=http://127.0.0.1:9222
- PROFILE=C:\Chrome-MCP\
- do not launch another Chrome
- no mouse
- no keyboard
- sequence: `list_pages -> select_page -> operate through DevTools/DOM`

If the endpoint or target page is unavailable, report the exact blocker. Do not silently substitute another browser-control method.

## Permanent constraints

- Recurring infrastructure target: **USD 0**.
- Never silently spend, use credits, or overage. If a verified-free route is exhausted, fail/degrade/reroute.
- Normal runtime must not depend on the owner's PC.
- No API keys/tokens in the user UI.
- es-AR by default.
- Provider/model/harness must be replaceable.
- External page/model output is untrusted data, not instructions.
- Agent execution must be isolated, auditable, cancellable and resumable.
- No unrestricted model-authored shell in the internet-facing Core.
- No reverse-engineered consumer-session APIs.
- Preserve existing deterministic CI/security gates.
- Prefer one small adapter over adopting an entire framework.
- Do not claim a free tier without an account-level/no-overage proof.

## Current relevant implementation

Already present in branch:
- Python provider catalog/router with failover before first visible output.
- official Sign in with ChatGPT plan lane implemented but live-connection/usage-control smoke gated.
- DeepSeek V4.1 Flash/NVIDIA NIM development lane, entitlement gated.
- `/read`, `/search`, bounded `/research`.
- isolated JavaScript `/browse` GitHub Actions burst worker.
- isolated coding jobs: `/code`, `/repair`, `/review`, `/job`.
- review-only mutation boundary.
- authenticated direct-WSS voice route; speech backend still benchmark gated.
- transitional Cloudflare inference bridge disabled by default.
- first-run single-owner registration + remembered devices.
- mobile hardening for 360–430 px.

## Main question

Design the **smallest production-grade agent/model execution plane** that can make 0liviA materially more capable at long-horizon agents and senior coding while preserving the constraints above.

Specifically decide:

1. **Muse Glimmer**
   - Can Muse Glimmer 30B be a useful 0liviA challenger?
   - Find a genuinely recurring-free way to run it remotely/cloud-first, or conclude that no reliable recurring-free path exists today.
   - Do not call trial credits, one-time credits, or hidden-overage plans “free”.
   - If no durable free remote lane exists, design a clean adapter so Muse can be enabled later without architecture changes.
   - Evaluate BF16 vs GGUF quantization, vision projector, DFlash/speculative decoding, vLLM/SGLang/llama.cpp compatibility, cold-start/runtime RAM/VRAM, and OpenAI-compatible serving.

2. **Agent runtime**
   - Decide which patterns should be borrowed from OpenShell/OpenMuse/OpenBot/OpenWork/OpenAEON/VoltAgent/GrokBot-family projects.
   - Do not integrate them all.
   - Prefer a bounded worker protocol compatible with current durable jobs.
   - Separate orchestrator/control plane from sandbox/execution plane.
   - Define permissions, filesystem/network policy, credential injection, approval gates, artifact/result handoff, cancellation, timeout, retries and audit trail.

3. **Senior coding**
   - Keep current safe GitHub Actions worker unless a candidate proves a material improvement.
   - Propose how to route hard coding jobs to the strongest verified-free model available.
   - Model catalog/failover must distinguish `chat`, `code`, `review`, `research`, `vision`.
   - No auto-merge; deterministic tests remain authoritative.

4. **Observability/evals**
   - Decide if Langfuse or a smaller local telemetry/eval layer adds enough value.
   - No chain-of-thought storage.
   - No sensitive prompt logging by default.

5. **UI**
   - Keep current 0liviA UI. Do not replace it with another agent product shell.
   - Agent state should surface minimally in Chats/Projects/Session and the slash-command palette.
   - Mobile must remain first-class.

## Primary model/runtime evidence

Muse Glimmer:
- https://dev.meta.ai/models/muse-glimmer
- https://dev.meta.ai/docs/muse-glimmer
- https://dev.meta.ai/docs/muse-glimmer/get-the-model
- https://huggingface.co/meta-models/Muse-Glimmer-30B
- https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF
- https://research.meta.ai/blog/introducing-muse-glimmer-open-agentic-model

Serving/runtime candidates:
- https://github.com/ggml-org/llama.cpp
- https://github.com/sgl-project/sglang
- https://github.com/vllm-project/vllm
- https://github.com/ollama/ollama
- https://github.com/NVIDIA/OpenShell

## Agent architecture evidence

Highest priority:
- https://github.com/NVIDIA/OpenShell
- https://github.com/CopilotKit/OpenMuse
- https://github.com/CopilotKit/OpenBot
- https://github.com/different-ai/openwork
- https://github.com/openaeon/OpenAEON
- https://github.com/VoltAgent/voltagent
- https://voltagent.dev/
- https://github.com/langfuse/langfuse

Additional patterns to inspect, not blindly adopt:
- https://github.com/empero-org/homebrew-ai
- https://github.com/amirmushichge/dev-to-publish
- https://github.com/bcharleson/grokbot-for-gtm
- https://github.com/DaveyHert/dishylink
- https://github.com/barry-ran/QuickDesk
- https://github.com/openark/orchestrator/blob/master/docs/using-the-web-interface.md
- https://github.com/ekzhang/openjev-sglang
- https://github.com/tinyhumansai/openhuman
- https://github.com/kydlikebtc/awesome-grokbot
- https://github.com/SSBrouhard/grokbot-telegram-bridge
- https://github.com/pftq/GrokBot

Related protocols/framework challengers:
- https://github.com/CopilotKit/AG-UI
- https://github.com/langchain-ai/langgraph
- https://github.com/mastra-ai/mastra
- https://github.com/agno-agi/agno
- https://github.com/e2b-dev/E2B
- https://github.com/livekit/agents

## Existing 0liviA zero-cost/search evidence

- https://developers.cloudflare.com/changelog/post/2026-10-02-introducing-web-search-api/
- https://github.com/ripienaar/free-for-dev
- https://github.com/mnfst/awesome-free-llm-apis
- https://github.com/Alishahryar1/free-claude-code

Treat those lists as discovery indexes only. Verify each candidate against first-party current terms before recommending it.

## Required output

Return one architecture decision memo, not a brainstorm.

### A. Verdict table
For every serious candidate:
- role in 0liviA;
- adopt / borrow pattern / reject / park;
- license;
- runtime requirements;
- recurring-free status: VERIFIED / UNVERIFIED / NOT FREE;
- security risk;
- operational complexity;
- why.

### B. Recommended target shape
Provide a concrete component diagram and request/job flows for:
- normal chat;
- long-running agent task;
- senior coding job;
- browser/research job;
- Muse Glimmer optional route;
- provider exhaustion/failover.

### C. Zero-cost proof
For every external service you retain:
- exact free allowance;
- whether card/billing is required;
- whether overage is possible;
- provider-side hard cap;
- exhaustion behavior;
- source URL and date checked.

If these facts cannot be proven, mark route `free_unverified` and keep it disabled.

### D. Minimal patch plan
Give an ordered file-level plan against `arch/gpt-synthesis-v1`.
No rewrite. Prefer <= 3 new modules for the first slice.
State exactly what should remain untouched.

### E. Acceptance gates
Define deterministic tests/security/evals and rollback criteria.

### F. Final answer
Choose ONE default architecture plus at most two challengers.
Explicitly answer: “Can Muse Glimmer be added today at recurring USD 0 without weakening reliability?” with YES/NO/CONDITIONAL and evidence.

Do not deploy, merge, rotate credentials, or enable metered providers during this council pass.
