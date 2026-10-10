"""Offline security and resource tests; never download weights or run a model in CI."""
import importlib.util
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "muse_q1_local.py"
spec = importlib.util.spec_from_file_location("muse_q1_local", SOURCE)
muse = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = muse
spec.loader.exec_module(muse)


def fake_gguf(tmp_path, *, header=b"GGUF", size=muse.ESTIMATED_BYTES):
    path = tmp_path / muse.MODEL_FILE
    with path.open("wb") as stream:
        stream.write(header)
        stream.truncate(size)  # Sparse file, no multi-GB disk allocation
    return path


def test_valid_sparse_gguf_passes_with_sufficient_memory(tmp_path):
    f = fake_gguf(tmp_path)
    r = muse.inspect(f, available=10 * 1024**3, disk_free=12 * 1024**3)
    assert r.can_run
    assert r.ram_required_bytes == muse.ESTIMATED_BYTES + muse.MIN_HEADROOM_BYTES
    assert r.model == "muse-glimmer-30b-q1-local"


def test_one_gib_micro_rejected(tmp_path):
    r = muse.inspect(fake_gguf(tmp_path), available=1024**3)
    assert not r.can_run
    assert "insufficient_available_memory" in r.reasons


def test_missing_truncated_and_forged_files_rejected(tmp_path):
    truncated = fake_gguf(tmp_path, size=1024)
    assert "unexpected_model_size" in muse.inspect(truncated, available=10**10).reasons
    fake = fake_gguf(tmp_path, header=b"FAKE")
    assert "invalid_gguf_header" in muse.inspect(fake, available=10**10).reasons
    fake.unlink()
    assert "model_file_missing" in muse.inspect(fake, available=10**10).reasons


def test_commands_are_local_and_bounded(tmp_path):
    weights = tmp_path / muse.MODEL_FILE
    binary = tmp_path / "llama-server"
    cmd = muse.command(binary, weights, "serve")
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert cmd[cmd.index("-c") + 1] == "512"
    assert cmd[cmd.index("-ngl") + 1] == "0"
    assert cmd[-1] == muse.MODEL_ID
    assert muse.command(binary, weights, "smoke")[-2] == "-p"
    with pytest.raises(ValueError):
        muse.command(binary, weights, "serve", 80)


def test_unpinned_download_does_not_access_network(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "tool", "download", "--model-file", str(tmp_path / muse.MODEL_FILE),
        "--ack-download", "--revision", "main",
    ])
    assert muse.main() == 2
    assert "40-hex Hub revision" in capsys.readouterr().err


def test_missing_weights_never_start_subprocess(tmp_path, monkeypatch):
    fake_binary = tmp_path / "llama-cli"
    fake_binary.write_text("binary")
    monkeypatch.setattr(sys, "argv", [
        "tool", "smoke", "--binary", str(fake_binary),
        "--model-file", str(tmp_path / muse.MODEL_FILE),
    ])
    monkeypatch.setattr(muse.subprocess, "run", lambda *a, **k: (
        (_ for _ in ()).throw(AssertionError("should never execute"))
    ))
    assert muse.main() == 2


def test_checksum_streaming_and_invalid_checksum(tmp_path):
    test = tmp_path / "data.bin"
    test.write_bytes(b"test")
    digest = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    assert muse.verify_hash(test, digest)
    assert not muse.verify_hash(test, "0" * 64)
    with pytest.raises(ValueError):
        muse.verify_hash(test, "invalid")
