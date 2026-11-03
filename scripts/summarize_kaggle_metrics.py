#!/usr/bin/env python3
"""Validate and summarize the synthetic-only Kaggle benchmark output without publishing raw metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def summarize(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"metrics.json is unreadable: {exc}") from None

    if payload.get("scope") != "offline_ml_benchmark_only":
        raise ValueError("unexpected benchmark scope")
    policy = payload.get("policy")
    if not isinstance(policy, dict) or not all(
        policy.get(key) is True for key in ("no_server", "no_tunnel", "no_core_connection")
    ):
        raise ValueError("offline-only policy flags are missing or false")

    model = payload.get("model")
    model_id = model.get("model_id") if isinstance(model, dict) else None
    quantization = model.get("quantization") if isinstance(model, dict) else None
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model identifier is missing")

    digest = payload.get("model_sha256_observed")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        raise ValueError("observed model SHA-256 is invalid")

    gpu_names = payload.get("gpu_names")
    compute = payload.get("compute_capability")
    if not isinstance(gpu_names, list) or len(gpu_names) != 2 or not all("T4" in str(x) for x in gpu_names):
        raise ValueError("metrics do not identify exactly two T4 GPUs")
    if not isinstance(compute, list) or compute != [[7, 5], [7, 5]]:
        raise ValueError("metrics do not identify two SM 7.5 devices")

    tasks = payload.get("synthetic_task_results")
    if not isinstance(tasks, list) or len(tasks) != 10:
        raise ValueError("expected exactly ten synthetic task results")
    passed = sum(1 for item in tasks if isinstance(item, dict) and item.get("passed") is True)
    if payload.get("synthetic_pass_at_1") != passed:
        raise ValueError("synthetic pass@1 count does not match task results")

    contexts = payload.get("context_results")
    if not isinstance(contexts, list):
        raise ValueError("context results are missing")

    # Exclude arbitrary manifest notes, source URLs, file names, output text and stderr.
    return {
        "model_id": model_id,
        "quantization": quantization if isinstance(quantization, str) else "unspecified",
        "model_sha256": digest.lower(),
        "llama_cpp_sha": payload.get("llama_cpp_sha"),
        "gpu_names": gpu_names,
        "compute_capability": compute,
        "contexts": [
            {
                "context": item.get("context"),
                "exit_code": item.get("exit_code"),
                "wall_seconds": item.get("wall_seconds"),
            }
            for item in contexts
            if isinstance(item, dict)
        ],
        "synthetic_pass_at_1": passed,
        "synthetic_task_count": len(tasks),
        "scope": "offline_ml_benchmark_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--summary-file", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = summarize(args.metrics)
    except ValueError as exc:
        parser.exit(2, f"metrics validation failed: {exc}\n")

    lines = [
        "## Kaggle T4×2 benchmark result",
        "",
        f"- Model: `{result['model_id']}`",
        f"- Quantization: `{result['quantization']}`",
        f"- Model SHA-256: `{result['model_sha256']}`",
        f"- llama.cpp: `{result['llama_cpp_sha']}`",
        f"- GPUs: {', '.join(result['gpu_names'])} (SM 7.5 each)",
        f"- Synthetic checks: **{result['synthetic_pass_at_1']}/10**",
        "- Scope: private/offline synthetic evaluation only",
        "",
        "| Context | Exit | Wall time |",
        "|---:|---:|---:|",
    ]
    for item in result["contexts"]:
        lines.append(
            f"| {item['context']} | {item['exit_code']} | {item['wall_seconds']} s |"
        )
    args.summary_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
