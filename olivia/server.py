from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from aiohttp import web

from .agent import Agent
from .config import Settings
from .router import ProviderPool
from .store import Store

MAX_BODY_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 12_000
MAX_TITLE_CHARS = 200


def _json(payload: dict[str, Any], status: int = 200) -> web.Response:
    return web.json_response(payload, status=status, dumps=lambda value: json.dumps(value, ensure_ascii=False))


class Gateway:
    def __init__(self, agent: Agent, settings: Settings, *, auth_token: str | None = None):
        self.agent = agent
        self.settings = settings
        self.auth_token = auth_token if auth_token is not None else os.getenv("OLIVIA_GATEWAY_TOKEN", "")
        self._turns: dict[str, asyncio.Task[None]] = {}
        self._turns_lock = asyncio.Lock()

    def _authorized(self, request: web.Request) -> bool:
        if not self.auth_token:
            return False
        supplied = request.headers.get("Authorization", "")
        scheme, _, value = supplied.partition(" ")
        return scheme.lower() == "bearer" and secrets.compare_digest(value, self.auth_token)

    async def _require_auth(self, request: web.Request) -> web.Response | None:
        if self._authorized(request):
            return None
        return _json({"error": "unauthorized"}, status=401)

    async def _read_json(self, request: web.Request) -> dict[str, Any]:
        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    raise web.HTTPRequestEntityTooLarge(max_size=MAX_BODY_BYTES, actual_size=int(content_length))
            except ValueError:
                raise web.HTTPBadRequest(text="invalid Content-Length")
        raw = await request.content.read(MAX_BODY_BYTES + 1)
        if len(raw) > MAX_BODY_BYTES:
            raise web.HTTPRequestEntityTooLarge(max_size=MAX_BODY_BYTES, actual_size=len(raw))
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise web.HTTPBadRequest(text="body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest(text="body must be a JSON object")
        return payload

    async def healthz(self, request: web.Request) -> web.Response:
        providers = list(self.agent.router.providers)
        configured = 0
        available = 0
        for provider in providers:
            configured += 1
            spec = getattr(provider, "spec", None)
            env_name = getattr(spec, "api_key_env", "")
            if env_name and os.getenv(env_name):
                state = self.agent.store.provider_state(provider.name)
                if float(state["cooldown_until"]) <= time.time() and (
                    not provider.daily_limit or int(state["daily_requests"]) < provider.daily_limit
                ):
                    available += 1
        return _json({
            "process_alive": True,
            "provider_configured": bool(configured),
            "provider_ready": bool(available),
            "providers_configured": configured,
            "providers_available": available,
        })

    async def create_session(self, request: web.Request) -> web.Response:
        denied = await self._require_auth(request)
        if denied:
            return denied
        payload = await self._read_json(request)
        title = payload.get("title", "")
        if not isinstance(title, str) or len(title) > MAX_TITLE_CHARS:
            return _json({"error": "title must be a string of at most 200 characters"}, 400)
        session_id = self.agent.store.create_session(title)
        return _json({"id": session_id, "title": title}, 201)

    async def get_messages(self, request: web.Request) -> web.Response:
        denied = await self._require_auth(request)
        if denied:
            return denied
        session_id = request.match_info["session_id"]
        if not self.agent.store.session_exists(session_id):
            return _json({"error": "session not found"}, 404)
        limit_raw = request.query.get("limit", "100")
        try:
            limit = max(1, min(int(limit_raw), 200))
        except ValueError:
            return _json({"error": "limit must be an integer"}, 400)
        return _json({"session_id": session_id, "messages": self.agent.store.recent_messages(session_id, limit)})

    async def chat(self, request: web.Request) -> web.StreamResponse:
        denied = await self._require_auth(request)
        if denied:
            return denied
        session_id = request.match_info["session_id"]
        if not self.agent.store.session_exists(session_id):
            return _json({"error": "session not found"}, 404)
        payload = await self._read_json(request)
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_MESSAGE_CHARS:
            return _json({"error": "text must be a non-empty string of at most 12000 characters"}, 400)
        async with self._turns_lock:
            active = self._turns.get(session_id)
            if active and not active.done():
                return _json({"error": "turn already active", "session_id": session_id}, 409)
            response = web.StreamResponse(status=200, headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            })
            await response.prepare(request)
            task = asyncio.create_task(self._stream_turn(response, session_id, text.strip()))
            self._turns[session_id] = task
        try:
            await task
        finally:
            async with self._turns_lock:
                if self._turns.get(session_id) is task:
                    self._turns.pop(session_id, None)
        return response

    async def _stream_turn(self, response: web.StreamResponse, session_id: str, text: str) -> None:
        try:
            async for event in self.agent.stream_turn(session_id, text):
                await response.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
            await response.write_eof()
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
            # Cancelling the handler cancels Agent.stream_turn and its provider HTTP request.
            raise
        except (web.HTTPException, OSError):
            raise
        except Exception as exc:
            # Do not expose provider internals; Agent already records the turn event.
            try:
                await response.write(f"data: {json.dumps({'type': 'error', 'error': 'gateway stream failed'}, ensure_ascii=False)}\n\n".encode())
                await response.write_eof()
            except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
                raise


def create_app(agent: Agent | None = None, settings: Settings | None = None, *, auth_token: str | None = None) -> web.Application:
    settings = settings or Settings.from_env()
    if agent is None:
        store = Store(settings.db_path)
        agent = Agent(store, ProviderPool.from_settings(settings, store), settings)
    gateway = Gateway(agent, settings, auth_token=auth_token)
    app = web.Application(client_max_size=MAX_BODY_BYTES)
    app["gateway"] = gateway
    app.router.add_get("/healthz", gateway.healthz)
    app.router.add_post("/api/sessions", gateway.create_session)
    app.router.add_get("/api/sessions/{session_id}/messages", gateway.get_messages)
    app.router.add_post("/api/chat/{session_id}", gateway.chat)
    return app


def main() -> None:
    settings = Settings.from_env()
    web.run_app(create_app(settings=settings), host=settings.bind, port=settings.port)


if __name__ == "__main__":
    main()
