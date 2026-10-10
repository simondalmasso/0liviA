#!/usr/bin/env python3
"""Fail-closed local runner for genuine Muse Glimmer 30B Q1_0 GGUF.

Q1 is an existing experimental community quantization, NOT a 1B model or a
distilled "Muse Lite". Does not use NVIDIA, Vercel, a paid API or user data.
External download requires a pinned Hub revision and explicit opt-in.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = "NANI-Nithin/Muse-Glimmer-30B-GGUF"
MODEL_FILE = "Muse-Glimmer-30B-Q1_0.gguf"
MODEL_ID = "muse-glimmer-30b-q1-local"
LOWER_BYTES = 4_600_000_000
UPPER_BYTES = 5_200_000_000
ESTIMATED_BYTES = 4_850_000_000
MIN_HEADROOM_BYTES = 2 * 1024 ** 3
MIN_DOWNLOAD_HEADROOM = 1024 ** 3
LOCAL_HOST = "127.0.0.1"


@dataclass(frozen=True)
class Readiness:
    source: str
    model: str
    platform: str
    ram_available_bytes: int
    ram_required_bytes: int
    disk_free_bytes: int
    file_exists: bool
    file_size_bytes: int | None
    gguf_magic: bool
    can_run: bool
    reasons: tuple[str, ...]


def memory_available_bytes() -> int:
    """Available RAM, bounded by a Linux cgroup v2 memory ceiling if present."""
    if not sys.platform.startswith("linux"):
        return 0
    try:
        meminfo = Path("/proc/meminfo").read_text(encoding="ascii")
        line = next(s for s in meminfo.splitlines() if s.startswith("MemAvailable:"))
        available = int(line.split()[1]) * 1024
        limit = Path("/sys/fs/cgroup/memory.max")
        used = Path("/sys/fs/cgroup/memory.current")
        if limit.exists() and used.exists():
            maximum = limit.read_text(encoding="ascii").strip()
            if maximum != "max":
                available = min(
                    available,
                    max(0, int(maximum) - int(used.read_text(encoding="ascii"))),
                )
        return max(0, available)
    except (OSError, ValueError, IndexError, StopIteration):
        return 0


def inspect(path: Path, *, available: int | None = None, disk_free: int | None = None) -> Readiness:
    model_file = path.resolve()
    exists = model_file.is_file()
    size = model_file.stat().st_size if exists else None
    gguf = False
    if exists and LOWER_BYTES <= size <= UPPER_BYTES:
        with model_file.open("rb") as stream:
            gguf = stream.read(4) == b"GGUF"
    if available is None:
        available = memory_available_bytes()
    if disk_free is None:
        parent = model_file.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        disk_free = shutil.disk_usage(parent).free
    required = (size or ESTIMATED_BYTES) + MIN_HEADROOM_BYTES
    reasons: list[str] = []
    if not sys.platform.startswith("linux"):
        reasons.append("linux_host_required")
    if available < required:
        reasons.append("insufficient_available_memory")
    if not exists:
        reasons.append("model_file_missing")
    elif not (LOWER_BYTES <= size <= UPPER_BYTES):
        reasons.append("unexpected_model_size")
    elif not gguf:
        reasons.append("invalid_gguf_header")
    return Readiness(
        source=REPO,
        model=MODEL_ID,
        platform=sys.platform,
        ram_available_bytes=available,
        ram_required_bytes=required,
        disk_free_bytes=disk_free,
        file_exists=exists,
        file_size_bytes=size,
        gguf_magic=gguf,
        can_run=not reasons,
        reasons=tuple(reasons),
    )


def command(binary: Path, weights: Path, mode: str, port: int = 8098) -> list[str]:
    """No shell and no public listener; bound context/output and CPU threads."""
    prefix = [
        str(binary.resolve()), "-m", str(weights.resolve()),
        "-c", "512", "-t", "2", "-ngl", "0",
    ]
    if mode == "smoke":
        return prefix + [
            "-n", "32", "-p",
            "Respondé con MUSE seguido de guion bajo y OK, sin nada más.",
        ]
    if mode == "serve":
        if not 1024 <= port <= 65535:
            raise ValueError("invalid_local_port")
        return prefix + [
            "--host", LOCAL_HOST, "--port", str(port), "--alias", MODEL_ID,
        ]
    raise ValueError("invalid_mode")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=("preflight", "download", "smoke", "serve")
    )
    parser.add_argument(
        "--model-file", type=Path,
        default=Path.home() / "muse-models" / MODEL_FILE,
    )
    parser.add_argument(
        "--binary", type=Path, default=None,
        help="Trusted preinstalled llama-cli or llama-server executable",
    )
    parser.add_argument(
        "--revision", default="", help="Exact 40-hex Hub commit for download",
    )
    parser.add_argument("--ack-download", action="store_true")
    parser.add_argument(
        "--sha256", default="", help="Optional expected full SHA256",
    )
    parser.add_argument("--port", type=int, default=8098)
    return parser.parse_args()


def verify_hash(path: Path, expected: str) -> bool:
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("sha256 must be 64 lowercase hex digits")
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 ** 2), b""):
            checksum.update(block)
    return checksum.hexdigest() == expected


def main() -> int:
    args = parse_args()
    state = inspect(args.model_file)
    if args.operation == "preflight":
        print(json.dumps(asdict(state), sort_keys=True))
        return 0 if state.can_run else 2

    if args.operation == "download":
        if not args.ack_download:
            print("BLOCKED: --ack-download required", file=sys.stderr)
            return 2
        if not re.fullmatch(r"[a-f0-9]{40}", args.revision):
            print("BLOCKED: exact 40-hex Hub revision required", file=sys.stderr)
            return 2
        if state.ram_available_bytes < ESTIMATED_BYTES + MIN_HEADROOM_BYTES:
            print("BLOCKED: insufficient RAM to serve Muse", file=sys.stderr)
            return 2
        if state.disk_free_bytes < ESTIMATED_BYTES + MIN_DOWNLOAD_HEADROOM:
            print("BLOCKED: insufficient disk space", file=sys.stderr)
            return 2
        try:
            from huggingface_hub import hf_hub_download
        except ImportError:
            print("BLOCKED: install huggingface_hub explicitly", file=sys.stderr)
            return 2
        args.model_file.parent.mkdir(parents=True, exist_ok=True)
        location = hf_hub_download(
            REPO, MODEL_FILE, revision=args.revision,
            local_dir=str(args.model_file.parent),
        )
        downloaded = inspect(Path(location))
        if not downloaded.can_run:
            print("BLOCKED: model resource or file validation failed", file=sys.stderr)
            return 2
        if args.sha256 and not verify_hash(Path(location), args.sha256):
            print("BLOCKED: SHA256 mismatch", file=sys.stderr)
            return 2
        print(json.dumps({
            "downloaded": True, "file": MODEL_FILE,
            "revision": args.revision, "ready": True,
        }))
        return 0

    if not state.can_run:
        print(json.dumps(asdict(state), sort_keys=True), file=sys.stderr)
        return 2
    if args.sha256 and not verify_hash(args.model_file, args.sha256):
        print("BLOCKED: SHA256 mismatch", file=sys.stderr)
        return 2
    if not args.binary or not args.binary.is_file():
        print("BLOCKED: trusted llama.cpp executable missing", file=sys.stderr)
        return 2
    cmd = command(args.binary, args.model_file, args.operation, args.port)
    if args.operation == "serve":
        print(json.dumps({
            "mode": "serve", "model": MODEL_ID,
            "host": LOCAL_HOST, "port": args.port,
        }), flush=True)
        return subprocess.call(cmd)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=180, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print(json.dumps({
            "status": "FAILED", "reason": "model_start_or_timeout",
        }))
        return 1
    passed = result.returncode == 0 and "MUSE_OK" in result.stdout
    print(json.dumps({
        "status": "PASS" if passed else "FAILED",
        "model": MODEL_ID, "source": REPO, "context": 512,
        "n_predict": 32,
    }))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
