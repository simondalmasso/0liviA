# 0liviA — Council Handoff

Repository: https://github.com/simondalmasso/0liviA

You are one independent member of an LLM architecture council. Do **not** inherit another model's preferred stack. Inspect the repo, verify current sources, challenge weak assumptions, and improve the project directly in GitHub if your host has write access.

## Goal

Design and, where safe, scaffold **0liviA**: a cloud-only personal AI workspace that feels fast and alive rather than like a slow chatbot. It should combine strong coding/research execution, persistence, memory, model/harness flexibility, recovery across long tasks, and a one-button low-latency live voice mode comparable in feel to modern realtime assistants.

Target behavior:
- quick / opportunistic / combative when useful, like a strong Grok-style coding bot;
- persistent and hard to derail across long work;
- experimentally curious but evidence-driven;
- good judgement and restraint;
- strong coding quality and verification;
- learns project/user patterns without silently corrupting durable truth.

Do not copy those personas literally. Convert them into measurable system behavior.

## Hard environment

- Recurring target cost: **USD 0**
- Normal operation: **100% cloud; operator's PC may be off**
- Reference low-cost host profile:
  - region: operator-selected
  - `VM.Standard.A1.Flex`: **2 OCPU / 12 GB RAM free**
  - ~153 GB free block storage
  - ~20 GiB free Object Storage
- GitHub is the durable source of truth.
- Cloudflare is for **deploying user applications only**. Do not route normal 0liviA chat, model, memory or voice turns through Workers/Tunnel/DO/proxy unless you can prove a compelling reason and label it as a proposal rather than an assumption.
- No mandatory paid API/SaaS.
- No cookie/session hacks or reverse-engineered commercial APIs.
- Swappable models/providers and graceful fallback are required.

## Candidate pool — evidence, not architecture

Agent / harness / orchestration:
- Agent Zero — https://github.com/agent0ai/agent-zero
- DeepSeek Harness — https://github.com/deepseek-ai/deepseek-harness
- OpenCode — https://github.com/anomalyco/opencode
- OmO — https://github.com/code-yeongyu/oh-my-openagent
- Tenet — https://github.com/JeiKeiLim/tenet
- HarnessRouter — https://github.com/HarnessRouter/harnessrouter
- Letta Code — https://github.com/letta-ai/letta-code
- Monomind — https://github.com/monoes/monomind
- free-claude-code — https://github.com/Alishahryar1/free-claude-code
- GitHub MCP Server — https://github.com/github/github-mcp-server
- MCP org — https://github.com/mcp

Voice / realtime:
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

Useful current facts to verify yourself:
- GhostCall advertises free browser P2P WebRTC calls with no account, but no public programmable bot API/self-host contract has yet been established.
- LiveKit Agents is open source, WebRTC-native, supports MCP, turn detection and self-hosting.
- Moonshine is explicitly built for low-latency streaming speech on CPU/on-device.
- Silero VAD is tiny and sub-millisecond per ~30 ms chunk on a CPU thread according to its project.
- MOSS-TTS-Nano is ~100M parameters, open source, streaming, CPU-oriented and has an ONNX path.
- Kokoro is 82M parameters and lightweight, but actual first-audio latency on this exact 2-OCPU Ampere host must be benchmarked.
- The original `rhasspy/piper` repository is archived; do not select it by nostalgia without checking the maintained successor.

## Your task

1. Independently rank the strongest current architecture for:
   - orchestration / harness;
   - model routing / fallback;
   - persistent memory + context compression/relearning;
   - browser + GitHub + MCP tool use;
   - long autonomous coding/research runs with verification/recovery;
   - realtime voice transport, VAD, STT, turn detection and TTS.
2. Search for **better current alternatives** beyond the list.
3. Reject components that are too heavy, immature, unmaintained, license-problematic, x86/GPU-bound, or unrealistic on 2 OCPU / 12 GB.
4. Define a benchmark matrix rather than choosing by stars or marketing.
5. For live voice, target one-button browser start, barge-in, partial transcript, streamed answer and warm conversational prosody. Quantify TTFT/TTFA and CPU/RAM.
6. Decide whether GhostCall can actually be integrated programmatically at $0. If not, keep its UX/P2P idea but choose a programmable open transport.
7. Write your findings into this repo. Prefer:
   - `docs/council/<your-model>.md`
   - code/scaffolding only when justified
   - update `docs/RESEARCH.md` with verified evidence
   - propose, do not silently overwrite, major architectural decisions.

## Deliverable

Leave the repo in a more useful state than you found it:
- recommendation + runner-up;
- rejected candidates and why;
- exact zero-cost dependency assumptions;
- estimated resource envelope;
- voice latency plan;
- benchmark/test plan;
- smallest implementation slice that proves or falsifies the architecture.

Do not deploy paid infrastructure. Do not fake completion. If a claim cannot be verified, mark it UNKNOWN and continue with the strongest testable path.
