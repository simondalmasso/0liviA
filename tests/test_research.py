from __future__ import annotations

import json

import pytest

from olivia.research import (
    CloudflareWebSearch,
    SearchUnavailable,
    web_search_from_env,
)


def test_web_search_is_disabled_by_default(monkeypatch):
    for name in (
        "OLIVIA_WEB_SEARCH_ENABLED",
        "OLIVIA_WEB_SEARCH_ZERO_COST_VERIFIED",
        "OLIVIA_CF_ACCOUNT_ID",
        "OLIVIA_CF_API_TOKEN",
        "OLIVIA_CF_WEB_SEARCH_BYOK_ALIAS",
    ):
        monkeypatch.delenv(name, raising=False)
    assert web_search_from_env() is None


def test_cloudflare_search_requires_verified_zero_cost_byok(monkeypatch):
    monkeypatch.setenv("OLIVIA_WEB_SEARCH_ENABLED", "1")
    monkeypatch.setenv("OLIVIA_CF_ACCOUNT_ID", "account")
    monkeypatch.setenv("OLIVIA_CF_API_TOKEN", "token")
    monkeypatch.setenv("OLIVIA_CF_WEB_SEARCH_BYOK_ALIAS", "free-search")

    monkeypatch.delenv("OLIVIA_WEB_SEARCH_ZERO_COST_VERIFIED", raising=False)
    with pytest.raises(SearchUnavailable):
        web_search_from_env()

    monkeypatch.setenv("OLIVIA_WEB_SEARCH_ZERO_COST_VERIFIED", "1")
    search = web_search_from_env()
    assert isinstance(search, CloudflareWebSearch)
    assert search.byok_alias == "free-search"


@pytest.mark.asyncio
async def test_cloudflare_search_sends_byok_alias_and_never_implicit_credits():
    calls = []

    class FakeResponse:
        status = 200
        headers = {"content-type": "application/json"}

        async def read(self):
            return json.dumps({
                "items": [
                    {
                        "url": "https://example.com/a",
                        "title": "A",
                        "description": "desc",
                    }
                ],
                "metadata": {"query": "demo", "requestId": "r1", "latencyMs": 12},
            }).encode()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class FakeSession:
        def post(self, url, *, json, headers):
            calls.append((url, json, headers))
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    search = CloudflareWebSearch(
        account_id="acct",
        api_token="secret-token",
        gateway_id="default",
        provider="exa",
        byok_alias="verified-free",
        zero_cost_verified=True,
        session_factory=lambda **_: FakeSession(),
    )
    result = await search.search("qué pasó hoy", limit=3)

    assert result["items"][0]["url"] == "https://example.com/a"
    assert len(calls) == 1
    _, payload, headers = calls[0]
    assert payload["byokAlias"] == "verified-free"
    assert payload["provider"] == "exa"
    assert payload["limit"] == 3
    assert "secret-token" not in repr(result)
    assert headers["Authorization"] == "Bearer secret-token"
    assert headers["cf-aig-no-wholesale"] == "true"


@pytest.mark.asyncio
async def test_cloudflare_search_fails_closed_when_unverified():
    search = CloudflareWebSearch(
        account_id="acct",
        api_token="token",
        gateway_id="default",
        provider="exa",
        byok_alias="free",
        zero_cost_verified=False,
    )
    with pytest.raises(SearchUnavailable):
        await search.search("hola")


def test_cloudflare_byok_alias_matches_official_contract():
    with pytest.raises(ValueError):
        CloudflareWebSearch(
            account_id="acct",
            api_token="token",
            gateway_id="default",
            provider="exa",
            byok_alias="alias with spaces",
            zero_cost_verified=True,
        )
    with pytest.raises(ValueError):
        CloudflareWebSearch(
            account_id="acct",
            api_token="token",
            gateway_id="default",
            provider="exa",
            byok_alias="x" * 65,
            zero_cost_verified=True,
        )
