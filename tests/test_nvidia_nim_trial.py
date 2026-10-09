"""NVIDIA trial adapter must never activate production routes or leak secrets."""
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eval_nvidia_nim.py"
WORKFLOW = ROOT / ".github" / "workflows" / "nvidia-nim-eval.yml"


def load_probe():
    spec = importlib.util.spec_from_file_location("nim_trial_probe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_request_when_entitlement_not_verified(monkeypatch, capsys):
    module = load_probe()
    monkeypatch.delenv("NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-do-not-log-this-secret")
    def no_network(*args, **kwargs):
        raise AssertionError("trial-only eval must not call network without approval")
    monkeypatch.setattr(module.http.client, "HTTPSConnection", no_network)
    assert module.main() == 2
    assert "nvapi-" not in capsys.readouterr().err


def test_no_request_without_api_key(monkeypatch):
    module = load_probe()
    monkeypatch.setenv("NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED", "1")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr(
        module.http.client, "HTTPSConnection",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network must not run")),
    )
    assert module.main() == 2


def test_only_fixed_official_model_and_endpoint():
    module = load_probe()
    assert module.MODEL == "deepseek-ai/deepseek-v4.1-flash"
    assert module.ENDPOINT == "https://integrate.api.nvidia.com/v1/chat/completions"
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"max_tokens": 64' in text
    assert '"stream": False' in text
    assert 'print("NVIDIA_NIM_TRIAL_EVAL_OK: internal-only;' in text
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "acknowledge_trial_only:" in workflow
    assert "NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED" in workflow
    assert "secrets.NVIDIA_API_KEY" in workflow
    assert "python3 scripts/eval_nvidia_nim.py" in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow
