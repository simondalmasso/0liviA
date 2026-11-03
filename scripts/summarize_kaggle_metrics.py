#!/usr/bin/env python3
"""Validate and summarize the synthetic-only Kaggle benchmark output without publishing raw metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _gpu_peaks(samples: Any) -> list[dict[str, int]]:
    if not isinstance(samples, list):
        return []
    peaks: list[dict[str, int]] = []
    for gpu_index in range(2):
        used_values: list[int] = []
        free_values: list[int] = []
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            gpus = sample.get("gpus")
            if not isinstance(gpus, list) or len(gpus) != 2:
                continue
            gpu = gpus[gpu_index]
            if not isinstance(gpu, dict):
                continue
            if isinstance(gpu.get("used_mib"), int):
                used_values.append(gpu["used_mib"])
            if isinstance(gpu.get("free_mib"), int):
                free_values.append(gpu["free_mib"])
        if used_values or free_values:
            peaks.append(
                {
                    "gpu_index": gpu_index,
                    "max_used_mib": max(used_values) if used_values else -1,
                    "min_free_mib": min(free_values) if free_values else -1,
                }
            )
    return peaks


def _bench_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        rows = value.get("results")
        if isinstance(rows, list):
            value = rows
    if not isinstance(value, list):
        return []

    allowed = (
        "n_prompt",
        "n_gen",
        "n_batch",
        "avg_ts",
        "stddev_ts",
        "split_mode",
        "n_gpu_layers",
        "type_k",
        "type_v",
    )
    output = []
    for row in value:
        if not isinstance(row, dict):
            continue
        safe = {
            key: row[key]
            for key in allowed
            if isinstance(row.get(key), (str, int, float)) and not isinstance(row.get(key), bool)
        }
        if "avg_ts" in safe:
            output.append(safe)
    return output


def summarize(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"metrics.json is unreadable: {exc}") from None
    if not isinstance(payload, dict):
        raise ValueError("metrics.json root must be an object")

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
    if not isinstance(digest, str) or len(digest) != 64 or any(
        c not in "0123456789abcdef" for c in digest.lower()
    ):
        raise ValueError("observed model SHA-256 is invalid")

    gpu_names = payload.get("gpu_names")
    compute = payload.get("compute_capability")
    if not isinstance(gpu_names, list) or len(gpu_names) != 2 or not all(
        "T4" in str(item) for item in gpu_names
    ):
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

    bench = payload.get("llama_bench")
    bench_samples = bench.get("gpu_samples") if isinstance(bench, dict) else []
    context_summaries = []
    all_context_samples = []
    for item in contexts:
        if not isinstance(item, dict):
            continue
        samples = item.get("gpu_samples")
        all_context_samples.extend(samples if isinstance(samples, list) else [])
        context_summaries.append(
            {
                "context": item.get("context"),
                "exit_code": item.get("exit_code"),
                "wall_seconds": item.get("wall_seconds"),
                "vram_peaks": _gpu_peaks(samples),
            }
        )

    return {
        "model_id": model_id,
        "quantization": quantization if isinstance(quantization, str) else "unspecified",
        "model_sha256": digest.lower(),
        "llama_cpp_sha": payload.get("llama_cpp_sha"),
        "gpu_names": gpu_names,
        "compute_capability": compute,
        "bench_rows": _bench_rows(payload.get("llama_bench_results")),
        "bench_vram_peaks": _gpu_peaks(bench_samples),
        "contexts": context_summaries,
        "context_vram_peaks": _gpu_peaks(all_context_samples),
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
        "### Prefill/decode measurements",
        "",
        "| Prompt tokens | Generated tokens | tok/s | stddev tok/s | Split |",
        "|---:|---:|---:|---:|---|",
    ]
    for item in result["bench_rows"]:
        lines.append(
            f"| {item.get('n_prompt', 0)} | {item.get('n_gen', 0)} | "
            f"{item.get('avg_ts', 'n/a')} | {item.get('stddev_ts', 'n/a')} | "
            f"{item.get('split_mode', 'unspecified')} |"
        )
    if not result["bench_rows"]:
        lines.append("| No parseable llama-bench rows | — | — | — | — |")

    lines.extend(["", "### Context runs", "", "| Context | Exit | Wall time |", "|---:|---:|---:|"])
    for item in result["contexts"]:
        lines.append(
            f"| {item['context']} | {item['exit_code']} | {item['wall_seconds']} s |"
        )

    lines.extend(
        [
            "",
            "### VRAM sampling",
            "",
            "Peak values are maxima from 2-second samples, not guaranteed hardware peaks.",
            "",
            "| GPU | Max used MiB | Min free MiB |",
            "|---:|---:|---:|",
        ]
    )
    vram = result["context_vram_peaks"] or result["bench_vram_peaks"]
    for item in vram:
        lines.append(f"| {item['gpu_index']} | {item['max_used_mib']} | {item['min_free_mib']} |")
    if not vram:
        lines.append("| No samples captured | — | — |")

    args.summary_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
