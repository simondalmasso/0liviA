from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from olivia.agent import Agent, SYSTEM_PROMPT
from olivia.config import Settings
from olivia.router import OpenAICompatibleProvider, ProviderSpec, RouteEvent
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


@pytest.mark.asyncio
async def test_secret_like_memory_is_rejected_and_never_persisted(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    sid = store.create_session()
    router = CaptureRouter()
    agent = Agent(store, router, Settings(data_dir=tmp_path))

    secret = "sk-proj-1234567890abcdefghijklmnopqrstuv"
    events = [event async for event in agent.stream_turn(
        sid,
        f"/recordar api = {secret}",
    )]

    assert router.calls == []
    assert events[0]["type"] == "memory"
    assert events[0]["action"] == "rejected_secret"
    assert store.list_memories("global") == []
    assert secret not in repr(store.recent_messages(sid))


@pytest.mark.asyncio
async def test_secret_like_user_text_is_redacted_before_storage_and_provider(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    sid = store.create_session()
    router = CaptureRouter()
    agent = Agent(store, router, Settings(data_dir=tmp_path))

    secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    _ = [event async for event in agent.stream_turn(sid, f"Usá {secret} para esto")]

    stored = repr(store.recent_messages(sid))
    outbound = repr(router.calls[-1])
    assert secret not in stored
    assert secret not in outbound
    assert "[REDACTED_SECRET]" in stored
    assert "[REDACTED_SECRET]" in outbound


@pytest.mark.asyncio
async def test_ephemeral_web_context_reaches_provider_but_not_durable_messages(tmp_path):
    store = Store(tmp_path / "web-context.sqlite3")
    sid = store.create_session()
    router = CaptureRouter()
    agent = Agent(store, router, Settings(data_dir=tmp_path))

    context = "UNIQUE_PAGE_FACT_42"
    _ = [
        event
        async for event in agent.stream_turn(
            sid,
            "/read https://example.com ¿qué dice?",
            ephemeral_context=context,
        )
    ]

    assert context in repr(router.calls[-1])
    assert context not in repr(store.recent_messages(sid))
    assert "untrusted external context" in router.calls[-1][0]["content"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "q modelo sos",
    "qué modelo usás?",
    "que modelo usas",
])
async def test_model_identity_question_is_local_exact_and_zero_cost(tmp_path, question):
    store = Store(tmp_path / "identity.sqlite3")
    sid = store.create_session()
    router = CaptureRouter()
    router.providers = [
        OpenAICompatibleProvider(
            ProviderSpec(
                name="deepseek-free",
                base_url="https://example.invalid/v1",
                model="deepseek-v4.1-flash",
                api_key_env="TEST_KEY",
                priority=1,
                cost_mode="free_hard_cap",
            )
        )
    ]
    agent = Agent(store, router, Settings(data_dir=tmp_path))

    events = [event async for event in agent.stream_turn(sid, question)]
    answer = "".join(event.get("text", "") for event in events if event["type"] == "delta")

    assert router.calls == []
    assert "Soy 0liviA" in answer
    assert "deepseek-v4.1-flash" in answer
    assert "deepseek-free" in answer
    assert "No tengo un modelo específico" not in answer
    assert "prioridad" in answer and "cuota" in answer and "salud" in answer
    assert answer in repr(store.recent_messages(sid))


@pytest.mark.asyncio
async def test_model_identity_never_invents_provider_when_none_configured(tmp_path):
    store = Store(tmp_path / "identity-empty.sqlite3")
    sid = store.create_session()
    router = CaptureRouter()
    agent = Agent(store, router, Settings(data_dir=tmp_path))

    events = [event async for event in agent.stream_turn(sid, "q modelo sos")]
    answer = "".join(event.get("text", "") for event in events if event["type"] == "delta")

    assert router.calls == []
    assert "Soy 0liviA" in answer
    assert "no tiene un modelo de inferencia configurado" in answer


@pytest.mark.asyncio
async def test_model_context_is_bounded_and_keeps_recent_turns(tmp_path):
    store = Store(tmp_path / "context-budget.sqlite3")
    sid = store.create_session()
    router = CaptureRouter()
    settings = Settings(data_dir=tmp_path, max_history=100, max_context_chars=16_000)
    agent = Agent(store, router, settings)

    for idx in range(20):
        store.append_message(sid, "user", f"OLD_{idx}_" + ("x" * 1800))
        store.append_message(sid, "assistant", f"ANSWER_{idx}_" + ("y" * 1800))

    _ = [
        event
        async for event in agent.stream_turn(
            sid,
            "CURRENT_QUESTION_" + ("z" * 1000),
            ephemeral_context="WEB_CONTEXT_" + ("w" * 20_000),
        )
    ]

    outbound = router.calls[-1]
    total = sum(len(message["content"]) for message in outbound)
    blob = repr(outbound)
    assert total <= settings.max_context_chars
    assert "CURRENT_QUESTION_" in blob
    assert "OLD_0_" not in blob
    assert "WEB_CONTEXT_" in blob
