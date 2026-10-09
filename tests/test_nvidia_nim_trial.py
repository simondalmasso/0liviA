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


def test_muse_trial_is_allowlisted_and_ui_choice_is_explicit():
    module = load_probe()
    assert module.ALLOWED_MODELS["muse-glimmer"] == "meta/muse-glimmer-30b"
    assert module.ALLOWED_MODELS["deepseek"] == module.MODEL
    yaml = WORKFLOW.read_text(encoding="utf-8")
    assert "NVIDIA_NIM_EVAL_MODEL: ${{ inputs.model }}" in yaml
    assert "          - muse-glimmer" in yaml
    assert "          - deepseek" in yaml
    assert "default: muse-glimmer" in yaml
    assert "if: ${{ inputs.acknowledge_trial_only }}" in yaml


def test_unlisted_model_cannot_make_any_network_request(monkeypatch):
    module = load_probe()
    monkeypatch.setenv("NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED", "1")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-never-print")
    monkeypatch.setenv("NVIDIA_NIM_EVAL_MODEL", "https://attacker.example/")
    monkeypatch.setattr(module.http.client, "HTTPSConnection",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network must not run")))
    assert module.main() == 2


def test_muse_evaluation_is_fixed_origin_bounded_and_does_not_log_output(monkeypatch, capsys):
    module = load_probe()
    monkeypatch.setenv("NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED", "1")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-fake-not-printed")
    monkeypatch.setenv("NVIDIA_NIM_EVAL_MODEL", "muse-glimmer")
    observed = {}
    class Connection:
        def __init__(self, host, timeout):
            observed["host"] = host
            observed["timeout"] = timeout
        def request(self, method, path, body, headers):
            import json
            data = json.loads(body)
            observed.update(method=method, path=path, data=data, headers=headers)
        def getresponse(self):
            class Response:
                status = 200
                def read(self, size):
                    assert size == 32_769
                    return b'{"choices":[{"message":{"content":"SECRET_PROVIDER_OUTPUT"}}]}'
            return Response()
        def close(self):
            observed["closed"] = True
    monkeypatch.setattr(module.http.client, "HTTPSConnection", Connection)
    assert module.main() == 0
    output = capsys.readouterr()
    assert "SECRET_PROVIDER_OUTPUT" not in output.out
    assert "nvapi-" not in output.out + output.err
    assert observed["host"] == "integrate.api.nvidia.com"
    assert observed["path"] == "/v1/chat/completions"
    assert observed["data"]["model"] == "meta/muse-glimmer-30b"
    assert observed["data"]["max_tokens"] == 64
    assert observed["data"]["messages"] == [{"role": "user", "content": "Respond only with: OK"}]
    assert observed["closed"] is True
