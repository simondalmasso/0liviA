#!/usr/bin/env python3
"""Fail-closed parser for Kaggle's weekly GPU/TPU quota CSV."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TextIO


def _decimal(value: str, field: str) -> Decimal:
    try:
        normalized = value.strip().lower()\n        if normalized.endswith("h"):\n            normalized = normalized[:-1].strip()\n        return Decimal(normalized)
    except (InvalidOperation, AttributeError):
        raise ValueError(f"invalid {field!r} value in Kaggle quota CSV") from None


def read_gpu_quota(stream: TextIO) -> dict[str, str | Decimal]:
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ValueError("Kaggle quota response is empty or has no CSV header")

    normalized = {name.strip().lower(): name for name in reader.fieldnames if name}
    required = {"resource", "used", "remaining", "total"}
    missing = required.difference(normalized)
    if missing:
        raise ValueError("Kaggle quota CSV is missing columns: " + ", ".join(sorted(missing)))

    gpu_row = None
    for row in reader:
        resource = (row.get(normalized["resource"]) or "").strip().upper()
        if resource == "GPU":
            gpu_row = row
            break
    if gpu_row is None:
        raise ValueError("Kaggle did not return a GPU quota row; refusing to assume availability")

    refresh_column = normalized.get("refreshat")
    result: dict[str, str | Decimal] = {
        "used": _decimal(gpu_row[normalized["used"]], "used"),
        "remaining": _decimal(gpu_row[normalized["remaining"]], "remaining"),
        "total": _decimal(gpu_row[normalized["total"]], "total"),
        "refresh_at": (gpu_row.get(refresh_column, "") if refresh_column else "").strip(),
    }
    if result["used"] < 0 or result["remaining"] < 0 or result["total"] < 0:
        raise ValueError("Kaggle returned a negative GPU quota value")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path, help="Path to output from 'kaggle quota -v'")
    parser.add_argument("--summary-file", type=Path, help="Optional GitHub Actions Markdown summary path")
    parser.add_argument(
        "--required-hours",
        type=Decimal,
        default=None,
        help="Require at least this many remaining GPU hours before starting a run",
    )
    args = parser.parse_args()

    if args.required_hours is not None and args.required_hours < 0:
        parser.error("--required-hours cannot be negative")

    try:
        with args.csv.open("r", encoding="utf-8-sig", newline="") as stream:
            quota = read_gpu_quota(stream)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"quota check failed closed: {exc}\n")

    used = quota["used"]
    remaining = quota["remaining"]
    total = quota["total"]
    refresh_at = quota["refresh_at"]
    print(f"GPU quota: used={used}h remaining={remaining}h total={total}h")
    if refresh_at:
        print(f"GPU quota refresh: {refresh_at}")

    summary_lines = [
        "## Kaggle API preflight — GPU quota",
        "",
        f"- GPU quota used: **{used} h**",
        f"- GPU quota remaining: **{remaining} h**",
        f"- GPU quota total: **{total} h**",
    ]
    if refresh_at:
        summary_lines.append(f"- Quota refresh: `{refresh_at}`")

    if args.required_hours is not None and remaining < args.required_hours:
        parser.exit(
            3,
            f"refusing GPU launch: {remaining}h remain but {args.required_hours}h are required\n",
        )
    if args.required_hours is not None:
        summary_lines.append(f"- Required for requested run: **{args.required_hours} h**")
    if remaining == 0:
        warning = "WARNING: no GPU quota remains; preflight only, do not launch a GPU session."
        print(warning)
        summary_lines.extend(["", f"> {warning}"])

    if args.summary_file:
        args.summary_file.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_file.open("a", encoding="utf-8") as output:
            output.write("\n".join(summary_lines) + "\n\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
