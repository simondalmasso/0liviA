from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from olivia.agent import Agent, SYSTEM_PROMPT
from olivia.config import Settings
from olivia.router import RouteEvent
from olivia.store import Store


class CaptureRouter:
    def __init__(self):
        self.providers = []
        self.calls = []

    async def stream(self, messages) -> AsyncIterator[RouteEvent]:
        self.calls.append(messages)
        yield RouteEvent(type="route", provider="fake")
        yield RouteEvent(type="delta", provider="fake", text="respuesta")


@pytest.mark.asyncio
async def test_explicit_memory_command_is_local_and_durable(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    sid = store.create_session()
    router = CaptureRouter()
    agent = Agent(store, router, Settings(data_dir=tmp_path))

    events = [event async for event in agent.stream_turn(
        sid,
        "/recordar ciudad = Santa Fe",
    )]
    assert router.calls == []
    assert [event["type"] for event in events] == ["memory", "delta", "done"]
    memories = store.list_memories("global")
    assert memories[0]["key"] == "ciudad"
    assert memories[0]["value"] == "Santa Fe"
    assert memories[0]["source"] == "explicit-user"

    _ = [event async for event in agent.stream_turn(sid, "¿En qué ciudad estoy?")]
    assert router.calls
    system = router.calls[-1][0]["content"]
    assert "[global:ciudad] Santa Fe" in system
    assert "Spanish from Argentina (es-AR)" in system


@pytest.mark.asyncio
async def test_forget_command_deactivates_without_provider_call(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    sid = store.create_session()
    store.promote_memory("global", "tema", "valor", source="test")
    router = CaptureRouter()
    agent = Agent(store, router, Settings(data_dir=tmp_path))

    events = [event async for event in agent.stream_turn(sid, "/olvidar tema")]
    assert router.calls == []
    assert events[0]["action"] == "forgotten"
    assert store.list_memories("global") == []


def test_kernel_prompt_locks_default_locale():
    assert "Spanish from Argentina (es-AR)" in SYSTEM_PROMPT
    assert "Do not switch language unless the user explicitly asks" in SYSTEM_PROMPT
