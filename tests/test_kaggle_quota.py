"""Tests for the Kaggle weekly GPU quota guard."""

from io import StringIO

import pytest

from scripts.check_kaggle_quota import main, read_gpu_quota


CSV = """resource,used,remaining,total,refreshAt
GPU,2.50h,7.50h,10.00h,2026-11-08T00:00:00Z
TPU,0.00h,20.00h,20.00h,2026-11-08T00:00:00Z
"""


def test_reads_gpu_quota_not_tpu_quota():
    result = read_gpu_quota(StringIO(CSV))
    assert result["used"] == 2.5
    assert result["remaining"] == 7.5
    assert result["total"] == 10.0


def test_accepts_csv_header_case_and_whitespace():
    result = read_gpu_quota(StringIO(" Resource , Used , Remaining , Total \nGPU,1.00h,2.00h,3.00h\n"))
    assert result["remaining"] == 2.0


def test_rejects_missing_gpu_row():
    with pytest.raises(ValueError, match="GPU quota row"):
        read_gpu_quota(StringIO("resource,used,remaining,total\nTPU,0,10,10\n"))


def test_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        read_gpu_quota(StringIO("resource,remaining\nGPU,1\n"))


def test_rejects_invalid_or_negative_values():
    with pytest.raises(ValueError, match="invalid"):
        read_gpu_quota(StringIO("resource,used,remaining,total\nGPU,zero,1,2\n"))
    with pytest.raises(ValueError, match="negative"):
        read_gpu_quota(StringIO("resource,used,remaining,total\nGPU,0,-1,2\n"))


def test_writes_github_step_summary_when_requested(tmp_path, monkeypatch):
    import sys

    quota_csv = tmp_path / "quota.csv"
    quota_csv.write_text(CSV, encoding="utf-8")
    summary = tmp_path / "nested" / "summary.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_kaggle_quota.py",
            "--csv",
            str(quota_csv),
            "--summary-file",
            str(summary),
            "--required-hours",
            "2",
        ],
    )
    assert main() == 0
    content = summary.read_text(encoding="utf-8")
    assert "GPU quota remaining: **7.5 h**" in content
    assert "Required for requested run: **2 h**" in content


def test_required_hours_fails_closed_when_quota_is_too_low(tmp_path, monkeypatch):
    import sys

    quota_csv = tmp_path / "quota.csv"
    quota_csv.write_text("resource,used,remaining,total\nGPU,9,1,10\n", encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["check_kaggle_quota.py", "--csv", str(quota_csv), "--required-hours", "2"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 3
