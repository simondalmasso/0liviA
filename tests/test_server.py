import asyncio
import json
from collections.abc import AsyncIterator

import pytest

from olivia.agent import Agent
from olivia.config import Settings
from olivia.server import create_app, default_es_ar_validator
from olivia.security import make_password_verifier
from olivia.store import Store


class FakeCodingWorker:
    repo = "simondalmasso/0liviA"
    configured = True

    def __init__(self):
        self.dispatched = []

    @staticmethod
    def validate_request(request):
        if not request.task.strip():
            raise ValueError("task must not be empty")

    async def dispatch(self, job_id, request):
        self.dispatched.append((job_id, request))
        return {
            "repo": self.repo,
            "workflow": "coding-agent.yml",
            "remote_status": "dispatched",
        }

    async def status(self, job_id):
        return {
            "remote_run_id": 123,
            "remote_status": "completed",
            "remote_conclusion": "success",
            "remote_url": "https://github.com/example/run/123",
            "remote_head_sha": "abc123",
        }


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
    assert "sessionStorage" not in html
    assert "localStorage" not in html
    for forbidden in ("showOpenFilePicker", "showSaveFilePicker", "Desktop Commander", "child_process", "localhost"):
        assert forbidden not in html
    assert "sessionStorage" not in html


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


def test_default_locale_guard_rejects_obvious_german():
    assert default_es_ar_validator("Das ist eine Antwort und wir können fortfahren.") is False
    assert default_es_ar_validator("Esto es una respuesta para vos y podemos seguir.") is True
    # Technical fragments without enough linguistic evidence are not falsely blocked.
    assert default_es_ar_validator("HTTP 429 -> retry 2s") is True


@pytest.mark.asyncio
async def test_ui_streams_sse_and_never_persists_auth_token(client):
    response = await client.get("/")
    html = await response.text()
    assert "pipeThrough(new TextDecoderStream())" in html
    assert "line.startsWith('data: ')" in html
    assert "Token de acceso" not in html
    assert "Authorization" not in html
    assert "/api/auth/login" in html
    assert "olivia_owner" not in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html


@pytest.mark.asyncio
async def test_session_listing_is_server_side(client, gateway):
    _, store, _ = gateway
    first = store.create_session("first")
    await asyncio.sleep(0.01)
    second = store.create_session("second")
    response = await client.get("/api/sessions?limit=1", headers=auth())
    assert response.status == 200
    sessions = (await response.json())["sessions"]
    assert [item["id"] for item in sessions] == [second]
    assert first != second


@pytest.mark.asyncio
async def test_live_voice_is_fullscreen_and_chat_stays_available(client):
    response = await client.get("/")
    html = await response.text()
    assert 'id="voiceLive"' in html
    assert 'position:fixed;inset:0' in html
    assert 'class="orb"' in html
    assert 'stroke:var(--cyan)' in html
    assert '#voiceLive.open{display:grid' in html
    assert 'id="voiceBtn"' in html
    assert 'id="text"' in html
    assert 'id="send"' in html
    assert 'id="voiceChat"' in html
    assert 'navigator.mediaDevices.getUserMedia' in html
    assert 'SpeechRecognition' in html
    assert "rec.lang='es-AR'" in html
    assert "==='es-ar'" in html
    assert 'speechSynthesis' in html
    assert 'localStorage' not in html
    assert 'sessionStorage' not in html


@pytest.mark.asyncio
async def test_sidebar_surfaces_and_web_read_status_are_truthful(client):
    response = await client.get("/")
    html = await response.text()
    for side in ("projects", "library", "memory", "config"):
        assert f'data-side="{side}"' in html
    assert "Todavía no conectada" not in html
    assert "URLs públicas · solo lectura" in html
    assert "$0 hard cap" not in html
    assert "Router automático" in html
    assert "coreHealth" in html


@pytest.mark.asyncio
async def test_projects_and_chats_exist_without_visual_clutter(client):
    response = await client.get("/")
    html = await response.text()
    assert 'id="drawer"' in html
    assert 'id="tree"' in html
    assert 'id="newProject"' in html
    assert "indexedDB.open" in html
    assert "selectedProjectId" in html
    assert "selectedChatId" in html
    assert "remoteSessionId" in html
    assert "/api/auth/login" in html
    assert "/api/sessions" in html
    assert "/api/chat/" in html
    assert "api_mode==='canonical'" in html
    assert "status:'queued'" in html
    for literal in (
        "Chat persistente + Live Voice",
        "Nueva sesión",
        ">Enviar<",
        ">Cancelar<",
        "Token de acceso",
        "core cloud todavía no conectado",
    ):
        assert literal not in html


@pytest.mark.asyncio
async def test_reference_inspired_violet_blue_cyan_visual_system(client):
    response = await client.get("/")
    html = await response.text()
    for token in ("--violet:", "--magenta:", "--blue:", "--cyan:"):
        assert token in html
    assert "linear-gradient(180deg" in html
    assert "radial-gradient" in html
    assert ".composer{" in html
    assert "#voiceLive{" in html
    assert ".voice-stage::before" in html
    assert ".drawer{" in html


@pytest.mark.asyncio
async def test_coding_job_dispatch_is_authenticated_durable_and_refreshable(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "coding.sqlite3")
    router = FakeRouter()
    agent = Agent(store, router, settings)
    worker = FakeCodingWorker()
    client = await aiohttp_client(
        create_app(agent, settings, auth_token="test-token", coding_worker=worker)
    )

    assert (await client.post("/api/jobs/code", json={"task": "fix tests"})).status == 401

    response = await client.post(
        "/api/jobs/code",
        json={
            "task": "Fix the failing tests without changing unrelated behavior.",
            "base_ref": "arch/gpt-synthesis-v1",
            "publish_branch": False,
        },
        headers=auth(),
    )
    assert response.status == 202
    body = await response.json()
    job_id = body["job_id"]
    assert body["status"] == "dispatched"
    stored = store.get_job(job_id)
    assert stored["kind"] == "code"
    assert stored["status"] == "dispatched"
    assert stored["checkpoint"]["base_ref"] == "arch/gpt-synthesis-v1"
    assert worker.dispatched[0][0] == job_id

    refreshed = await client.get(f"/api/jobs/{job_id}", headers=auth())
    assert refreshed.status == 200
    job = (await refreshed.json())["job"]
    assert job["status"] == "succeeded"
    assert job["checkpoint"]["remote_run_id"] == 123


@pytest.mark.asyncio
async def test_coding_job_fails_closed_without_worker(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "no-worker.sqlite3")
    agent = Agent(store, FakeRouter(), settings)
    client = await aiohttp_client(
        create_app(agent, settings, auth_token="test-token", coding_worker=None)
    )
    response = await client.post(
        "/api/jobs/code",
        json={"task": "do work"},
        headers=auth(),
    )
    assert response.status == 503
    assert (await response.json())["error"] == "coding_worker_unavailable"


@pytest.mark.asyncio
async def test_ui_preserves_partial_stream_without_requeue(client):
    response = await client.get("/")
    html = await response.text()
    assert "let buffer='',answer='',streamError=null,sawDone=false;" in html
    assert "if(raw==='[DONE]'){sawDone=true;return}" in html
    assert "assistant.status='partial'" in html
    assert "userMessage.status='synced'" in html
    assert "if(streamError||!sawDone)throw new Error" in html


@pytest.mark.asyncio
async def test_owner_login_sets_http_only_cookie_and_unlocks_api(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "auth.sqlite3")
    agent = Agent(store, FakeRouter(), settings)
    verifier = make_password_verifier("owner-passphrase", salt=b"0123456789abcdef")
    client = await aiohttp_client(
        create_app(
            agent,
            settings,
            auth_token="gateway-signing-secret",
            owner_password_verifier=verifier,
        )
    )

    wrong = await client.post("/api/auth/login", json={"password": "wrong"})
    assert wrong.status == 401

    login = await client.post("/api/auth/login", json={"password": "owner-passphrase"})
    assert login.status == 200
    cookie = login.cookies["olivia_owner"]
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"].lower() == "strict"

    response = await client.get(
        "/api/sessions",
        headers={"Cookie": f"olivia_owner={cookie.value}"},
    )
    assert response.status == 200

    health = await client.get("/healthz")
    body = await health.json()
    assert body["api_mode"] == "canonical"
    assert body["owner_auth_configured"] is True


@pytest.mark.asyncio
async def test_owner_logout_expires_cookie(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "logout.sqlite3")
    agent = Agent(store, FakeRouter(), settings)
    verifier = make_password_verifier("owner-passphrase", salt=b"0123456789abcdef")
    client = await aiohttp_client(
        create_app(
            agent,
            settings,
            auth_token="gateway-signing-secret",
            owner_password_verifier=verifier,
        )
    )
    login = await client.post("/api/auth/login", json={"password": "owner-passphrase"})
    cookie = login.cookies["olivia_owner"]
    logout = await client.post(
        "/api/auth/logout",
        headers={"Cookie": f"olivia_owner={cookie.value}"},
    )
    assert logout.status == 200
    cleared = logout.cookies["olivia_owner"]
    assert cleared["max-age"] == "0"


@pytest.mark.asyncio
async def test_browser_can_use_canonical_core_without_exposing_gateway_secret(client):
    html = await (await client.get("/")).text()
    assert "ensureRemoteSession" in html
    assert "backendMode==='canonical'" in html
    assert "showOwnerLogin" in html
    assert "credentials:'same-origin'" in html
    assert "remoteSessionId" in html
    assert "OLIVIA_GATEWAY_TOKEN" not in html
    assert "Bearer " not in html


@pytest.mark.asyncio
async def test_session_creation_can_import_redacted_history(client, gateway):
    _, store, _ = gateway
    secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    response = await client.post(
        "/api/sessions",
        json={
            "title": "Migrado",
            "messages": [
                {"role": "user", "content": f"token {secret}"},
                {"role": "assistant", "content": "respuesta previa"},
            ],
        },
        headers=auth(),
    )
    assert response.status == 201
    session_id = (await response.json())["id"]
    messages = store.recent_messages(session_id)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert secret not in repr(messages)
    assert "[REDACTED_SECRET]" in messages[0]["content"]


@pytest.mark.asyncio
async def test_ui_can_switch_from_bridge_to_canonical_cookie_sessions(client):
    response = await client.get("/")
    html = await response.text()
    assert "backendMode='bridge'" in html
    assert "body.api_mode==='canonical'" in html
    assert 'id="ownerLogin"' in html
    assert 'type="password"' in html
    assert "credentials:'same-origin'" in html
    assert "ensureRemoteSession" in html
    assert "/api/auth/login" in html
    assert "/api/sessions" in html
    assert "/api/chat/${chat.remoteSessionId}" in html
    assert "Authorization" not in html


@pytest.mark.asyncio
async def test_ui_can_use_canonical_cookie_auth_and_server_sessions(client):
    response = await client.get("/")
    html = await response.text()
    assert 'id="ownerLogin"' in html
    assert 'id="ownerLoginForm"' in html
    assert "credentials:'same-origin'" in html
    assert "/api/auth/login" in html
    assert "/api/sessions" in html
    assert "ensureRemoteSession" in html
    assert "syncCanonicalSessions" in html
    assert "event.type==='delta'" in html
    assert "ev?.type==='done'" in html
    assert "Authorization" not in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html


@pytest.mark.asyncio
async def test_owner_login_rate_limits_repeated_failures(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "login-rate.sqlite3")
    agent = Agent(store, FakeRouter(), settings)
    verifier = make_password_verifier("owner-passphrase", salt=b"0123456789abcdef")
    client = await aiohttp_client(
        create_app(
            agent,
            settings,
            auth_token="gateway-signing-secret",
            owner_password_verifier=verifier,
        )
    )

    for _ in range(5):
        response = await client.post("/api/auth/login", json={"password": "wrong"})
        assert response.status == 401

    limited = await client.post("/api/auth/login", json={"password": "owner-passphrase"})
    assert limited.status == 429
    assert int(limited.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_owner_login_rate_limits_repeated_failures(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "rate-limit.sqlite3")
    agent = Agent(store, FakeRouter(), settings)
    verifier = make_password_verifier("owner-passphrase", salt=b"0123456789abcdef")
    client = await aiohttp_client(
        create_app(
            agent,
            settings,
            auth_token="gateway-signing-secret",
            owner_password_verifier=verifier,
        )
    )

    for _ in range(5):
        response = await client.post("/api/auth/login", json={"password": "wrong"})
        assert response.status == 401

    blocked = await client.post("/api/auth/login", json={"password": "owner-passphrase"})
    assert blocked.status == 429
    assert blocked.headers["Retry-After"]


@pytest.mark.asyncio
async def test_successful_owner_login_clears_failure_counter(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "rate-reset.sqlite3")
    agent = Agent(store, FakeRouter(), settings)
    verifier = make_password_verifier("owner-passphrase", salt=b"0123456789abcdef")
    client = await aiohttp_client(
        create_app(
            agent,
            settings,
            auth_token="gateway-signing-secret",
            owner_password_verifier=verifier,
        )
    )

    assert (await client.post("/api/auth/login", json={"password": "wrong"})).status == 401
    assert (await client.post("/api/auth/login", json={"password": "owner-passphrase"})).status == 200
    assert (await client.post("/api/auth/login", json={"password": "wrong"})).status == 401


@pytest.mark.asyncio
async def test_code_command_dispatches_durable_isolated_job_without_chat_model(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "code-command.sqlite3")
    router = FakeRouter(parts=("MODEL_SHOULD_NOT_RUN",))
    agent = Agent(store, router, settings)
    worker = FakeCodingWorker()
    client = await aiohttp_client(
        create_app(agent, settings, auth_token="test-token", coding_worker=worker)
    )
    session_id = store.create_session("coding")

    response = await client.post(
        f"/api/chat/{session_id}",
        json={"text": "/code Implementá una validación robusta."},
        headers=auth(),
    )
    assert response.status == 200
    events = [
        json.loads(line[6:])
        for line in (await response.text()).splitlines()
        if line.startswith("data: ")
    ]
    job = next(event for event in events if event.get("type") == "job")
    assert job["mode"] == "implement"
    assert job["status"] == "dispatched"
    assert any(event.get("type") == "delta" and "rama aislada" in event.get("text", "") for event in events)
    assert worker.dispatched
    _, request = worker.dispatched[0]
    assert request.mode == "implement"
    assert request.publish_branch is True
    messages = store.recent_messages(session_id)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert "MODEL_SHOULD_NOT_RUN" not in repr(messages)


@pytest.mark.asyncio
async def test_repair_command_uses_repair_mode(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "repair-command.sqlite3")
    agent = Agent(store, FakeRouter(), settings)
    worker = FakeCodingWorker()
    client = await aiohttp_client(
        create_app(agent, settings, auth_token="test-token", coding_worker=worker)
    )
    session_id = store.create_session("repair")

    response = await client.post(
        f"/api/chat/{session_id}",
        json={"text": "/repair Arreglá únicamente el test roto."},
        headers=auth(),
    )
    assert response.status == 200
    await response.read()
    _, request = worker.dispatched[0]
    assert request.mode == "repair"
    assert request.publish_branch is True


@pytest.mark.asyncio
async def test_job_command_refreshes_existing_coding_job(aiohttp_client, tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / "job-command.sqlite3")
    agent = Agent(store, FakeRouter(), settings)
    worker = FakeCodingWorker()
    client = await aiohttp_client(
        create_app(agent, settings, auth_token="test-token", coding_worker=worker)
    )
    session_id = store.create_session("status")
    job_id = store.create_job("code", repo=worker.repo)
    store.checkpoint_job(job_id, "dispatched", {"mode": "implement"})

    response = await client.post(
        f"/api/chat/{session_id}",
        json={"text": f"/job {job_id}"},
        headers=auth(),
    )
    events = [
        json.loads(line[6:])
        for line in (await response.text()).splitlines()
        if line.startswith("data: ")
    ]
    assert any(event.get("type") == "job" and event.get("status") == "succeeded" for event in events)
    assert any(event.get("type") == "delta" and "succeeded" in event.get("text", "") for event in events)


@pytest.mark.asyncio
async def test_ui_uses_cloud_workspace_as_canonical_source(client):
    html = await (await client.get("/")).text()
    assert "syncCanonicalWorkspace" in html
    assert "migrateLocalWorkspace" in html
    assert "/api/workspace" in html
    assert "/api/projects" in html
    assert "/api/library" in html
    assert "/api/memories" in html
    assert "project_id" in html
