import asyncio
import io
import json
import os
import zipfile

import pytest

from olivia.browser_worker import (
    BrowserDispatchUncertainError,
    BrowserJobRequest,
    BrowserWorkerError,
    GitHubActionsBrowserWorker,
    browser_worker_from_env,
)


def test_browser_job_validation_rejects_private_and_oversized_input():
    with pytest.raises(ValueError):
        GitHubActionsBrowserWorker.validate_request(
            BrowserJobRequest(url="http://127.0.0.1/", objective="x", base_ref="main")
        )
    with pytest.raises(ValueError):
        GitHubActionsBrowserWorker.validate_request(
            BrowserJobRequest(
                url="https://example.com/",
                objective="x" * 4001,
                base_ref="main",
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
        def get(self, url, *, headers):
            calls.append((url, None, headers))
            response = FakeResponse()
            response.status = 200
            async def private_repo():
                return {"private": True}
            response.json = private_repo
            return response
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
            base_ref="main",
        ),
    )

    assert result["remote_status"] == "dispatched"
    assert len(calls) == 2
    repo_url, _, repo_headers = calls[0]
    assert repo_url.endswith("/repos/simondalmasso/0liviA")
    assert repo_headers["authorization"] == "Bearer test-token"
    url, payload, headers = calls[1]
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


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/?token=abc",
        "https://example.com/?api_key=abc",
        "https://example.com/?sessionid=abc",
        "https://example.com/?signature=abc",
        "https://example.com/?code=abc",
    ],
)
def test_browser_job_rejects_sensitive_query_parameters(url):
    with pytest.raises(ValueError, match="sensitive query"):
        GitHubActionsBrowserWorker.validate_request(
            BrowserJobRequest(
                url=url,
                objective="",
                base_ref="main",
            )
        )


def test_browser_job_allows_ordinary_public_query_parameters():
    GitHubActionsBrowserWorker.validate_request(
        BrowserJobRequest(
            url="https://example.com/search?q=olivia&page=2",
            objective="",
            base_ref="main",
        )
    )


def test_browser_worker_hard_zero_cost_requires_explicit_actions_cost_verification(monkeypatch):
    monkeypatch.setenv("OLIVIA_BROWSER_WORKER_ENABLED", "1")
    monkeypatch.setenv("OLIVIA_BROWSER_REPO", "owner/private-browser")
    monkeypatch.delenv("OLIVIA_BROWSER_ZERO_COST_VERIFIED", raising=False)

    with pytest.raises(BrowserWorkerError, match="zero-cost"):
        browser_worker_from_env(hard_zero_cost=True)

    monkeypatch.setenv("OLIVIA_BROWSER_ZERO_COST_VERIFIED", "1")
    worker = browser_worker_from_env(hard_zero_cost=True)
    assert worker is not None
    assert worker.repo == "owner/private-browser"


def test_browser_worker_non_hard_zero_cost_can_be_enabled_without_cost_attestation(monkeypatch):
    monkeypatch.setenv("OLIVIA_BROWSER_WORKER_ENABLED", "1")
    monkeypatch.setenv("OLIVIA_BROWSER_REPO", "owner/private-browser")
    monkeypatch.delenv("OLIVIA_BROWSER_ZERO_COST_VERIFIED", raising=False)

    worker = browser_worker_from_env(hard_zero_cost=False)
    assert worker is not None


@pytest.mark.asyncio
async def test_browser_worker_rejects_public_repo_before_dispatch(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status, body=None):
            self.status = status
            self._body = body or {}
        async def json(self):
            return self._body
        async def text(self):
            return ""
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    class FakeSession:
        def get(self, url, *, headers):
            calls.append(("get", url))
            return FakeResponse(200, {"private": False})
        def post(self, url, *, json, headers):
            calls.append(("post", url))
            return FakeResponse(204)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA",
        session_factory=lambda **_: FakeSession(),
    )

    with pytest.raises(BrowserWorkerError, match="private"):
        await worker.dispatch(
            "0123456789abcdef",
            BrowserJobRequest(
                url="https://example.com/",
                objective="",
                base_ref="main",
            ),
        )

    assert [kind for kind, _ in calls] == ["get"]


@pytest.mark.asyncio
async def test_browser_dispatch_timeout_after_private_repo_check_is_uncertain(monkeypatch):
    class RepoResponse:
        status = 200

        async def json(self):
            return {"private": True}

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class FakeSession:
        def get(self, url, *, headers):
            return RepoResponse()

        def post(self, url, *, json, headers):
            raise asyncio.TimeoutError()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA",
        session_factory=lambda **_: FakeSession(),
    )
    with pytest.raises(BrowserDispatchUncertainError, match="outcome uncertain"):
        await worker.dispatch(
            "0123456789abcdef",
            BrowserJobRequest(
                url="https://example.com/",
                objective="",
                base_ref="main",
            ),
        )


@pytest.mark.asyncio
async def test_browser_dispatch_http_503_remains_uncertain(monkeypatch):
    class Response:
        def __init__(self, status):
            self.status = status

        async def json(self):
            return {"private": True}

        async def text(self):
            return "temporarily unavailable"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class Session:
        def get(self, url, *, headers):
            return Response(200)

        def post(self, url, *, json, headers):
            return Response(503)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA", session_factory=lambda **_: Session()
    )
    with pytest.raises(BrowserDispatchUncertainError):
        await worker.dispatch(
            "0123456789abcdef",
            BrowserJobRequest(url="https://example.com/", objective="", base_ref="main"),
        )


@pytest.mark.asyncio
async def test_browser_dispatch_session_teardown_after_204_remains_uncertain(monkeypatch):
    class Response:
        def __init__(self, status):
            self.status = status

        async def json(self):
            return {"private": True}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class Session:
        def get(self, url, *, headers):
            return Response(200)

        def post(self, url, *, json, headers):
            return Response(204)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            raise asyncio.TimeoutError()

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA", session_factory=lambda **_: Session()
    )
    with pytest.raises(BrowserDispatchUncertainError):
        await worker.dispatch(
            "0123456789abcdef",
            BrowserJobRequest(url="https://example.com/", objective="", base_ref="main"),
        )


@pytest.mark.asyncio
async def test_browser_status_finds_verified_receipt_beyond_first_hundred_runs(monkeypatch):
    job_id = "0123456789abcdef"
    visited = []
    stale = [{"id": i + 1, "display_title": "unrelated workflow"} for i in range(100)]
    target = {
        "id": 424242,
        "display_title": f"0liviA browse {job_id}",
        "status": "completed",
        "conclusion": "success",
        "head_sha": "signed-test-sha",
        "html_url": "https://github.com/example/actions/runs/424242",
    }

    class Response:
        status = 200
        def __init__(self, runs):
            self.runs = runs
        async def json(self):
            return {"workflow_runs": self.runs}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    class Session:
        def get(self, url, *, headers):
            visited.append(url)
            return Response([target] if "page=2" in url else stale)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA", session_factory=lambda **_: Session()
    )
    receipt = await worker.status(job_id)
    assert receipt is not None
    assert receipt["remote_run_id"] == 424242
    assert receipt["remote_conclusion"] == "success"
    assert len(visited) == 2
    assert all("per_page=100" in url for url in visited)
    assert "page=2" in visited[1]


@pytest.mark.asyncio
async def test_browser_status_exhausted_scan_fails_closed_without_dispatch(monkeypatch):
    calls = []
    stale = [{"id": i + 1, "display_title": "unrelated workflow"} for i in range(100)]

    class Response:
        status = 200
        async def json(self):
            return {"workflow_runs": stale}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    class Session:
        def get(self, url, *, headers):
            calls.append(url)
            return Response()
        def post(self, *args, **kwargs):
            raise AssertionError("status reconciliation must never dispatch")
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsBrowserWorker(
        "simondalmasso/0liviA", session_factory=lambda **_: Session()
    )
    with pytest.raises(BrowserWorkerError, match="scan exhausted"):
        await worker.status("0123456789abcdef")
    assert len(calls) == 10
