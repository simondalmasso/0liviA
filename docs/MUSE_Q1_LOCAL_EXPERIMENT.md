# Muse Glimmer 30B Q1 — local experiment, NOT production

Verified open weights: Meta Muse Glimmer 30B Apache-2.0. Community compressed GGUF:
https://huggingface.co/NANI-Nithin/Muse-Glimmer-30B-GGUF/tree/main
Filename: Muse-Glimmer-30B-Q1_0.gguf; HF browser: 4.85GB decimal (~4.52GiB).
This is an **extreme** Q1 quantization of the real 30B weights, not a small Muse Lite model.
Quality is likely severely degraded. The 1.6GB DFlash is a drafter, not a standalone Muse.

## Owner-authorized, $0 local evaluation

1. Use an approved Linux machine with adequate free RAM (preliminary threshold: Q1 file size + 2GiB); install a trusted pinned build of llama.cpp supporting Muse. Never execute a remote installer blindly.
2. Inspect the source Hub repository and record its exact 40-hex commit; use the model card or a read-only call to HfApi.model_info(...).sha.
3. Read-only preflight: python scripts/muse_q1_local.py preflight
4. Download only if enough free RAM/disk and after explicit authorization:
   python scripts/muse_q1_local.py download --ack-download --revision YOUR_40_HEX_COMMIT
   Downloads the exact 4.85GB file only. Optional --sha256 VERIFIED_SHA256 for integrity.
5. Smoke real weights: python scripts/muse_q1_local.py smoke --binary /trusted/llama-cli
6. If real output, coding benchmarks, CPU and memory pass: python scripts/muse_q1_local.py serve --binary /trusted/llama-server

The server binds only 127.0.0.1:8098 with context 512 and no GPU usage, using model alias muse-glimmer-30b-q1-local. It runs in the foreground and is NOT installed or made persistent by this script. Never expose it publicly without authenticated proxy and real resource/quality certification.

## Existing Python Core interface (not enabled)

0liviA's existing OpenAI-compatible router supports local inference, so a separately running, verified llama-server can be configured on the **same** machine with this provider (operator action only):

    [{
      "name": "muse-glimmer-q1-local",
      "kind": "openai_compatible",
      "base_url": "http://127.0.0.1:8098/v1",
      "model": "muse-glimmer-30b-q1-local",
      "cost_mode": "local",
      "auth_mode": "none",
      "priority": 900,
      "capabilities": ["chat", "code"],
      "fallback_policy": "stop"
    }]

This is NOT automatically put in OLIVIA_PROVIDERS_JSON or the public UI. The short 512-token context cannot replace the full canonical Core until tested.

## What is and is not proven

- Local/offline unit tests verify GGUF magic, size, source naming, checksum logic, cgroup-aware memory, explicit download revision, and loopback-only command building. They DO NOT load real Muse.
- Actual sandbox available RAM was ~3.6GiB against ~6.5GiB required. Download was blocked; no GPU or Hugging Face egress available.
- The owner's Windows PC reported 8GB total but below 1GB available when read-only audited. It must not be used as a production Muse runtime. OCI E2 Micro 1GB is too small.
- An actually free OCI A1 12GB instance could trial Q1 after issue #43 SSH/quotas are certified, but CPU latency, quality and model architecture compatibility are unverified.
- All calls to paid providers, NVIDIA trial for production, automatic downloads, enabling in Cloudflare, and secret exposure remain disabled.
- Never advertise Muse as active before live pinned-model inference with nonempty result and budgeted runtime.
