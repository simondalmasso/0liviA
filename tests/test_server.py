import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from aiohttp import ClientSession

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


@pytest.mark.asyncio
async def test_health_distinguishes_process_and_provider_ready(client):
    response = await client.get("/healthz")
    assert response.status == 200
    body = await response.json()
    assert body["process_alive"] is True
    assert body["provider_ready"] is False
    assert body["provider_configured"] is False


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
async def test_streaming_and_duplicate_turn_rejection(client, gateway):
    _, store, router = gateway
    session_id = store.create_session()
    router.wait = True
    first = await client.post(f"/api/chat/{session_id}", json={"text": "uno"}, headers=auth())
    second = await client.post(f"/api/chat/{session_id}", json={"text": "dos"}, headers=auth())
    assert second.status == 409
    first.close()


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
async def test_disconnect_cancels_agent_turn(client, gateway):
    _, store, router = gateway
    session_id = store.create_session()
    router.wait = True
    response = await client.post(f"/api/chat/{session_id}", json={"text": "cancelame"}, headers=auth())
    response.close()
    await asyncio.sleep(0.05)
    assert router.cancelled is True
