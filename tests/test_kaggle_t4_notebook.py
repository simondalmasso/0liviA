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


def test_notebook_is_valid_jupyter_and_all_code_cells_parse():
    cells = _cells()
    assert len(cells) == 12
    for index, cell in enumerate(cells):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        ast.parse(source, filename=f"{NOTEBOOK.name}:cell-{index + 1}")


def test_notebook_requires_two_real_t4_gpus_and_checks_model_hash():
    source = "\n".join(
        "".join(cell["source"])
        for cell in _cells()
        if cell["cell_type"] == "code"
    )
    assert "torch.cuda.device_count() == 2" in source
    assert '"T4" in n' in source
    assert "compute_capability" in source
    assert "sha256_file" in source
    assert "actual_sha == expected_sha" in source


def test_notebook_has_ten_synthetic_tasks_and_exports_metrics():
    source = "\n".join(
        "".join(cell["source"])
        for cell in _cells()
        if cell["cell_type"] == "code"
    )
    assert "SYNTHETIC_PASS_AT_1" in source
    assert "passed_count" in source
    assert '"metrics.json"' in source


def test_notebook_does_not_start_a_server_or_tunnel():
    source = "\n".join(
        "".join(cell["source"])
        for cell in _cells()
        if cell["cell_type"] == "code"
    ).lower()
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
