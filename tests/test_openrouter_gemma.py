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

