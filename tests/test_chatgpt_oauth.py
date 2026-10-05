import json
import stat
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from olivia.chatgpt_oauth import (
    APP_NAME,
    DYNAMIC_CLIENT_ID,
    ChatGPTOAuthError,
    build_authorization_url,
    build_profile,
    disconnect_profile,
    load_or_create_host_id,
    new_transaction,
    save_profile,
    validate_id_token,
)


def synthetic(label: str) -> str:
    return "test-" + label + "-" + ("x" * 12)


def test_pkce_transaction_and_dynamic_registration_url(tmp_path):
    tx = new_transaction()
    assert tx.state and tx.nonce and tx.verifier and tx.challenge
    assert "=" not in tx.challenge

    host_id = load_or_create_host_id(tmp_path / "host-id")
    url = build_authorization_url(
        "https://auth.openai.com/api/accounts/authorize",
        redirect_uri="http://127.0.0.1:1455/auth/callback",
        host_id=host_id,
        transaction=tx,
    )
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == [DYNAMIC_CLIENT_ID]
    assert query["agent_name_hint"] == [APP_NAME]
    assert query["ext_agent_host_id"] == [host_id]
    assert query["resource"] == ["https://api.openai.com/v1"]
    assert "chatgpt.tokens.use.direct" in query["scope"][0].split()
    assert query["state"] == [tx.state]
    assert query["nonce"] == [tx.nonce]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [tx.challenge]


def test_host_id_is_stable_and_private(tmp_path):
    path = tmp_path / "host-id"
    first = load_or_create_host_id(path)
    assert first == load_or_create_host_id(path)
    assert first.startswith("urn:uuid:")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_returning_authorization_reuses_client_and_hints():
    tx = new_transaction()
    previous = {
        "email": "owner@example.com",
        "id_token": synthetic("id"),
    }
    url = build_authorization_url(
        "https://auth.openai.com/api/accounts/authorize",
        redirect_uri="http://127.0.0.1:1455/auth/callback",
        host_id="urn:uuid:12345678-1234-4234-8234-123456789abc",
        transaction=tx,
        client_id="oaiapp_existing",
        previous=previous,
    )
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["oaiapp_existing"]
    assert "agent_name_hint" not in query
    assert query["login_hint"] == ["owner@example.com"]


def signed_id_token(*, client_id: str, nonce: str):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(
        private_key.public_key(), as_dict=True
    )
    public_jwk["kid"] = "key-1"
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://auth.openai.com",
            "aud": client_id,
            "sub": "subject-123",
            "email": "owner@example.com",
            "nonce": nonce,
            "iat": now,
            "exp": now + 600,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    return token, {"keys": [public_jwk]}


def test_id_token_validation_checks_signature_audience_and_nonce():
    token, jwks = signed_id_token(client_id="oaiapp_demo", nonce="nonce-1")
    claims = validate_id_token(
        token,
        jwks=jwks,
        issuer="https://auth.openai.com",
        client_id="oaiapp_demo",
        nonce="nonce-1",
    )
    assert claims["sub"] == "subject-123"
    with pytest.raises(ChatGPTOAuthError):
        validate_id_token(
            token,
            jwks=jwks,
            issuer="https://auth.openai.com",
            client_id="oaiapp_demo",
            nonce="wrong",
        )


def test_profile_scope_and_mode_0600(tmp_path):
    id_token, _ = signed_id_token(client_id="oaiapp_demo", nonce="n")
    response = {
        "access_token": synthetic("access"),
        "refresh_token": synthetic("refresh"),
        "id_token": id_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "earliest_refresh_at": 1234567890,
        "scope": (
            "openid profile email offline_access resource.invoke "
            "chatgpt.tokens.use.direct"
        ),
    }
    profile = build_profile(
        response,
        claims={"sub": "subject-123", "email": "owner@example.com"},
        client_id="oaiapp_demo",
        host_id="urn:uuid:12345678-1234-4234-8234-123456789abc",
    )
    path = tmp_path / "chatgpt-plan.json"
    save_profile(path, profile)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["subject"] == "subject-123"
    assert stored["earliest_refresh_at"] == 1234567890

    bad = dict(response)
    bad["scope"] = "openid profile email offline_access"
    with pytest.raises(ChatGPTOAuthError):
        build_profile(
            bad,
            claims={"sub": "subject-123"},
            client_id="oaiapp_demo",
            host_id="urn:uuid:12345678-1234-4234-8234-123456789abc",
        )



class _DisconnectResponse:
    def __init__(self, status=200, body=None):
        self.status = status
        self._body = body or {}

    async def json(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


class _DisconnectSession:
    def __init__(self, post_statuses, calls, **_kwargs):
        self.post_statuses = list(post_statuses)
        self.calls = calls

    def get(self, url):
        self.calls.append(("GET", url, {}))
        return _DisconnectResponse(
            200,
            {
                "issuer": "https://auth.openai.com",
                "authorization_endpoint": "https://auth.openai.com/api/accounts/authorize",
                "token_endpoint": "https://auth.openai.com/api/accounts/oauth/token",
                "jwks_uri": "https://auth.openai.com/.well-known/jwks.json",
                "revocation_endpoint": "https://auth.openai.com/api/accounts/oauth/revoke",
            },
        )

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return _DisconnectResponse(self.post_statuses.pop(0))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_disconnect_revokes_refresh_token_then_removes_local_profile(tmp_path):
    profile_path = tmp_path / "chatgpt-plan.json"
    save_profile(
        profile_path,
        {
            "client_id": "oaiapp_demo",
            "refresh_token": synthetic("refresh"),
        },
    )
    calls = []
    confirmed = await disconnect_profile(
        profile_path=profile_path,
        session_factory=lambda **kwargs: _DisconnectSession([200], calls, **kwargs),
        sleep=lambda _delay: None,
    )
    assert confirmed is True
    assert profile_path.exists() is False
    posts = [call for call in calls if call[0] == "POST"]
    assert len(posts) == 1
    _, url, kwargs = posts[0]
    assert url == "https://auth.openai.com/api/accounts/oauth/revoke"
    assert kwargs["data"]["token_type_hint"] == "refresh_token"
    assert kwargs["data"]["client_id"] == "oaiapp_demo"
    assert "refresh" in kwargs["data"]["token"]


@pytest.mark.asyncio
async def test_disconnect_clears_local_profile_when_remote_revocation_is_unconfirmed(tmp_path):
    profile_path = tmp_path / "chatgpt-plan.json"
    save_profile(
        profile_path,
        {
            "client_id": "oaiapp_demo",
            "refresh_token": synthetic("refresh"),
        },
    )
    calls = []

    async def no_wait(_delay):
        return None

    confirmed = await disconnect_profile(
        profile_path=profile_path,
        session_factory=lambda **kwargs: _DisconnectSession([503, 503, 503], calls, **kwargs),
        sleep=no_wait,
    )
    assert confirmed is False
    assert profile_path.exists() is False
    assert len([call for call in calls if call[0] == "POST"]) == 3
