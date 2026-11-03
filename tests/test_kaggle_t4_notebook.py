"""Static safety and syntax checks for the offline Kaggle notebook template."""

import ast
import json
from pathlib import Path


NOTEBOOK = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "kaggle_t4"
    / "0livia_t4x2_offline_benchmark.ipynb"
)


def _cells():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    return notebook["cells"]


def _source():
    return "\\n".join(
        "".join(cell["source"])
        for cell in _cells()
        if cell["cell_type"] == "code"
    )


def test_notebook_is_valid_jupyter_and_all_code_cells_parse():
    cells = _cells()
    assert len(cells) == 12
    for index, cell in enumerate(cells):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        ast.parse(source, filename=f"{NOTEBOOK.name}:cell-{index + 1}")


def test_notebook_requires_two_real_t4_gpus_and_checks_model_hash():
    source = _source()
    assert "torch.cuda.device_count() == 2" in source
    assert '"T4" in n' in source
    assert "compute_capability" in source
    assert "sha256_file" in source
    assert "actual_sha == expected_sha" in source
    assert '"512,2048,4096,8192"' in source


def test_notebook_has_ten_synthetic_tasks_and_exports_metrics():
    source = _source()
    assert "SYNTHETIC_PASS_AT_1" in source
    assert "passed_count" in source
    assert '"metrics.json"' in source


def test_notebook_samples_vram_and_separates_model_output_from_logs():
    source = _source()
    assert "def run_monitored(" in source
    assert "gpu_samples" in source
    assert "stderr_file" in source
    assert "llama-bench.stderr.txt" in source


def test_generated_model_code_runs_in_restricted_subprocess():
    source = _source()
    assert "resource.RLIMIT_CPU" in source
    assert "resource.RLIMIT_AS" in source
    assert "Attribute access is forbidden" in source
    assert "Only direct function calls are allowed" in source
    assert '"ord": ord' in source and '"chr": chr' in source
    assert '[sys.executable, "-I", "-S"' in source


def test_notebook_does_not_start_a_server_or_tunnel():
    source = _source().lower()
    forbidden = (
        "llama-server",
        "cloudflared",
        "ngrok",
        "uvicorn",
        "fastapi",
        "http.server",
        "socketserver",
    )
    assert not [token for token in forbidden if token in source]
