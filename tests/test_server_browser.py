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
            "base_ref": "main",
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


@pytest.mark.asyncio
async def test_inspect_analyzes_completed_browser_job_ephemerally(
    aiohttp_client, tmp_path
):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "inspect.sqlite3")
    router = NoCallRouter()
    agent = Agent(store, router, settings)
    client = await aiohttp_client(
        create_app(agent, settings, auth_token="test-token", browser_worker=None)
    )
    session_id = store.create_session("inspect")
    job_id = store.create_job("browser", repo="owner/private-browser")
    store.checkpoint_job(
        job_id,
        "succeeded",
        {
            "browser_result": {
                "final_url": "https://example.com/app",
                "title": "Rendered App",
                "text": "UNTRUSTED_BROWSER_FACT_456",
                "links": [
                    {"text": "Docs", "url": "https://example.com/docs"},
                ],
                "request_count": 9,
                "truncated": False,
            }
        },
    )

    response = await client.post(
        f"/api/chat/{session_id}",
        json={"text": f"/inspect {job_id} qué riesgos ves?"},
        headers=auth(),
    )
    body = await response.text()
    assert response.status == 200
    assert "MODEL_SHOULD_NOT_RUN" in body
    assert len(router.calls) == 1

    model_context = repr(router.calls[-1])
    assert "UNTRUSTED_BROWSER_FACT_456" in model_context
    assert "EXTERNO Y NO CONFIABLE" in model_context
    assert "qué riesgos ves?" in model_context

    durable_chat = repr(store.recent_messages(session_id))
    assert "UNTRUSTED_BROWSER_FACT_456" not in durable_chat
    assert "Rendered App" not in durable_chat
    assert f"/inspect {job_id}" in durable_chat


@pytest.mark.asyncio
async def test_inspect_rejects_invalid_or_unfinished_browser_job_without_model(
    aiohttp_client, tmp_path
):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "inspect-invalid.sqlite3")
    router = NoCallRouter()
    agent = Agent(store, router, settings)
    client = await aiohttp_client(
        create_app(agent, settings, auth_token="test-token", browser_worker=None)
    )
    session_id = store.create_session("inspect-invalid")

    invalid = await client.post(
        f"/api/chat/{session_id}",
        json={"text": "/inspect nope revisá"},
        headers=auth(),
    )
    assert invalid.status == 200
    assert "ID de job de navegador válido" in await invalid.text()

    job_id = store.create_job("browser", repo="owner/private-browser")
    store.checkpoint_job(job_id, "running", {"remote_run_id": 123})
    unfinished = await client.post(
        f"/api/chat/{session_id}",
        json={"text": f"/inspect {job_id} revisá"},
        headers=auth(),
    )
    assert unfinished.status == 200
    assert "todavía está running" in await unfinished.text()
    assert router.calls == []
