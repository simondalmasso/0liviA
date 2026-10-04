import asyncio
import json
from collections.abc import AsyncIterator

import pytest

from olivia.agent import Agent
from olivia.config import Settings
from olivia.server import create_app
from olivia.store import Store


class FakeRouter:
    def __init__(self, parts=("hola", " mundo"), *, wait=False):
        self.providers = []
        self.parts = parts
        self.wait = wait
        self.cancelled = False

    async def stream(self, messages) -> AsyncIterator[object]:
        from olivia.router import RouteEvent

        yield RouteEvent(type="route", provider="fake")
        for part in self.parts:
            if self.wait:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise
            yield RouteEvent(type="delta", provider="fake", text=part)
        yield RouteEvent(type="done", provider="fake")


@pytest.fixture
def gateway(tmp_path):
    settings = Settings(data_dir=tmp_path, max_history=24)
    store = Store(tmp_path / "state.sqlite3")
    router = FakeRouter()
    agent = Agent(store, router, settings)
    return create_app(agent, settings, auth_token="test-token"), store, router


@pytest.fixture
async def client(aiohttp_client, gateway):
    return await aiohttp_client(gateway[0])


def auth():
    return {"Authorization": "Bearer test-token"}


async def wait_until(predicate, attempts=20):
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0.01)
    assert predicate()


@pytest.mark.asyncio
async def test_health_distinguishes_process_and_provider_ready(client):
    response = await client.get("/healthz")
    assert response.status == 200
    body = await response.json()
    assert body["process_alive"] is True
    assert body["provider_ready"] is False
    assert body["provider_configured"] is False


@pytest.mark.asyncio
async def test_static_ui_is_served_without_local_capabilities(client):
    response = await client.get("/")
    assert response.status == 200
    html = await response.text()
    assert '<html lang="es-AR">' in html
    assert "sessionStorage.setItem(key,sessionId)" in html
    assert "localStorage" not in html
    for forbidden in ("showOpenFilePicker", "showSaveFilePicker", "Desktop Commander", "child_process", "localhost"):
        assert forbidden not in html
    assert "sessionStorage.setItem(key,sessionId)" in html
    assert "sessionStorage.setItem(key,token)" not in html


@pytest.mark.asyncio
async def test_auth_and_session_persistence(client):
    assert (await client.post("/api/sessions", json={})).status == 401
    response = await client.post("/api/sessions", json={"title": "Prueba"}, headers=auth())
    assert response.status == 201
    session_id = (await response.json())["id"]
    assert (await client.get(f"/api/sessions/{session_id}/messages")).status == 401
    response = await client.get(f"/api/sessions/{session_id}/messages", headers=auth())
    assert response.status == 200
    assert (await response.json())["messages"] == []


@pytest.mark.asyncio
async def test_streaming_and_duplicate_turn_rejection_and_cleanup(client, gateway):
    _, store, router = gateway
    session_id = store.create_session()
    router.wait = True
    first = await client.post(f"/api/chat/{session_id}", json={"text": "uno"}, headers=auth())
    second = await client.post(f"/api/chat/{session_id}", json={"text": "dos"}, headers=auth())
    assert second.status == 409
    turn_id = first.headers["X-Turn-ID"]
    cancelled = await client.post(
        f"/api/chat/{session_id}/cancel", json={"turn_id": turn_id}, headers=auth()
    )
    assert cancelled.status == 202
    first.close()
    await wait_until(lambda: router.cancelled and session_id not in client.app["gateway"]._turns)


@pytest.mark.asyncio
async def test_streaming_response_and_persistence(client, gateway):
    _, store, _ = gateway
    session_id = store.create_session()
    response = await client.post(f"/api/chat/{session_id}", json={"text": "hola"}, headers=auth())
    assert response.status == 200
    events = [json.loads(line[6:]) for line in (await response.text()).splitlines() if line.startswith("data: ")]
    assert {event["type"] for event in events} >= {"route", "delta", "done"}
    messages = await client.get(f"/api/sessions/{session_id}/messages", headers=auth())
    assert [item["role"] for item in (await messages.json())["messages"]] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_disconnect_cancels_agent_turn_and_cleans_registry(client, gateway):
    _, store, router = gateway
    session_id = store.create_session()
    router.wait = True
    response = await client.post(f"/api/chat/{session_id}", json={"text": "cancelame"}, headers=auth())
    response.close()
    await wait_until(lambda: router.cancelled and session_id not in client.app["gateway"]._turns)


@pytest.mark.asyncio
async def test_locale_mismatch_is_retryable_and_emits_no_text(client, gateway):
    app, store, _ = gateway
    app["gateway"].locale_validator = lambda text: False
    app["gateway"].locale_buffer_chars = 5
    session_id = store.create_session()
    response = await client.post(f"/api/chat/{session_id}", json={"text": "probá"}, headers=auth())
    events = [json.loads(line[6:]) for line in (await response.text()).splitlines() if line.startswith("data: ")]
    assert events == [{"type": "error", "code": "locale_mismatch", "retryable": True, "turn_id": events[0]["turn_id"]}]
    assert all(event.get("type") != "delta" for event in events)
    messages = store.recent_messages(session_id)
    assert [message["role"] for message in messages] == ["user"]


@pytest.mark.asyncio
async def test_cancel_requires_matching_turn_id(client, gateway):
    _, store, router = gateway
    session_id = store.create_session()
    router.wait = True
    first = await client.post(f"/api/chat/{session_id}", json={"text": "uno"}, headers=auth())
    wrong = await client.post(
        f"/api/chat/{session_id}/cancel", json={"turn_id": "wrong"}, headers=auth()
    )
    assert wrong.status == 409
    await client.post(
        f"/api/chat/{session_id}/cancel", json={"turn_id": first.headers["X-Turn-ID"]}, headers=auth()
    )
    first.close()
    await wait_until(lambda: router.cancelled and session_id not in client.app["gateway"]._turns)
