# Pocket Coding Models — source-backed screening (2026-10-09)

Goal: genuine no-overage, low-memory **coding assistance**, not a fabricated frontier model on an OCI E2 Micro (~1 GiB). All models below are candidate benchmarks; none were downloaded, loaded, tested on OCI or connected to the production router.

## Evidence matrix

| Candidate | Publisher / weights | License | Exact public evidence | Decision |
|---|---|---|---|---|
| **Qwen2.5-Coder-0.5B-Instruct** | [official model](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct) | Apache 2.0 | [bartowski GGUF Q4_K_M 398 MB](https://huggingface.co/bartowski/Qwen2.5-Coder-0.5B-Instruct-GGUF/tree/main); [Qwen technical report](https://arxiv.org/html/2409.12186v2) gives **HumanEval 28.0 for BASE 0.5B**, not the Instruct quant. | **Highest priority for isolated pocket-coder CPU benchmark**; focused code suggestions/fixes only. |
| **Qwen2.5-Coder-1.5B-Instruct** | [official model](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct) | Apache 2.0 | Report: **43.9 HumanEval BASE 1.5B**, not quant. Minimum weight storage alone around 1 GB at Q4, **too tight** for ~1 GiB host with KV cache and OS. | Benchmark on CPU-4C-16G / independent >= 4GB box, not OCI Micro. |
| **Qwen3.5-0.8B** | [official model](https://huggingface.co/Qwen/Qwen3.5-0.8B) | Apache 2.0 | Native image+text, multilingual (201 languages/dialects per Qwen). [Quantizations](https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF) need architecture support; published 1GB download variants cannot prove runtime <=1GB. | Multilingual tool-intent challenger; not coding winner without head-to-head. |
| **LFM2.5-1.2B-Instruct** | [official model](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct) | LFM Open License v1.0 | Edge-friendly hybrid; model-card BFCLv3 49.12 and IFEval 86.23 are vendor-reported, **not coding repo completion** scores. | Evaluate only if licensing, reproducibility and memory permit. |
| **Muse Glimmer 30B Q4** | [official guide](https://dev.meta.ai/models/muse-glimmer) | Apache 2.0 | ~16.8GB GGUF, ~60GB BF16; 1.6GB DFlash drafter is not standalone. | Not a pocket model; separate GPU research only. |

### GPU- and account-independent acceptance suite

To avoid misleading results from marketing benchmarks, evaluate each candidate against **the same 24 offline prompts**:
- 8 micro-edit tasks in Python/JS/TypeScript with expected unit tests; no repository secrets
- 6 single-function bug repairs with a known regression test
- 4 explanations of tricky code in es-AR with rubric
- 4 structured tool-intent JSON outputs (no tools executed)
- 2 adversarial prompt-injection refusals from a fake repository README

Record model commit and quant checksum, tokenizer/chat template, llama.cpp revision, context tokens, free memory, peak RSS, TTFT and throughput, test-pass percentage, language compliance, malformed JSON and cost. Use temperature 0, 1024 input tokens maximum (or model-compatible), 128 output token cap; repeated runs for consistency. Use **disposable synthetic** code only.

A pass at sub-1GB must be measured on the actual host with:
- the 0liviA Python Core + SQLite resident,
- baseline free memory measured right before loading,
- llama.cpp buffers and **KV cache included** in peak RSS,
- 3 repeated trials without OOM or swap thrash,
- reasonable latency (target <5s for 16 tokens only if host supports it),
- tests verifying no history/memory secret egress and no side effects.

**Do not** default to local inference on OCI Micro. Test only via explicitly authorized idle resources; keep the proven free cloud inference route as primary when permitted.

## Automation of InternAI seven-day sessions — legitimate boundaries

[Official developer-machine docs](https://discovery.intern-ai.org.cn/docs/en/workbench/developer/) state a **maximum single start duration of 7×24 hours**, not an account expiry. Stopped machines can be restarted by setting a new duration; the provider charges **compute points during running**. Persist only under `/data`: stopping wipes other files. A user may request more points but obtaining a new 168-hour session does **not** refill quota automatically.

Safe automation, once there is a published authorized management API:
1. Watch remaining points and `ends_at` from official API.
2. Checkpoint experiment/code in `/data` and optionally Git without any keys or private user data.
3. Stop before expiry to preserve data and prevent point depletion.
4. Only restart on a **positive provider entitlement+quota+cost verification**, explicitly authorized project, and an operator-set maximum experiment budget; never by creating duplicate accounts, rotating credentials, or bypassing restrictions.
5. If no supported API or insufficient points, **fail closed** and ask owner for a manual restart.

No official public management API was verified at this review. No automatic restart loop is installed. Treat InternAI as temporary bench lab, **not** the cloud Core host.

## MiniAGI — inspect rather than blindly fork

[muellerberndt/mini-agi](https://github.com/muellerberndt/mini-agi) is MIT but the latest observed commit is June 2023; it uses legacy OpenAI SDK + unrestricted `execute_python` (built-in `exec`) and `execute_shell`. Its optional `ENABLE_CRITIC=true` uses additional model requests and does not prove actions happened (its own README includes fabricated success examples). Do not vendor the framework or run it against user repos/secrets.

**Adopted concept:** separate a model's self-reported goal completion from externally verifiable results. `olivia/agent_outcome.py` now accepts `succeeded` only with a real GitHub run ID and successful conclusion; absent, malformed or unknown receipts fail closed. Adds **zero** inference calls, no shell access, and no extra dependencies. It is independent of model honesty.

## OpenMuse and OpenShell implementation notes

- OpenMuse's transactional lease pattern already entered SQLite via PR #77. This change actually **uses** `claim_queued_job`, `checkpoint_leased_job` and `handoff_leased_job` during existing coding/browser dispatches. All remote retries remain disabled and remote run IDs are verified before showing success. No CopilotKit Intelligence cloud storage is imported.
- OpenShell is available as an optional **readiness probe** in `olivia/openshell.py`, a side-effect-free CLI report in `scripts/check_openshell.py` and a narrow GitHub REST GET-only policy in `deploy/openshell/olivia-readonly-policy.yaml`. It does **not** boot/install a gateway or grant any production execution. Pin releases and run OpenShell's actual policy prover and negative sandbox tests after host and zero-cost capability are verified.
- OpenShell initial 4096 MiB screening heuristic is conservative, **not a published minimum**. Kernel Landlock/seccomp, transport, host isolation, credentials broker and rollback still require real test. Do not construe a passing JSON preflight as host attestation.

### References
- https://arxiv.org/html/2409.12186v2
- https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct
- https://huggingface.co/bartowski/Qwen2.5-Coder-0.5B-Instruct-GGUF/tree/main
- https://huggingface.co/Qwen/Qwen3.5-0.8B
- https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct
- https://github.com/NVIDIA/OpenShell
- https://github.com/CopilotKit/OpenMuse
- https://github.com/muellerberndt/mini-agi
- https://discovery.intern-ai.org.cn/docs/en/workbench/developer/
