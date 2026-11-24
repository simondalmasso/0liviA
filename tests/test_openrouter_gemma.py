import pytest

from olivia.config import Settings
from olivia.router import (
    OpenAICompatibleProvider,
    ProviderConfigError,
    ProviderPool,
    ProviderSpec,
)
from olivia.store import Store


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GEMMA_MODEL = "google/gemma-4-26b-a4b-it:free"


def _openrouter_spec(**overrides):
    raw = {
        "name": "gemma-4-26b-a4b-free",
        "base_url": OPENROUTER_BASE_URL,
        "model": GEMMA_MODEL,
        "api_key_env": "OPENROUTER_API_KEY",
        "priority": 50,
        "daily_limit": 35,
        "max_output_tokens": 512,
        "cost_mode": "free_hard_cap",
        "capabilities": ["chat"],
        "fallback_policy": "stop",
    }
    raw.update(overrides)
    return ProviderSpec.from_dict(raw)


@pytest.mark.parametrize(
    "model",
    [
        "google/gemma-4-26b-a4b-it",
        "google/gemma-4-26b-a4b-it:paid",
        "openrouter/free",
        "google/gemma-4-26b-a4b-it:free/../paid",
    ],
)
def test_openrouter_free_hard_cap_rejects_models_not_explicitly_free(model):
    with pytest.raises(ProviderConfigError, match="explicit :free model ID"):
        _openrouter_spec(model=model)


def test_openrouter_free_hard_cap_requires_stop_fallback_policy():
    with pytest.raises(ProviderConfigError, match="fallback_policy=stop"):
        _openrouter_spec(fallback_policy="allow")


def test_gemma_free_profile_is_admitted_as_chat_only(tmp_path):
    spec = {
        "name": "gemma-4-26b-a4b-free",
        "base_url": OPENROUTER_BASE_URL,
        "model": GEMMA_MODEL,
        "api_key_env": "OPENROUTER_API_KEY",
        "priority": 50,
        "daily_limit": 35,
        "max_output_tokens": 512,
        "cost_mode": "free_hard_cap",
        "capabilities": ["chat"],
        "fallback_policy": "stop",
    }
    pool = ProviderPool.from_settings(
        Settings(data_dir=tmp_path, hard_zero_cost=True, providers=(spec,)),
        Store(tmp_path / "router.sqlite3"),
    )

    assert len(pool.providers) == 1
    provider = pool.providers[0]
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.spec.base_url == OPENROUTER_BASE_URL
    assert provider.spec.model == GEMMA_MODEL
    assert provider.daily_limit == 35
    assert provider.cost_mode == "free_hard_cap"
    assert provider.capabilities == ("chat",)
    assert provider.fallback_policy == "stop"


def test_openrouter_free_profile_is_blocked_when_hard_zero_cost_is_off(tmp_path):
    # Gemma's free alias is admitted only through the normal, enabled cost guard.
    # This test pins the default production policy; callers must not disable it.
    settings = Settings(
        data_dir=tmp_path,
        hard_zero_cost=False,
        providers=({
            "name": "gemma-4-26b-a4b-free",
            "base_url": OPENROUTER_BASE_URL,
            "model": GEMMA_MODEL,
            "api_key_env": "OPENROUTER_API_KEY",
            "daily_limit": 35,
            "cost_mode": "free_hard_cap",
            "capabilities": ["chat"],
            "fallback_policy": "stop",
        },),
    )
    # The project Settings constructor intentionally carries the invariant as True.
    assert settings.hard_zero_cost is True
    pool = ProviderPool.from_settings(settings, Store(tmp_path / "cost-guard.sqlite3"))
    assert len(pool.providers) == 1
    assert pool.metrics()["hard_zero_cost"] is True


@pytest.mark.asyncio
async def test_openrouter_gemma_uses_pinned_free_model_and_server_side_bearer_key(
    monkeypatch,
):
    import olivia.router as router

    sent = []

    class MockResponse:
        status = 200
        headers = {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        @property
        def content(self):
            async def lines():
                yield b'data: {"choices":[{"delta":{"content":"ok"}}]}\\n'
                yield b'data: [DONE]\\n'
            return lines()

    class MockSession:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def post(self, url, *, json, headers):
            sent.append({"url": url, "json": json, "headers": headers})
            return MockResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-not-for-logs")
    monkeypatch.setattr(router.aiohttp, "ClientSession", MockSession)
    provider = OpenAICompatibleProvider(_openrouter_spec())

    chunks = [
        item
        async for item in provider.stream([{"role": "user", "content": "Respondé: listo"}])
    ]

    assert chunks == ["ok"]
    assert sent[0]["url"] == OPENROUTER_BASE_URL + "/chat/completions"
    assert sent[0]["json"]["model"] == GEMMA_MODEL
    assert sent[0]["json"]["max_tokens"] == 512
    assert sent[0]["json"]["stream"] is True
    assert sent[0]["headers"]["Authorization"] == "Bearer test-secret-not-for-logs"
