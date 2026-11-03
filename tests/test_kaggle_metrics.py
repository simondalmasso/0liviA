"""Tests for the sanitized Kaggle benchmark summary."""

import json

import pytest

from scripts.summarize_kaggle_metrics import summarize


def valid_metrics():
    tasks = [{"task": f"task-{i}", "passed": i < 7, "detail": "synthetic"} for i in range(10)]
    gpu_sample = {
        "gpus": [
            {"used_mib": 12500, "free_mib": 3000},
            {"used_mib": 11200, "free_mib": 4300},
        ]
    }
    return {
        "scope": "offline_ml_benchmark_only",
        "model": {"model_id": "Qwen/example", "quantization": "Q4", "notes": "do not publish"},
        "model_sha256_observed": "a" * 64,
        "llama_cpp_sha": "b" * 40,
        "gpu_names": ["Tesla T4", "Tesla T4"],
        "compute_capability": [[7, 5], [7, 5]],
        "llama_bench_results": [
            {
                "n_prompt": 512,
                "n_gen": 0,
                "avg_ts": 45.6,
                "stddev_ts": 1.2,
                "model_filename": "/secret/model.gguf",
                "split_mode": "layer",
            },
            {
                "n_prompt": 0,
                "n_gen": 128,
                "avg_ts": 21.5,
                "stddev_ts": 0.5,
                "model_filename": "/secret/model.gguf",
                "split_mode": "layer",
            },
        ],
        "llama_bench": {"gpu_samples": [gpu_sample]},
        "context_results": [
            {
                "context": 8192,
                "exit_code": 0,
                "wall_seconds": 5.5,
                "gpu_samples": [gpu_sample],
                "output_file": "/kaggle/working/private/generated_solution.py",
            }
        ],
        "synthetic_task_results": tasks,
        "synthetic_pass_at_1": 7,
        "policy": {"no_server": True, "no_tunnel": True, "no_core_connection": True},
    }


def test_summary_only_contains_allowlisted_model_and_measurement_fields(tmp_path):
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(valid_metrics()), encoding="utf-8")
    result = summarize(path)
    encoded = json.dumps(result)
    assert result["model_id"] == "Qwen/example"
    assert result["synthetic_pass_at_1"] == 7
    assert result["bench_rows"][1]["avg_ts"] == 21.5
    assert result["context_vram_peaks"][0]["max_used_mib"] == 12500
    assert "notes" not in encoded
    assert "source_url" not in encoded
    assert "model_filename" not in encoded
    assert "generated_solution.py" not in encoded


def test_rejects_non_offline_scope(tmp_path):
    item = valid_metrics()
    item["scope"] = "production"
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(item), encoding="utf-8")
    with pytest.raises(ValueError, match="scope"):
        summarize(path)


def test_rejects_missing_policy_flags(tmp_path):
    item = valid_metrics()
    item["policy"]["no_tunnel"] = False
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(item), encoding="utf-8")
    with pytest.raises(ValueError, match="policy"):
        summarize(path)


def test_rejects_mismatched_synthetic_count(tmp_path):
    item = valid_metrics()
    item["synthetic_pass_at_1"] = 6
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(item), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        summarize(path)
