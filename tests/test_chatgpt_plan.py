import json
import os
import stat
import time
from pathlib import Path

import pytest

from olivia.router import (
    ChatGPTPlanProvider,
    ProviderConfigError,
    ProviderHTTPError,
    ProviderSpec,
)


class FakeContent:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class FakeResponse:
    def __init__(self, status=200, *, json_body=None, text_body="", chunks=(), headers=None):
        self.status = status
        self._json_body = json_body
        self._text_body = text_body
        self.content = FakeContent(chunks)
        self.headers = headers or {}

    async def json(self):
        return self._json_body

    async def text(self):
        return self._text_body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


class FakeSession:
    def __init__(self, responses, calls, **kwargs):
        self._responses = responses
        self._calls = calls
        self._kwargs = kwargs

    def post(self, url, **kwargs):
        self._calls.append(("POST", url, kwargs))
        return self._responses.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


def write_profile(path: Path, **overrides):
    payload = {
        "client_id": "oaiapp_demo",
        "access_token": "access-demo",
        "refresh_token": "refresh-demo",
        "expires_at": int(time.time()) + 3600,
        "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
        "email": "owner@example.com",
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o600)
    return payload


def spec(path: Path, **overrides):
    raw = {
        "name": "chatgpt-plan",
        "kind": "chatgpt_plan",
        "model": "gpt-6-astra",
        "profile_path": str(path),
        "priority": 1,
        "cost_mode": "plan_included",
        "no_credit_overage_verified": True,
    }
    raw.update(overrides)
    return ProviderSpec.from_dict(raw)


def test_chatgpt_plan_profile_requires_private_permissions(tmp_path):
    profile = tmp_path / "profile.json"
    write_profile(profile)
    os.chmod(profile, 0o644)
    provider = ChatGPTPlanProvider(spec(profile))
    with pytest.raises(ProviderConfigError):
        provider._load_profile()


def test_chatgpt_plan_profile_requires_plan_usage_scope(tmp_path):
    profile = tmp_path / "profile.json"
    write_profile(profile, scope="openid profile email")
    provider = ChatGPTPlanProvider(spec(profile))
    with pytest.raises(ProviderConfigError):
        provider._load_profile()


@pytest.mark.asyncio
async def test_chatgpt_plan_provider_uses_responses_stream_contract(tmp_path):
    profile = tmp_path / "profile.json"
    write_profile(profile)
    calls = []
    responses = [
        FakeResponse(
            chunks=(
                b'data: {"type":"response.created"}\n',
                b'data: {"type":"response.output_text.delta","delta":"hola"}\n',
                b'data: {"type":"response.output_text.delta","delta":" mundo"}\n',
                b'data: {"type":"response.completed"}\n',
            )
        )
    ]
    provider = ChatGPTPlanProvider(
        spec(profile),
        session_factory=lambda **kwargs: FakeSession(responses, calls, **kwargs),
    )

    text = "".join(
        [
            token
            async for token in provider.stream(
                [
                    {"role": "system", "content": "Respondé en es-AR."},
                    {"role": "user", "content": "hola"},
                ]
            )
        ]
    )
    assert text == "hola mundo"
    assert len(calls) == 1
    method, url, kwargs = calls[0]
    assert method == "POST"
    assert url == "https://api.openai.com/v1/responses"
    assert kwargs["headers"]["Authorization"] == "Bearer access-demo"
    payload = kwargs["json"]
    assert payload["model"] == "gpt-6-astra"
    assert payload["store"] is False
    assert payload["stream"] is True
    assert payload["instructions"] == "Respondé en es-AR."
    assert payload["input"] == [{"role": "user", "content": "hola"}]
    assert "max_output_tokens" not in payload
    assert "previous_response_id" not in payload


@pytest.mark.asyncio
async def test_chatgpt_plan_provider_refreshes_expired_profile_atomically(tmp_path):
    profile = tmp_path / "profile.json"
    write_profile(profile, expires_at=1)
    calls = []
    responses = [
        FakeResponse(
            json_body={
                "access_token": "fresh-access",
                "refresh_token": "fresh-refresh",
                "expires_in": 7200,
                "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
            }
        ),
        FakeResponse(
            chunks=(
                b'data: {"type":"response.output_text.delta","delta":"ok"}\n',
                b'data: {"type":"response.completed"}\n',
            )
        ),
    ]
    provider = ChatGPTPlanProvider(
        spec(profile),
        session_factory=lambda **kwargs: FakeSession(responses, calls, **kwargs),
    )

    assert "".join([token async for token in provider.stream([{"role": "user", "content": "x"}])]) == "ok"
    assert calls[0][1] == "https://auth.openai.com/api/accounts/oauth/token"
    assert calls[0][2]["data"]["grant_type"] == "refresh_token"
    assert calls[0][2]["data"]["client_id"] == "oaiapp_demo"
    assert calls[0][2]["data"]["resource"] == "https://api.openai.com/v1"
    saved = json.loads(profile.read_text(encoding="utf-8"))
    assert saved["access_token"] == "fresh-access"
    assert saved["refresh_token"] == "fresh-refresh"
    assert saved["expires_at"] > int(time.time())
    mode = stat.S_IMODE(profile.stat().st_mode)
    assert mode == 0o600


@pytest.mark.asyncio
async def test_chatgpt_plan_usage_limit_maps_to_rate_limit(tmp_path):
    profile = tmp_path / "profile.json"
    write_profile(profile)
    calls = []
    responses = [
        FakeResponse(
            chunks=(
                b'data: {"type":"response.failed","response":{"error":{"code":"subscription_sharing_usage_limit_exceeded"}}}\n',
            )
        )
    ]
    provider = ChatGPTPlanProvider(
        spec(profile),
        session_factory=lambda **kwargs: FakeSession(responses, calls, **kwargs),
    )
    with pytest.raises(ProviderHTTPError) as exc:
        _ = [token async for token in provider.stream([{"role": "user", "content": "x"}])]
    assert exc.value.status == 429
    assert "subscription_sharing_usage_limit_exceeded" in str(exc.value)
