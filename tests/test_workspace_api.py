from collections.abc import AsyncIterator

import pytest

from olivia.agent import Agent
from olivia.config import Settings
from olivia.router import RouteEvent
from olivia.server import create_app
from olivia.store import Store


class QuietRouter:
    providers = []

    async def stream(self, messages) -> AsyncIterator[RouteEvent]:
        yield RouteEvent(type="delta", provider="fake", text="ok")
        yield RouteEvent(type="done", provider="fake")


def auth():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_workspace_api_is_owner_authenticated_and_durable(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "workspace-api.sqlite3")
    agent = Agent(store, QuietRouter(), settings)
    client = await aiohttp_client(create_app(agent, settings, auth_token="test-token"))

    assert (await client.get("/api/workspace")).status == 401

    initial = await client.get("/api/workspace", headers=auth())
    assert initial.status == 200
    body = await initial.json()
    assert body["projects"][0]["name"] == "0liviA"
    assert body["library"] == []
    assert body["memories"] == []

    created_project = await client.post(
        "/api/projects",
        json={"name": "Producto"},
        headers=auth(),
    )
    assert created_project.status == 201
    project = await created_project.json()

    created_session = await client.post(
        "/api/sessions",
        json={"title": "Arquitectura", "project_id": project["id"]},
        headers=auth(),
    )
    assert created_session.status == 201
    session = await created_session.json()
    assert session["project_id"] == project["id"]

    created_library = await client.post(
        "/api/library",
        json={"title": "Spec", "value": "Contrato cloud-first"},
        headers=auth(),
    )
    assert created_library.status == 201

    created_memory = await client.post(
        "/api/memories",
        json={"title": "Idioma", "value": "es-AR"},
        headers=auth(),
    )
    assert created_memory.status == 201

    final = await client.get("/api/workspace", headers=auth())
    data = await final.json()
    product = next(item for item in data["projects"] if item["id"] == project["id"])
    assert any(chat["id"] == session["id"] for chat in product["chats"])
    assert any(item["title"] == "Spec" and item["value"] == "Contrato cloud-first" for item in data["library"])
    assert any(item["title"] == "Idioma" and item["value"] == "es-AR" for item in data["memories"])


@pytest.mark.asyncio
async def test_workspace_writes_apply_secret_redaction(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "workspace-dlp.sqlite3")
    agent = Agent(store, QuietRouter(), settings)
    client = await aiohttp_client(create_app(agent, settings, auth_token="test-token"))

    response = await client.post(
        "/api/library",
        json={"title": "Clave", "value": "OPENAI_API_KEY=sk-123456789012345678901234567890"},
        headers=auth(),
    )
    assert response.status == 201

    workspace = await (await client.get("/api/workspace", headers=auth())).json()
    rendered = repr(workspace)
    assert "sk-123456789012345678901234567890" not in rendered
