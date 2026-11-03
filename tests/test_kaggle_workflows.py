"""Static guardrails for Kaggle GitHub Actions automation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = (ROOT / ".github/workflows/kaggle-api-preflight.yml").read_text(encoding="utf-8")
RUN = (ROOT / ".github/workflows/kaggle-t4x2-benchmark.yml").read_text(encoding="utf-8")


def test_api_preflight_is_read_only_and_does_not_allocate_gpu():
    assert "workflow_dispatch:" in PREFLIGHT
    assert "kaggle quota -v" in PREFLIGHT
    assert "secrets.OLIVIA_KAGGLE_API_TOKEN" in PREFLIGHT
    assert "KAGGLE_API_TOKEN:" in PREFLIGHT
    assert "permissions:\n  contents: read" in PREFLIGHT
    assert "kaggle kernels push" not in PREFLIGHT
    assert "enable_gpu" not in PREFLIGHT


def test_gpu_run_requires_manual_dispatch_and_explicit_confirmation():
    assert "workflow_dispatch:" in RUN
    assert "confirm_gpu_session" in RUN
    assert "default: false" in RUN
    assert 'CONFIRM_GPU: ${{ inputs.confirm_gpu_session }}' in RUN
    assert '[[ "${CONFIRM_GPU}" == "true" ]]' in RUN
    assert "NvidiaTeslaT4" in RUN
    assert "machine_shape" in RUN
    assert "is_private" in RUN


def test_secret_is_not_embedded_in_kernel_metadata_or_passed_as_notebook_data():
    assert "secrets.OLIVIA_KAGGLE_API_TOKEN" in RUN
    assert '"KAGGLE_API_TOKEN"' not in RUN
    assert "KAGGLE_API_TOKEN" in RUN
    assert "dataset_sources" in RUN
    assert "enable_gpu" in RUN
    assert "kaggle kernels push" in RUN
    assert "--no-run" not in RUN


def test_run_checks_weekly_gpu_quota_before_push_and_validates_private_dataset():
    quota_check = RUN.index("Check API access, quota and private dataset visibility")
    push = RUN.index("Push private T4x2 notebook")
    dataset_check = RUN.index('kaggle datasets files')
    assert quota_check < push
    assert dataset_check < push
    assert "scripts/check_kaggle_quota.py" in RUN
    assert "--required-hours" in RUN
