from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ephemeral_checkpoint.py"


def run(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=True,
        text=True,
        capture_output=True,
    )


def test_ephemeral_checkpoint_round_trip_and_excludes_secrets(tmp_path: Path):
    source = tmp_path / "work"
    source.mkdir()
    (source / "result.txt").write_text("durable", encoding="utf-8")
    (source / ".env").write_text("SECRET=do-not-copy", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("git-secret", encoding="utf-8")
    nested = source / "artifacts"
    nested.mkdir()
    (nested / "metrics.json").write_text('{"score": 1}', encoding="utf-8")

    persistent = tmp_path / "data" / "0livia-checkpoints"
    created = run(
        "--persistent-root",
        str(persistent),
        "--name",
        "job-42",
        "--checkpoint",
        str(source),
    )
    manifest = json.loads(created.stdout)
    assert manifest["files"] == 2
    assert manifest["bytes"] > 0

    snapshot = persistent / "job-42"
    assert (snapshot / "result.txt").read_text(encoding="utf-8") == "durable"
    assert not (snapshot / ".env").exists()
    assert not (snapshot / ".git").exists()

    destination = tmp_path / "restore"
    restored = run(
        "--persistent-root",
        str(persistent),
        "--name",
        "job-42",
        "--restore",
        str(destination),
    )
    restored_manifest = json.loads(restored.stdout)
    assert restored_manifest["name"] == "job-42"
    assert (destination / "result.txt").read_text(encoding="utf-8") == "durable"
    assert (destination / "artifacts" / "metrics.json").exists()


def test_ephemeral_checkpoint_fails_closed_on_size_limit(tmp_path: Path):
    source = tmp_path / "work"
    source.mkdir()
    (source / "large.bin").write_bytes(b"x" * 64)

    persistent = tmp_path / "data"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--persistent-root",
            str(persistent),
            "--name",
            "too-large",
            "--max-bytes",
            "32",
            "--checkpoint",
            str(source),
        ],
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert not (persistent / "too-large").exists()
