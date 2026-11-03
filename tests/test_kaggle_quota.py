"""Tests for the Kaggle weekly GPU quota guard."""

from io import StringIO

import pytest

from scripts.check_kaggle_quota import read_gpu_quota


CSV = """resource,used,remaining,total,refreshAt
GPU,2.5,7.5,10.0,2026-11-08T00:00:00Z
TPU,0,20,20,2026-11-08T00:00:00Z
"""


def test_reads_gpu_quota_not_tpu_quota():
    result = read_gpu_quota(StringIO(CSV))
    assert result["used"] == 2.5
    assert result["remaining"] == 7.5
    assert result["total"] == 10.0


def test_accepts_csv_header_case_and_whitespace():
    result = read_gpu_quota(StringIO(" Resource , Used , Remaining , Total \nGPU,1,2,3\n"))
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
