import pytest

from olivia.config import Settings
from olivia.router import ProviderPool, ProviderStreamInterrupted
from olivia.store import Store


class FakeProvider:
    def __init__(
        self,
        name,
        parts,
        *,
        priority=10,
        daily_limit=0,
        fail_before=False,
        fail_after=False,
        capabilities=("chat",),
    ):
        self.name = name
        self.parts = parts
        self.priority = priority
        self.daily_limit = daily_limit
        self.fail_before = fail_before
        self.fail_after = fail_after
        self.capabilities = tuple(capabilities)

    async def stream(self, messages):
        if self.fail_before:
            raise RuntimeError("before")
        for i, part in enumerate(self.parts):
            yield part
            if self.fail_after and i == 0:
                raise RuntimeError("after")


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, ttft_timeout_s=1, circuit_base_s=1, circuit_max_s=2)


@pytest.mark.asyncio
async def test_failover_only_before_first_token(tmp_path, settings):
    store = Store(tmp_path / "db.sqlite3")
    pool = ProviderPool(
        [
            FakeProvider("dead", [], priority=1, fail_before=True),
            FakeProvider("alive", ["hello", " world"], priority=2),
        ],
        store,
        settings,
    )
    events = [e async for e in pool.stream([{"role": "user", "content": "x"}])]
    assert [e.type for e in events] == ["route", "delta", "delta"]
    assert events[0].provider == "alive"
    assert "".join(e.text or "" for e in events if e.type == "delta") == "hello world"


@pytest.mark.asyncio
async def test_no_failover_after_first_token(tmp_path, settings):
    store = Store(tmp_path / "db.sqlite3")
    pool = ProviderPool(
        [
            FakeProvider("partial", ["hello"], priority=1, fail_after=True),
            FakeProvider("must-not-run", ["fallback"], priority=2),
        ],
        store,
        settings,
    )
    with pytest.raises(ProviderStreamInterrupted):
        _ = [e async for e in pool.stream([{"role": "user", "content": "x"}])]


def test_hard_zero_cost_blocks_unverified_and_paid_routes(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        hard_zero_cost=True,
        providers=(
            {
                "name": "safe",
                "base_url": "https://safe.example/v1",
                "model": "m",
                "api_key_env": "SAFE_KEY",
                "cost_mode": "free_hard_cap",
            },
            {
                "name": "maybe-free",
                "base_url": "https://maybe.example/v1",
                "model": "m",
                "api_key_env": "MAYBE_KEY",
                "cost_mode": "free_unverified",
            },
            {
                "name": "paid",
                "base_url": "https://paid.example/v1",
                "model": "m",
                "api_key_env": "PAID_KEY",
                "cost_mode": "paid",
            },
        ),
    )
    store = Store(tmp_path / "db.sqlite3")
    pool = ProviderPool.from_settings(settings, store)
    assert [p.name for p in pool.providers] == ["safe"]
    assert pool.zero_cost_blocked == [
        {"provider": "maybe-free", "cost_mode": "free_unverified"},
        {"provider": "paid", "cost_mode": "paid"},
    ]
    assert pool.metrics()["hard_zero_cost"] is True


def test_zero_cost_provider_mode_is_fail_closed_when_omitted(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        hard_zero_cost=True,
        providers=(
            {
                "name": "legacy",
                "base_url": "https://legacy.example/v1",
                "model": "m",
                "api_key_env": "LEGACY_KEY",
            },
        ),
    )
    store = Store(tmp_path / "db.sqlite3")
    pool = ProviderPool.from_settings(settings, store)
    assert pool.providers == []
    assert pool.zero_cost_blocked == [
        {"provider": "legacy", "cost_mode": "free_unverified"}
    ]


def test_local_provider_allows_no_api_key(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        hard_zero_cost=True,
        providers=(
            {
                "name": "ollama-local",
                "base_url": "http://127.0.0.1:11434/v1",
                "model": "qwen3:1.7b",
                "cost_mode": "local",
                "priority": 1,
            },
        ),
    )
    store = Store(tmp_path / "db.sqlite3")
    pool = ProviderPool.from_settings(settings, store)
    assert len(pool.providers) == 1
    provider = pool.providers[0]
    assert provider.name == "ollama-local"
    assert provider.spec.api_key_env == ""
    assert provider.cost_mode == "local"


def test_chatgpt_plan_route_requires_no_credit_overage_verification(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        hard_zero_cost=True,
        providers=(
            {
                "name": "chatgpt-plan",
                "kind": "chatgpt_plan",
                "model": "gpt-6-astra",
                "profile_path": str(tmp_path / "chatgpt-plan.json"),
                "priority": 1,
                "cost_mode": "plan_included",
                "no_credit_overage_verified": False,
            },
        ),
    )
    store = Store(tmp_path / "db.sqlite3")
    pool = ProviderPool.from_settings(settings, store)
    assert pool.providers == []
    assert pool.zero_cost_blocked == [
        {"provider": "chatgpt-plan", "cost_mode": "plan_included"}
    ]


def test_chatgpt_plan_route_is_eligible_after_no_credit_overage_verification(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        hard_zero_cost=True,
        providers=(
            {
                "name": "chatgpt-plan",
                "kind": "chatgpt_plan",
                "model": "gpt-6-astra",
                "profile_path": str(tmp_path / "chatgpt-plan.json"),
                "priority": 1,
                "cost_mode": "plan_included",
                "no_credit_overage_verified": True,
            },
        ),
    )
    store = Store(tmp_path / "db.sqlite3")
    pool = ProviderPool.from_settings(settings, store)
    assert len(pool.providers) == 1
    provider = pool.providers[0]
    assert provider.name == "chatgpt-plan"
    assert provider.model == "gpt-6-astra"
    assert provider.cost_mode == "plan_included"


def test_provider_capabilities_default_to_chat_and_reject_unknown(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        hard_zero_cost=True,
        providers=(
            {
                "name": "legacy-chat",
                "base_url": "https://safe.example/v1",
                "model": "m",
                "api_key_env": "SAFE_KEY",
                "cost_mode": "free_hard_cap",
            },
        ),
    )
    store = Store(tmp_path / "db.sqlite3")
    pool = ProviderPool.from_settings(settings, store)
    assert pool.providers[0].capabilities == ("chat",)

    bad = Settings(
        data_dir=tmp_path,
        providers=(
            {
                "name": "bad",
                "base_url": "https://safe.example/v1",
                "model": "m",
                "cost_mode": "local",
                "capabilities": ["chat", "telepathy"],
            },
        ),
    )
    with pytest.raises(Exception, match="capabilit"):
        ProviderPool.from_settings(bad, Store(tmp_path / "bad.sqlite3"))


@pytest.mark.asyncio
async def test_capability_routing_only_attempts_matching_providers(tmp_path, settings):
    store = Store(tmp_path / "cap.sqlite3")
    pool = ProviderPool(
        [
            FakeProvider("chat-only", ["wrong"], priority=1, capabilities=("chat",)),
            FakeProvider("research", ["grounded"], priority=2, capabilities=("research",)),
        ],
        store,
        settings,
    )
    events = [
        event
        async for event in pool.stream(
            [{"role": "user", "content": "x"}],
            capability="research",
        )
    ]
    assert events[0].provider == "research"
    assert "".join(event.text or "" for event in events if event.type == "delta") == "grounded"


def test_provider_catalog_exposes_models_capabilities_without_secrets(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        hard_zero_cost=True,
        providers=(
            {
                "name": "frontier",
                "base_url": "https://safe.example/v1",
                "model": "model-x",
                "api_key_env": "VERY_SECRET_ENV_NAME",
                "cost_mode": "free_hard_cap",
                "capabilities": ["chat", "research", "vision"],
                "priority": 3,
            },
        ),
    )
    pool = ProviderPool.from_settings(settings, Store(tmp_path / "catalog.sqlite3"))
    catalog = pool.catalog()
    assert catalog == [
        {
            "name": "frontier",
            "model": "model-x",
            "priority": 3,
            "daily_limit": 0,
            "cost_mode": "free_hard_cap",
            "capabilities": ["chat", "research", "vision"],
        }
    ]
    assert "VERY_SECRET_ENV_NAME" not in repr(catalog)


def test_openai_compatible_configured_state_is_transport_aware(tmp_path, monkeypatch):
    local = OpenAICompatibleProvider(
        ProviderSpec(
            name="local",
            base_url="http://127.0.0.1:11434/v1",
            model="local-model",
            api_key_env="",
            cost_mode="local",
        )
    )
    assert local.configured is True

    remote = OpenAICompatibleProvider(
        ProviderSpec(
            name="remote",
            base_url="https://example.com/v1",
            model="remote-model",
            api_key_env="REMOTE_KEY",
            cost_mode="free_hard_cap",
        )
    )
    monkeypatch.delenv("REMOTE_KEY", raising=False)
    assert remote.configured is False
    monkeypatch.setenv("REMOTE_KEY", "test-key")
    assert remote.configured is True
