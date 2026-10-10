#!/usr/bin/env python3
"""Portable checkpoint helper for ephemeral workers.

Copies a bounded workspace snapshot into persistent storage (for example
Intern InkStone /data) without requiring provider APIs or credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".env",
    ".env.local",
    "secrets",
}


def _safe_name(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in "-_.")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("invalid checkpoint name")
    return cleaned[:96]


def _should_skip(path: Path, source: Path) -> bool:
    rel = path.relative_to(source)
    return any(part in DEFAULT_EXCLUDES for part in rel.parts)


def _copy_regular_tree(source: Path, destination: Path, max_bytes: int) -> tuple[int, int]:
    files = 0
    total = 0
    for path in source.rglob("*"):
        if _should_skip(path, source):
            continue
        if path.is_symlink():
            continue
        rel = path.relative_to(source)
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        if total + size > max_bytes:
            raise ValueError("checkpoint exceeds max-bytes")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        files += 1
        total += size
    return files, total


def checkpoint(source: Path, persistent_root: Path, name: str, max_bytes: int) -> dict[str, object]:
    source = source.resolve()
    persistent_root = persistent_root.resolve()
    if not source.is_dir():
        raise ValueError("source must be a directory")
    persistent_root.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(name)
    final = persistent_root / safe
    with tempfile.TemporaryDirectory(prefix=f".{safe}.", dir=persistent_root) as tmp:
        tmp_path = Path(tmp) / "snapshot"
        tmp_path.mkdir()
        files, total = _copy_regular_tree(source, tmp_path, max_bytes)
        manifest = {
            "name": safe,
            "created_at": int(time.time()),
            "files": files,
            "bytes": total,
            "source_basename": source.name,
        }
        (tmp_path / ".olivia-checkpoint.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        backup = persistent_root / f".{safe}.previous"
        if backup.exists():
            shutil.rmtree(backup)
        if final.exists():
            final.replace(backup)
        tmp_path.replace(final)
        if backup.exists():
            shutil.rmtree(backup)
    return manifest


def restore(persistent_root: Path, name: str, destination: Path) -> dict[str, object]:
    persistent_root = persistent_root.resolve()
    source = persistent_root / _safe_name(name)
    manifest_path = source / ".olivia-checkpoint.json"
    if not source.is_dir() or not manifest_path.is_file():
        raise ValueError("checkpoint not found")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        if path.name == ".olivia-checkpoint.json":
            continue
        if path.is_symlink():
            continue
        rel = path.relative_to(source)
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persistent-root", default="/data/0livia-checkpoints")
    parser.add_argument("--name", required=True)
    parser.add_argument("--max-bytes", type=int, default=2_000_000_000)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--checkpoint", metavar="SOURCE")
    mode.add_argument("--restore", metavar="DESTINATION")
    args = parser.parse_args()

    root = Path(args.persistent_root)
    if args.checkpoint:
        result = checkpoint(Path(args.checkpoint), root, args.name, args.max_bytes)
    else:
        result = restore(root, args.name, Path(args.restore))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
