# 0liviA 🎲

0liviA is a **personal super-AI**: one persistent cloud intelligence for its owner, combining conversation, coding, repository control, research, tools, memory, autonomous execution and live voice. It is not a generic SaaS workspace, a team product, or a thin chatbot wrapper.

The target is deliberately hard: **always available, browser-first, persistent, fast, model-agnostic and $0 to operate within free-tier limits**. The user's PC must not be required for normal operation.

## Non-negotiable constraints

- **Cloud-only runtime:** normal use must continue with the user's PC turned off.
- **Budget:** target recurring infrastructure cost is USD 0.
- **Primary host available:** Oracle Cloud Free Tier, `VM.Standard.A1.Flex`, up to **2 OCPU / 12 GB RAM**, São Paulo.
- **GitHub is the durable source of truth:** code, architecture, agent instructions and checkpoints live here.
- **Cloudflare is for application deployment only.** Normal chat, memory, voice and agent turns must not depend on Cloudflare Workers/Tunnel/runtime.
- **Browser-first:** text chat and one-button live voice should work from desktop/mobile browsers.
- **Model-agnostic:** no single model/provider may be a permanent dependency; routing/fallback is expected.
- **Persistent memory/context:** conversations, project state, decisions and learned operating patterns should survive restarts and model swaps.
- **High autonomy with evidence:** agents should plan, execute, verify, recover and leave current checkpoints without claiming unverified success.
- **Security:** least-privilege credentials, no secrets in prompts/memory/git, explicit approval for destructive or high-impact actions.

## Current research tracks

The repository is intentionally not committed to one stack yet. The council should evaluate and benchmark candidates rather than inherit a predetermined architecture.

### Agent / harness / orchestration
- Agent Zero — https://github.com/agent0ai/agent-zero
- DeepSeek Harness — https://github.com/deepseek-ai/deepseek-harness
- OpenCode — https://github.com/anomalyco/opencode
- OmO / oh-my-openagent — https://github.com/code-yeongyu/oh-my-openagent
- Tenet — https://github.com/JeiKeiLim/tenet
- HarnessRouter — https://github.com/HarnessRouter/harnessrouter
- Letta Code — https://github.com/letta-ai/letta-code
- Monomind — https://github.com/monoes/monomind
- free-claude-code — https://github.com/Alishahryar1/free-claude-code
- GitHub MCP Server — https://github.com/github/github-mcp-server
- MCP ecosystem — https://github.com/mcp

### Live voice / realtime
- GhostCall — https://www.ghostcall.space/
- LiveKit Agents — https://github.com/livekit/agents
- StreamCore — https://github.com/streamcoreai/streamcore-server
- Moonshine Voice — https://github.com/moonshine-ai/moonshine
- faster-whisper — https://github.com/SYSTRAN/faster-whisper
- Silero VAD — https://github.com/snakers4/silero-vad
- Kokoro — https://github.com/hexgrad/kokoro
- MOSS-TTS-Nano — https://github.com/OpenMOSS/MOSS-TTS-Nano
- Fish Speech — https://github.com/fishaudio/fish-speech
- OpenVoice — https://github.com/myshell-ai/OpenVoice
- CosyVoice — https://github.com/QwenAudio/CosyVoice

## Start here

**Council / implementation order:** [`SUPER_ORDER_END_TO_END.md`](./SUPER_ORDER_END_TO_END.md)

Give that single file to any zero-context LLM/coding agent with GitHub access. It is intentionally architecture-neutral and instructs the agent to research stronger alternatives and implement evidence-backed improvements directly in this repository.

## Repository map

- `SUPER_ORDER_END_TO_END.md` — canonical zero-context council + end-to-end build order for building the personal super-AI.
- `AGENTS.md` — invariant operating contract for any coding/research agent.
- `docs/COUNCIL_HANDOFF.md` — compact zero-context handoff for independent LLM council review.
- `docs/RESEARCH.md` — verified facts, candidates, caveats and open questions.
- `docs/DECISIONS.md` — append-only architectural decisions once evidence justifies them.

## Status

**Phase:** architecture research / council review  
**Default branch:** `main`  
**Deployment:** not started  
**Production claims:** none

Do not treat candidate links as approved dependencies. Benchmark against the actual Oracle Free Tier machine and preserve replaceability.
