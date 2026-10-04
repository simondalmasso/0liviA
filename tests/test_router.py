import pytest

from olivia.config import Settings
from olivia.router import ProviderPool, ProviderStreamInterrupted
from olivia.store import Store


class FakeProvider:
    def __init__(self, name, parts, *, priority=10, daily_limit=0, fail_before=False, fail_after=False):
        self.name = name
        self.parts = parts
        self.priority = priority
        self.daily_limit = daily_limit
        self.fail_before = fail_before
        self.fail_after = fail_after

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
