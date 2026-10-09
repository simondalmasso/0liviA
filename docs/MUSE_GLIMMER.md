# Muse Glimmer — optional challenger (not production)

## Verified upstream artifacts (2026-10-09)

Meta released **Muse Glimmer 30B** as an Apache-2.0 open-weight model. It can be downloaded, quantized or fine-tuned lawfully under the applicable Apache license and Meta's usage policy. There is **no separately verified general-purpose official 1B/3B/8B Muse Lite**.

| Artifact | Size | Role |
| --- | ---: | --- |
| [BF16](https://huggingface.co/meta-models/Muse-Glimmer-30B) | ~60 GB | Main model |
| [Official GGUF Q4 K-Quant](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF) | ~16.8 GB | Main model, text-only |
| Official GGUF Q4 dynamic | ~19.7 GB | Higher fidelity |
| Official GGUF DFlash | ~1.6 GB | **Draft model only**, not a standalone assistant |
| [Community GGUF IQ2_M](https://huggingface.co/NANI-Nithin/Muse-Glimmer-30B-GGUF) | ~9.17 GB | Extreme third-party quantization, unverified |
| Community GGUF Q1_0 | ~4.52 GB | Experimental, substantial quality loss |

The 3B DFlash `meta-models/Muse-Glimmer-30B-assistant` has no standalone input/output embeddings and depends on the 30B target model. Do **not** advertise this as a "Muse Lite" chatbot.

## Optional offline download — do not run on Cloudflare / OCI Micro

If you have a host with ample storage, memory and a supported llama.cpp build (**b10353 or later**), an operator can explicitly download the **official** ~16.8 GB GGUF:

```bash
python -m pip install -U huggingface_hub
hf download meta-models/Muse-Glimmer-30B-GGUF \
  --include "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf" \
  --local-dir ./muse-glimmer
```

For image input, the optional official `mmproj-Muse-Glimmer-30B-Q4_K_M.gguf` adds roughly 1.4 GB. Quantization reduces weight storage, not parameter count or the memory needed for the KV cache. A ~1 GB RAM Oracle E2.1.Micro cannot serve these variants, and the reference 12 GB RAM A1 is also not a safe production fit for the official Q4 build. Do not persist multi-gigabyte weights in GitHub or spin up a paid GPU under the USD 0 contract.

## NVIDIA prototype — manual and **not** for production

NVIDIA hosts `meta/muse-glimmer-30b` on the prototype API `https://integrate.api.nvidia.com/v1/chat/completions`, but [API Trial Terms §§1.2 and 1.4](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf) bar production use without a separate subscription. The existing workflow `.github/workflows/nvidia-nim-eval.yml` now accepts `model: muse-glimmer`; it remains manual, requires an explicit trial acknowledgement **and** `NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED=1`, sends exactly one harmless canned prompt, enforces 64 output tokens, does not retry, does not log raw completions, and never inserts the key into Cloudflare or the product UI.

The gate is an **account-level owner assertion**, not a substitute for a provider billing audit. Do not set it without proof that the NVIDIA trial cannot charge this account and the request is permitted.

When a future independently verified $0 production-capable inference host exists, configure Muse through the existing OpenAI-compatible provider interface (exact endpoint/model); never mark it ready based on the local weights or NVIDIA trial alone.

## Source evidence

- [Meta Muse Glimmer official overview](https://dev.meta.ai/models/muse-glimmer)
- [Meta official downloads](https://dev.meta.ai/docs/muse-glimmer/get-the-model)
- [Meta quantization instructions](https://dev.meta.ai/docs/muse-glimmer/quantization)
- [Meta speculative drafter](https://dev.meta.ai/docs/muse-glimmer/spec-decode)
- [NVIDIA Muse prototype endpoint](https://build.nvidia.com/meta/muse-glimmer-30b/build)
- [NVIDIA API trial terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf)
