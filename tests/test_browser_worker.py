import io
import json
import os
import zipfile

import pytest

from olivia.browser_worker import (
    BrowserJobRequest,
    BrowserWorkerError,
    GitHubActionsBrowserWorker,
)


def test_browser_job_validation_rejects_private_and_oversized_input():
    with pytest.raises(ValueError):
        GitHubActionsBrowserWorker.validate_request(
            BrowserJobRequest(url="http://127.0.0.1/", objective="x", base_ref="arch/gpt-synthesis-v1")
        )
    with pytest.raises(ValueError):
        GitHubActionsBrowserWorker.validate_request(
            BrowserJobRequest(
                url="https://example.com/",
                objective="x" * 4001,
                base_ref="arch/gpt-synthesis-v1",
            )
        )


@pytest.mark.asyncio
async def test_browser_worker_dispatches_bounded_workflow(monkeypatch):
    calls = []

    class FakeResponse:
        status = 204
        async def text(self):
            return ""
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    class FakeSession:
        def post(self, url, *, json, headers):
            calls.append((url, json, headers))
            return FakeResponse()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA",
        session_factory=lambda **_: FakeSession(),
    )
    result = await worker.dispatch(
        "0123456789abcdef",
        BrowserJobRequest(
            url="https://example.com/path#fragment",
            objective="Leé la página",
            base_ref="arch/gpt-synthesis-v1",
        ),
    )

    assert result["remote_status"] == "dispatched"
    assert len(calls) == 1
    url, payload, headers = calls[0]
    assert url.endswith("/actions/workflows/browser-agent.yml/dispatches")
    assert payload["inputs"]["url"] == "https://example.com/path"
    assert "objective" not in payload["inputs"]
    assert headers["authorization"] == "Bearer test-token"


@pytest.mark.asyncio
async def test_browser_worker_reads_bounded_result_artifact(monkeypatch):
    artifact_body = {
        "artifacts": [
            {
                "id": 77,
                "name": "browser-result",
                "expired": False,
            }
        ]
    }
    payload = {
        "final_url": "https://example.com/",
        "title": "Example",
        "text": "Rendered content",
        "links": [{"text": "More", "url": "https://example.com/more"}],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("browser-result.json", json.dumps(payload))

    class FakeResponse:
        def __init__(self, status, json_body=None, raw=b""):
            self.status = status
            self._json_body = json_body
            self._raw = raw
        async def json(self):
            return self._json_body
        async def read(self):
            return self._raw
        async def text(self):
            return ""
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    class FakeSession:
        def get(self, url, *, headers):
            if url.endswith("/artifacts"):
                return FakeResponse(200, artifact_body)
            assert url.endswith("/actions/artifacts/77/zip")
            return FakeResponse(200, raw=buf.getvalue())
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA",
        session_factory=lambda **_: FakeSession(),
    )
    result = await worker.result(123)
    assert result == payload


@pytest.mark.asyncio
async def test_browser_worker_status_matches_only_its_job(monkeypatch):
    class FakeResponse:
        status = 200
        async def json(self):
            return {
                "workflow_runs": [
                    {
                        "id": 99,
                        "display_title": "0liviA browse 0123456789abcdef",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://github.com/example/run/99",
                        "head_sha": "abc",
                    }
                ]
            }
        async def text(self):
            return ""
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    class FakeSession:
        def get(self, url, *, headers):
            return FakeResponse()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA",
        session_factory=lambda **_: FakeSession(),
    )
    result = await worker.status("0123456789abcdef")
    assert result["remote_run_id"] == 99
    assert result["remote_conclusion"] == "success"


def test_public_browser_workflow_is_read_only_and_prompt_private():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "browser-agent.yml").read_text(encoding="utf-8")
    runner = (root / "scripts" / "browser_snapshot.py").read_text(encoding="utf-8")

    assert "inputs.objective" not in workflow
    assert 'objective:' not in workflow
    assert 'request.method not in {"GET", "HEAD"}' in runner
    assert "accept_downloads=False" in runner
    assert "127.0.0.0/8" in workflow
    assert "::1/128" in workflow
    assert "169.254.0.0/16" in workflow
