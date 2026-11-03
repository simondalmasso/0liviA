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
        return Decimal(value.strip())
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

    result: dict[str, str | Decimal] = {
        "used": _decimal(gpu_row[normalized["used"]], "used"),
        "remaining": _decimal(gpu_row[normalized["remaining"]], "remaining"),
        "total": _decimal(gpu_row[normalized["total"]], "total"),
        "refresh_at": (gpu_row.get(normalized.get("refreshat", "")) or "").strip(),
    }
    if result["used"] < 0 or result["remaining"] < 0 or result["total"] < 0:
        raise ValueError("Kaggle returned a negative GPU quota value")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path, help="Path to output from 'kaggle quota -v'")
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

    if args.required_hours is not None and remaining < args.required_hours:
        parser.exit(
            3,
            f"refusing GPU launch: {remaining}h remain but {args.required_hours}h are required\n",
        )
    if remaining == 0:
        print("WARNING: no GPU quota remains; preflight only, do not launch a GPU session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
