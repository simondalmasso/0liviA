# 0liviA 🌠 — SUPER ORDER
## Independent End-to-End Build Mandate

**Repository:** https://github.com/simondalmasso/0liviA  
**Public app target:** https://0livia.simondalmasso44.workers.dev/

You are one independent member of an expert LLM engineering council. Your job is not to agree with prior work. Your job is to **beat it**.

Do not inherit a preferred architecture from this repository, from another model, or from the person who sent you this prompt. Treat 0liviA as a fresh systems problem with hard constraints, current evidence, and a concrete outcome.

Research broadly outside this repo. Use current primary sources, official docs, active repositories, release notes, benchmarks, source code and live tests. If you find a stronger architecture, stronger harness, stronger model-routing layer, stronger memory design, stronger voice stack, stronger browser/tool stack, or stronger engineering process than anything already mentioned, **use it**.

Do not optimize for what is fashionable. Optimize for:
- speed;
- autonomy;
- coding ability;
- repository control;
- research quality;
- persistence;
- context retention;
- relearning;
- recovery;
- low latency;
- reliability;
- inspectability;
- security;
- replaceability;
- real USD 0 operation.

0liviA must **fly**.

---

# 1. PRODUCT OUTCOME

Build **0liviA**, a cloud-resident personal AI workspace that can operate for long periods without the user's PC.

It must be capable of:

- high-quality text conversation;
- one-button low-latency live voice;
- writing, refactoring, debugging and reviewing code;
- understanding unfamiliar repositories;
- managing GitHub repositories, branches, commits, PRs, issues and releases when authorized;
- running tests, builds, linters, typechecks, browser checks and audits;
- researching the live web and preserving source-backed evidence;
- using MCP, tools and skills without degenerating into tool-call spam;
- delegating to subagents or alternative models when useful;
- remembering durable project/user information across sessions;
- compacting context without losing important state;
- resuming interrupted work without rediscovering everything;
- recovering from provider, model, tool and process failures;
- deploying user applications when explicitly requested;
- distinguishing VERIFIED facts from assumptions;
- leaving exact checkpoints so another agent can resume instantly.

The desired behavior should feel:
- fast and opportunistic;
- difficult to stall;
- persistent;
- experimentally curious;
- technically disciplined;
- strategically creative;
- concise in ordinary chat;
- deep when the task demands it;
- willing to abandon weak approaches quickly.

Do not imitate named model personalities. Translate the desired qualities into measurable system behavior.

---

# 2. HARD CONSTRAINTS

## Runtime

Normal operation must be **100% cloud-based**.

The user's PC may be powered off. Do not make desktop remote access, local GPU, local browser automation or local background processes a dependency.

Available always-on infrastructure currently verified:

- Oracle Cloud Free Tier
- region: `sa-saopaulo-1`
- `VM.Standard.A1.Flex`
- ARM64
- maximum free allocation currently visible: **2 OCPU / 12 GB RAM**
- approximately **153 GB free block storage**
- approximately **20 GiB free Object Storage**
- currently **0 compute instances**

Treat the actual Oracle machine as the benchmark target.

Do not design for imaginary hardware.

## Cost

Recurring operating target: **USD 0**.

Do not make any of these mandatory:
- paid model APIs;
- paid GPU;
- paid database;
- paid vector DB;
- paid queue;
- paid browser farm;
- paid telephony;
- paid inference gateway;
- paid observability;
- paid SaaS.

Free quotas are allowed only behind replaceable abstractions.

If one free provider disappears, 0liviA must degrade or reroute rather than die.

## GitHub

GitHub is the durable source of truth for:
- code;
- architecture;
- agent instructions;
- decisions;
- tests;
- deployment config;
- checkpoints;
- evaluation results;
- reproducible evidence.

Do not leave critical system truth trapped only inside model context.

## Cloudflare

Cloudflare is for **deployment of user applications**.

Do not make normal 0liviA chat, memory, inference or voice turns depend on:
- Workers;
- Durable Objects;
- AI Gateway;
- Tunnel;
- Workers AI;
- Cloudflare Containers;
- Cloudflare proxying.

A thin deployed frontend at:

https://0livia.simondalmasso44.workers.dev/

is acceptable.

Do not silently move the intelligence, persistent memory or live voice backend into Cloudflare.

If you believe a Cloudflare component is objectively superior, document the reason and treat it as a proposed exception, not an inherited assumption.

## Security

- never commit secrets;
- never persist raw credentials in memory;
- use least-privilege scopes;
- separate read-only discovery from mutation;
- protect against prompt injection from web pages, repos and MCP results;
- require explicit authorization for destructive/high-impact operations;
- make rollback possible;
- never call NOT_CHECKED a PASS;
- never fabricate tool execution.

## Model independence

No provider is sacred.

Do not build around one vendor.

Avoid:
- reverse-engineered consumer cookies;
- session scraping;
- unofficial auth bypasses;
- brittle wrappers around consumer chat products;
- anything likely to violate provider terms or disappear overnight.

---

# 3. RESEARCH OUTSIDE THIS REPO IS MANDATORY

Do not constrain yourself to this seed list.

Search for newer, stronger 2026 alternatives.

Evaluate actual project health:
- release cadence;
- recent commits;
- maintainers;
- issue velocity;
- license;
- ARM64 viability;
- resource requirements;
- API stability;
- community;
- security posture;
- production evidence.

Do not rank by stars.

## Seed: agent / coding / orchestration

- https://github.com/agent0ai/agent-zero
- https://github.com/deepseek-ai/deepseek-harness
- https://github.com/anomalyco/opencode
- https://github.com/code-yeongyu/oh-my-openagent
- https://github.com/JeiKeiLim/tenet
- https://github.com/HarnessRouter/harnessrouter
- https://github.com/letta-ai/letta-code
- https://github.com/monoes/monomind
- https://github.com/Alishahryar1/free-claude-code
- https://github.com/github/github-mcp-server
- https://github.com/mcp

## Seed: voice / realtime

- https://www.ghostcall.space/
- https://github.com/livekit/agents
- https://github.com/streamcoreai/streamcore-server
- https://github.com/moonshine-ai/moonshine
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/snakers4/silero-vad
- https://github.com/hexgrad/kokoro
- https://github.com/OpenMOSS/MOSS-TTS-Nano
- https://github.com/fishaudio/fish-speech
- https://github.com/myshell-ai/OpenVoice
- https://github.com/QwenAudio/CosyVoice
- https://github.com/coqui-ai/TTS
- https://github.com/openai/whisper

## Seed: tools / browser / MCP / device

- https://github.com/github/github-mcp-server
- https://github.com/mobile-next/mobile-mcp
- https://github.com/mcp
- Playwright
- browser-use
- Stagehand
- computer-use frameworks
- code graph / repository intelligence systems
- agent memory systems
- durable job systems
- current MCP registries and security tooling

If something better exists, bring it in.

---

# 4. SOLVE THE INTELLIGENCE LAYER

Design how 0liviA decides:

- which model handles ordinary chat;
- which model plans;
- which model codes;
- which model reviews;
- which model researches;
- which model handles long-context reasoning;
- when to invoke a specialist;
- when to retry;
- when to switch models;
- when to stop;
- when to ask the user;
- when to continue autonomously.

Do not create a council for every request.

Fast/simple tasks should stay fast.

Escalate only when task value or risk justifies it.

The router must survive:
- rate limits;
- expired free quotas;
- provider downtime;
- model regressions;
- changing model names;
- temporary latency spikes.

Measure routing quality with real tasks.

---

# 5. FIND OR BUILD THE BEST HARNESS

0liviA needs a harness capable of:

- streaming chat;
- tool calling;
- shell execution;
- code execution;
- Git;
- GitHub;
- browser automation;
- MCP;
- skills;
- task cancellation;
- durable jobs;
- checkpointing;
- retries;
- recovery;
- logs;
- subagent delegation;
- repository isolation;
- long-running tasks;
- browser UI;
- ARM64 operation;
- low idle resource use.

If one existing project dominates, use it.

If the best design is compositional, integrate multiple focused components behind stable interfaces.

If existing projects are too heavy or brittle, build the minimum missing orchestration layer yourself.

Do not build complexity for its own sake.

---

# 6. MEMORY, CONTEXT AND RELEARNING

0liviA must not become amnesiac between sessions.

Design explicit memory horizons:

1. current-turn working state;
2. current conversation;
3. active task checkpoint;
4. durable user/project facts;
5. architecture/decision history;
6. episodic task history;
7. reusable skills/procedures;
8. codebase/repository knowledge.

Memory must be:
- inspectable;
- editable;
- deduplicated;
- source-aware;
- confidence-aware;
- compact;
- cheap to retrieve;
- resistant to hallucination;
- recoverable after restart;
- portable across models.

Not every sentence becomes permanent memory.

Define promotion, contradiction, expiry and compaction rules.

The system must be able to relearn:
- repeated user preferences;
- recurring repo patterns;
- failed approaches;
- successful workflows;
- provider/model strengths;
- benchmark results.

Do not let long-term memory become prompt garbage.

---

# 7. AUTONOMOUS SOFTWARE ENGINEERING

0liviA must be able to execute substantial engineering work end-to-end:

`discover → verify requirements → plan → isolate branch/worktree → implement → test → lint/typecheck → runtime/browser test → review → commit → push → PR → CI → diagnose → repair → reverify → handoff`

Required behavior:
- inspect repository instructions first;
- protect unrelated user changes;
- use atomic commits;
- preserve checkpoints;
- distinguish source truth from assumptions;
- run the smallest useful verification first;
- escalate verification before release/deploy;
- use independent review when worthwhile;
- leave exact evidence.

No "done" based on narration.

---

# 8. RESEARCH ENGINE

0liviA must research well.

Requirements:
- primary sources first;
- version-matched docs;
- current official repositories;
- source code when docs are ambiguous;
- explicit source freshness;
- facts separated from inference;
- conflicting evidence preserved;
- no fake certainty;
- research stops when the decision is grounded;
- durable evidence stored without bloating every prompt.

For current/fresh claims, use live search.

For repo-local claims, inspect the repo.

---

# 9. LIVE VOICE — MUST FEEL FAST

A core requirement is a **single-button live voice conversation**.

Target experience:

1. user taps a button;
2. microphone opens immediately;
3. partial speech recognition starts while the user is still talking;
4. natural turn completion is detected;
5. response generation begins quickly;
6. synthesized audio starts before the full answer is complete;
7. user can interrupt the assistant;
8. the assistant cancels pending speech/generation correctly;
9. text and voice share the same conversation state;
10. switching modes loses no context;
11. a long call does not leak memory or drift.

Measure:
- microphone-ready time;
- VAD latency;
- partial transcript latency;
- end-of-turn latency;
- LLM first token;
- time-to-first-audio;
- barge-in cancellation latency;
- CPU/RAM;
- reconnect time;
- 30-minute stability;
- 60-minute stability.

## GhostCall

Investigate independently:

https://www.ghostcall.space/

It currently advertises free browser P2P WebRTC calls without accounts.

Do not assume it exposes a programmable AI endpoint.

Determine whether there is:
- a documented API;
- bot/client SDK;
- protocol surface;
- safe automation path;
- reusable signaling path;
- self-hosting path.

If GhostCall can be integrated cleanly at USD 0, use it.

If not, do not force it. Reproduce the good UX with a better programmable open transport.

The requirement is **GPT-Live-like feel at USD 0**, not GhostCall loyalty.

## Voice components to evaluate

At minimum compare:
- LiveKit Agents;
- StreamCore;
- Moonshine;
- faster-whisper;
- Silero VAD;
- Kokoro;
- MOSS-TTS-Nano;
- Fish Speech;
- OpenVoice;
- CosyVoice.

Search beyond them.

Favor:
- streaming;
- ARM64;
- CPU viability;
- low first-audio latency;
- interruption support;
- natural prosody;
- active maintenance;
- permissive licensing.

Build a real prototype early:

`browser mic → realtime transport → VAD/turn detection → streaming STT → LLM → streaming TTS → browser speaker → barge-in`

Do not leave voice until the end.

---

# 10. BROWSER UX

Everyday operation should not require a terminal.

Minimum product surface:

- text chat;
- streaming responses;
- voice button;
- stop/cancel;
- visible active model/provider route;
- project/repo selector;
- current task state;
- compact tool activity;
- error/retry state;
- resumable task indicator;
- access to durable memory/checkpoints;
- deployment status when relevant.

Do not expose private chain-of-thought.

Keep UI low-overhead and fast.

Avoid telemetry-dashboards masquerading as UX.

---

# 11. GITHUB / REPOSITORY POWER

0liviA must be genuinely useful on repositories.

It should be able to:
- search code;
- understand structure;
- inspect history;
- create branches;
- create files;
- edit files;
- commit;
- push;
- open PRs;
- respond to reviews;
- inspect CI;
- repair failures;
- manage issues;
- prepare releases;
- maintain project handoffs.

Prefer official GitHub MCP/API/CLI paths.

Do not give every agent permanent write permission.

Use scoped permissions and privilege escalation by task.

---

# 12. DEPLOYMENT

0liviA itself and the applications it deploys are separate concerns.

When explicitly asked, 0liviA must be able to deploy user projects using the target platform's supported CLI/API/MCP.

For Cloudflare projects, that may mean Wrangler or official Cloudflare tooling.

Cloudflare should not become an always-on hidden dependency of 0liviA's normal conversation loop.

The public target:

https://0livia.simondalmasso44.workers.dev/

may host a thin frontend, landing page or browser client.

Do not deploy infrastructure merely because it exists.

---

# 13. RESOURCE DISCIPLINE

The always-on box is only:

**2 OCPU / 12 GB RAM ARM64**

Therefore:

- measure idle footprint;
- avoid running multiple heavyweight stacks just because they are interesting;
- prefer one small always-on control plane;
- use on-demand processes;
- stop idle workers;
- avoid duplicate databases;
- avoid duplicate vector stores;
- prefer SQLite/file-backed state when sufficient;
- move burst compute to legitimate free external capacity only when necessary;
- keep the permanent node boring and recoverable.

A system that technically runs but swaps constantly or responds slowly fails.

---

# 14. BENCHMARK BEFORE FREEZING ARCHITECTURE

Create a reproducible evaluation matrix.

At minimum:

## Agent / coding
- repo comprehension;
- bug fix;
- multi-file feature;
- failing test diagnosis;
- refactor;
- browser QA;
- PR review;
- long task resume;
- provider failure recovery.

Measure:
- success/failure;
- retries;
- wall time;
- tool calls;
- token/request usage where visible;
- human intervention;
- test quality;
- regression rate.

## Memory
- exact fact recall;
- conflicting memory;
- old fact superseded by new;
- session restart;
- multi-project separation;
- retrieval precision;
- context size growth.

## Voice
- TTFT;
- TTFA;
- turn detection;
- interruption;
- CPU/RAM;
- reconnect;
- long-session stability.

## Infrastructure
- cold boot;
- restart recovery;
- disk use;
- memory use;
- backup restore;
- migration to a fresh VM.

Architecture is provisional until actual numbers exist.

---

# 15. REPOSITORY DISCIPLINE

Work directly in:

https://github.com/simondalmasso/0liviA

Read first:
- `README.md`
- `AGENTS.md`
- `docs/RESEARCH.md`
- `docs/DECISIONS.md`
- `docs/COUNCIL_HANDOFF.md`
- this file

Create your council report at:

`docs/council/<MODEL-OR-AGENT>.md`

Do not overwrite another council member's report.

Record:
- what you researched;
- primary sources;
- what you rejected;
- what you recommend;
- exact reasons;
- resource estimates;
- unresolved risks;
- implementation evidence.

If you materially improve the architecture, update the appropriate docs.

For major architectural changes, add an ADR in `docs/DECISIONS.md`.

---

# 16. YOU ARE ALLOWED TO IMPLEMENT

Do not stop at commentary if you have the tools and permissions to improve the project.

You may:
- scaffold code;
- add tests;
- add CI;
- build benchmarks;
- add interfaces;
- implement prototype slices;
- build the browser UI;
- build the voice prototype;
- add memory experiments;
- add model-router experiments;
- add harness adapters;
- add GitHub/MCP integration;
- create branches/PRs.

But:

- do not spend money;
- do not provision paid resources;
- do not expose secrets;
- do not deploy destructive infrastructure;
- do not call something production-ready without evidence;
- do not rewrite working code merely to impose your taste.

Prefer small proof-producing implementation slices.

---

# 17. INDEPENDENT COUNCIL MODE

Your answer must be genuinely independent.

Do not say:
- "I agree with the previous architecture."
- "The proposed stack looks good."
- "I would keep what GPT suggested."

Instead:
1. reconstruct the problem yourself;
2. research;
3. compare;
4. falsify weak options;
5. design;
6. implement evidence where possible.

If your architecture is better, say why.

If the repository's current direction is better than alternatives, prove it.

---

# 18. REQUIRED DELIVERABLE

Before stopping, leave the repo in a more useful state.

At minimum produce:

1. **Primary recommendation**
2. **Runner-up architecture**
3. **Rejected options + reasons**
4. **Exact USD 0 assumptions**
5. **ARM64 / 2 OCPU / 12 GB resource estimate**
6. **Memory architecture**
7. **Model routing architecture**
8. **Coding/repo workflow**
9. **Research workflow**
10. **Live voice architecture**
11. **Security model**
12. **Failure/recovery strategy**
13. **Benchmark plan**
14. **Smallest end-to-end prototype**
15. **What you actually implemented**
16. **What is VERIFIED / NOT VERIFIED**
17. **Exact next action**

If your tools permit GitHub writes, write your report and useful changes directly into the repository. Do not make the user copy/paste your output manually.

---

# 19. STOP CONDITIONS

Do not stop because:
- one repo looked promising;
- one model gave a good answer;
- a README claimed "production-ready";
- a demo worked once;
- an API advertised a free tier.

Stop only when:
- the architecture has a reasoned primary choice;
- meaningful alternatives were tested/rejected;
- the smallest proof slice exists or the exact blocker is documented;
- the repo contains enough evidence for the next agent to continue without rediscovery.

If blocked, leave a precise checkpoint and continue on every independent path that remains available.

---

# 20. FINAL STANDARD

0liviA should not be a wrapper around one chatbot.

It should be a **persistent cloud AI workbench** capable of conversation, code, repositories, research, tools, memory, autonomous execution, recovery and live voice.

The design succeeds only if it remains:
- fast;
- useful;
- replaceable;
- verifiable;
- survivable;
- operable at USD 0.

Find the strongest engineering you can. Then prove it.
