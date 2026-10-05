from collections.abc import AsyncIterator
import re

import pytest

from olivia.agent import Agent
from olivia.browser_worker import BrowserJobRequest
from olivia.config import Settings
from olivia.router import RouteEvent
from olivia.server import create_app
from olivia.store import Store


class NoCallRouter:
    providers = []

    def __init__(self):
        self.calls = []

    async def stream(self, messages) -> AsyncIterator[RouteEvent]:
        self.calls.append(messages)
        yield RouteEvent(type="delta", provider="fake", text="MODEL_SHOULD_NOT_RUN")
        yield RouteEvent(type="done", provider="fake")


class FakeBrowserWorker:
    configured = True
    repo = "simondalmasso/0liviA"
    workflow = "browser-agent.yml"

    def __init__(self):
        self.requests = []

    @staticmethod
    def validate_request(request: BrowserJobRequest):
        if not request.url.startswith("https://"):
            raise ValueError("invalid browser URL")

    async def dispatch(self, job_id, request):
        self.requests.append((job_id, request))
        return {
            "repo": self.repo,
            "workflow": self.workflow,
            "remote_status": "dispatched",
        }

    async def status(self, job_id):
        return {
            "remote_run_id": 321,
            "remote_status": "completed",
            "remote_conclusion": "success",
            "remote_url": "https://github.com/example/run/321",
            "remote_head_sha": "abc123",
        }

    async def result(self, run_id):
        assert run_id == 321
        return {
            "final_url": "https://example.com/app",
            "title": "Rendered App",
            "text": "UNTRUSTED_BROWSER_FACT_123",
            "links": [
                {"text": "Docs", "url": "https://example.com/docs"},
            ],
            "request_count": 17,
            "truncated": False,
        }


def auth():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_browse_command_dispatches_without_calling_chat_model(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "browse.sqlite3")
    router = NoCallRouter()
    agent = Agent(store, router, settings)
    worker = FakeBrowserWorker()
    client = await aiohttp_client(
        create_app(
            agent,
            settings,
            auth_token="test-token",
            browser_worker=worker,
        )
    )
    session_id = store.create_session("browse")

    response = await client.post(
        f"/api/chat/{session_id}",
        json={"text": "/browse https://example.com/app inspeccioná la UI"},
        headers=auth(),
    )
    body = await response.text()
    assert response.status == 200
    assert "despachado" in body
    assert router.calls == []
    assert len(worker.requests) == 1
    job_id, request = worker.requests[0]
    assert re.fullmatch(r"[0-9a-f]{16}", job_id)
    assert request.url == "https://example.com/app"
    assert request.objective == "inspeccioná la UI"
    assert store.get_job(job_id)["kind"] == "browser"


@pytest.mark.asyncio
async def test_browse_fails_closed_without_worker(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "browse-disabled.sqlite3")
    router = NoCallRouter()
    agent = Agent(store, router, settings)
    client = await aiohttp_client(
        create_app(agent, settings, auth_token="test-token", browser_worker=None)
    )
    session_id = store.create_session("browse")

    response = await client.post(
        f"/api/chat/{session_id}",
        json={"text": "/browse https://example.com/"},
        headers=auth(),
    )
    body = await response.text()
    assert "browser worker no está disponible" in body.lower()
    assert router.calls == []


@pytest.mark.asyncio
async def test_job_recovers_browser_result_without_persisting_external_text_in_chat(
    aiohttp_client, tmp_path
):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "browse-result.sqlite3")
    router = NoCallRouter()
    agent = Agent(store, router, settings)
    worker = FakeBrowserWorker()
    client = await aiohttp_client(
        create_app(
            agent,
            settings,
            auth_token="test-token",
            browser_worker=worker,
        )
    )
    session_id = store.create_session("browse-result")
    job_id = store.create_job("browser", repo=worker.repo)
    store.checkpoint_job(
        job_id,
        "dispatched",
        {
            "base_ref": "arch/gpt-synthesis-v1",
            "url": "https://example.com/app",
            "objective": "inspeccioná",
        },
    )

    response = await client.post(
        f"/api/chat/{session_id}",
        json={"text": f"/job {job_id}"},
        headers=auth(),
    )
    body = await response.text()
    assert "UNTRUSTED_BROWSER_FACT_123" in body
    assert "Rendered App" in body
    assert router.calls == []

    job = store.get_job(job_id)
    assert job["status"] == "succeeded"
    assert job["checkpoint"]["browser_result"]["text"] == "UNTRUSTED_BROWSER_FACT_123"

    durable_chat = repr(store.recent_messages(session_id))
    assert "UNTRUSTED_BROWSER_FACT_123" not in durable_chat
    assert "Rendered App" not in durable_chat


@pytest.mark.asyncio
async def test_health_reports_browser_worker_without_exposing_credentials(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "browse-health.sqlite3")
    agent = Agent(store, NoCallRouter(), settings)
    client = await aiohttp_client(
        create_app(
            agent,
            settings,
            auth_token="test-token",
            browser_worker=FakeBrowserWorker(),
        )
    )
    body = await (await client.get("/healthz")).json()
    assert body["browser_worker_configured"] is True
    assert "token" not in repr(body).lower()
