"""One-time local Sign in with ChatGPT onboarding for the cloud 0liviA Core.

This module intentionally does not run in the normal cloud hot path. It performs
the browser/loopback OAuth flow on a user's local machine, validates the OIDC
identity, and writes a protected profile that can then be transferred to the VM.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
import uuid
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import aiohttp
from aiohttp import web

ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
DYNAMIC_CLIENT_ID = "dynamic_agent_client"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
CALLBACK_PATH = "/auth/callback"
APP_NAME = "0liviA"


class ChatGPTOAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class OAuthTransaction:
    state: str
    nonce: str
    verifier: str
    challenge: str


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def new_transaction() -> OAuthTransaction:
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return OAuthTransaction(
        state=_b64url(secrets.token_bytes(32)),
        nonce=_b64url(secrets.token_bytes(32)),
        verifier=verifier,
        challenge=challenge,
    )


def load_or_create_host_id(path: Path) -> str:
    path = path.expanduser()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value.startswith("urn:uuid:") and len(value) < 80:
            return value
        raise ChatGPTOAuthError("invalid saved ChatGPT host ID")
    path.parent.mkdir(parents=True, exist_ok=True)
    value = f"urn:uuid:{uuid.uuid4()}"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(value + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return value


def _validate_openai_url(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise ChatGPTOAuthError(f"invalid OpenAI discovery field: {field}")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.netloc != "auth.openai.com":
        raise ChatGPTOAuthError(f"unexpected OpenAI discovery origin: {field}")
    return value


async def discover(session: aiohttp.ClientSession) -> dict[str, str]:
    async with session.get(DISCOVERY_URL) as response:
        if response.status != 200:
            raise ChatGPTOAuthError(
                f"OpenAI discovery failed with HTTP {response.status}"
            )
        body = await response.json()
    if not isinstance(body, dict) or body.get("issuer") != ISSUER:
        raise ChatGPTOAuthError("OpenAI issuer could not be verified")
    return {
        "issuer": ISSUER,
        "authorization_endpoint": _validate_openai_url(
            body.get("authorization_endpoint"), field="authorization_endpoint"
        ),
        "token_endpoint": _validate_openai_url(
            body.get("token_endpoint"), field="token_endpoint"
        ),
        "jwks_uri": _validate_openai_url(body.get("jwks_uri"), field="jwks_uri"),
        "revocation_endpoint": _validate_openai_url(
            body.get("revocation_endpoint"), field="revocation_endpoint"
        ),
    }


def build_authorization_url(
    authorization_endpoint: str,
    *,
    redirect_uri: str,
    host_id: str,
    transaction: OAuthTransaction,
    client_id: str = DYNAMIC_CLIENT_ID,
    previous: dict[str, Any] | None = None,
) -> str:
    params: dict[str, str] = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "resource": RESOURCE,
        "state": transaction.state,
        "nonce": transaction.nonce,
        "code_challenge_method": "S256",
        "code_challenge": transaction.challenge,
        "ext_agent_host_id": host_id,
    }
    if client_id == DYNAMIC_CLIENT_ID:
        params["agent_name_hint"] = APP_NAME
    elif previous:
        id_token = previous.get("id_token")
        email = previous.get("email")
        if isinstance(id_token, str) and id_token:
            params["id_token_hint"] = id_token
        if isinstance(email, str) and email:
            params["login_hint"] = email
    return authorization_endpoint + "?" + urlencode(params)


def _select_jwk(jwks: dict[str, Any], kid: str) -> dict[str, Any]:
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise ChatGPTOAuthError("OpenAI JWKS is invalid")
    matches = [key for key in keys if isinstance(key, dict) and key.get("kid") == kid]
    if len(matches) != 1:
        raise ChatGPTOAuthError("OpenAI ID-token signing key is unavailable")
    return matches[0]


def validate_id_token(
    token: str,
    *,
    jwks: dict[str, Any],
    issuer: str,
    client_id: str,
    nonce: str,
) -> dict[str, Any]:
    try:
        import jwt
    except ImportError as exc:  # pragma: no cover - exercised by packaging contract.
        raise ChatGPTOAuthError(
            "PyJWT[crypto] is required for ChatGPT OAuth onboarding"
        ) from exc
    try:
        header = jwt.get_unverified_header(token)
        kid = str(header.get("kid") or "")
        if header.get("alg") != "RS256" or not kid:
            raise ChatGPTOAuthError("unsupported OpenAI ID-token signing header")
        jwk = _select_jwk(jwks, kid)
        key = jwt.PyJWK.from_dict(jwk).key
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
            leeway=5,
            options={"require": ["iss", "aud", "exp", "iat", "sub"]},
        )
    except ChatGPTOAuthError:
        raise
    except Exception as exc:
        raise ChatGPTOAuthError("OpenAI ID token validation failed") from exc
    if payload.get("nonce") != nonce:
        raise ChatGPTOAuthError("OpenAI ID token nonce mismatch")
    azp = payload.get("azp")
    aud = payload.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and azp != client_id:
        raise ChatGPTOAuthError("OpenAI ID token azp mismatch")
    if azp is not None and azp != client_id:
        raise ChatGPTOAuthError("OpenAI ID token azp mismatch")
    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise ChatGPTOAuthError("OpenAI ID token subject is missing")
    return payload


async def fetch_jwks(
    session: aiohttp.ClientSession,
    jwks_uri: str,
) -> dict[str, Any]:
    async with session.get(jwks_uri) as response:
        if response.status != 200:
            raise ChatGPTOAuthError(f"OpenAI JWKS failed with HTTP {response.status}")
        body = await response.json()
    if not isinstance(body, dict):
        raise ChatGPTOAuthError("OpenAI JWKS is invalid")
    return body


async def exchange_code(
    session: aiohttp.ClientSession,
    token_endpoint: str,
    *,
    client_id: str,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with session.post(
        token_endpoint,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "resource": RESOURCE,
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    ) as response:
        body = await response.json(content_type=None)
        if response.status >= 400:
            raise ChatGPTOAuthError(
                f"OpenAI code exchange failed with HTTP {response.status}"
            )
    if not isinstance(body, dict):
        raise ChatGPTOAuthError("OpenAI returned an invalid token response")
    return body


def build_profile(
    token_response: dict[str, Any],
    *,
    claims: dict[str, Any],
    client_id: str,
    host_id: str,
) -> dict[str, Any]:
    access = token_response.get("access_token")
    refresh = token_response.get("refresh_token")
    id_token = token_response.get("id_token")
    scope = token_response.get("scope")
    token_type = str(token_response.get("token_type") or "")
    expires_in = token_response.get("expires_in")
    earliest_refresh_at = token_response.get("earliest_refresh_at")
    granted = set(scope.split()) if isinstance(scope, str) else set()
    required_scopes = {
        "offline_access",
        "resource.invoke",
        "chatgpt.tokens.use.direct",
    }
    if (
        not isinstance(access, str)
        or not access
        or not isinstance(refresh, str)
        or not refresh
        or not isinstance(id_token, str)
        or not id_token
        or not required_scopes.issubset(granted)
        or token_type.casefold() != "bearer"
    ):
        raise ChatGPTOAuthError(
            "ChatGPT plan permission or renewable credentials were not granted"
        )
    try:
        lifetime = int(expires_in)
    except (TypeError, ValueError) as exc:
        raise ChatGPTOAuthError("invalid OpenAI token lifetime") from exc
    if lifetime <= 0:
        raise ChatGPTOAuthError("invalid OpenAI token lifetime")
    try:
        refresh_floor = int(earliest_refresh_at or 0)
    except (TypeError, ValueError) as exc:
        raise ChatGPTOAuthError("invalid OpenAI earliest refresh time") from exc
    if refresh_floor < 0:
        raise ChatGPTOAuthError("invalid OpenAI earliest refresh time")
    email = claims.get("email") if isinstance(claims.get("email"), str) else ""
    return {
        "issuer": ISSUER,
        "subject": claims["sub"],
        "email": email,
        "client_id": client_id,
        "ext_agent_host_id": host_id,
        "id_token": id_token,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_at": int(time.time()) + lifetime,
        "earliest_refresh_at": refresh_floor,
        "scope": scope,
        "scopes": scope.split(),
        "saved_at": int(time.time()),
    }


def save_profile(path: Path, profile: dict[str, Any]) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def load_existing_profile(path: Path) -> dict[str, Any] | None:
    path = path.expanduser()
    if not path.exists():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChatGPTOAuthError("existing ChatGPT profile is invalid") from exc
    if not isinstance(body, dict):
        raise ChatGPTOAuthError("existing ChatGPT profile is invalid")
    return body


@dataclass(frozen=True)
class CallbackResult:
    code: str
    client_id: str


async def start_callback_listener(
    *,
    port: int,
    state: str,
    saved_client_id: str | None,
) -> tuple[asyncio.Future[CallbackResult], web.AppRunner, str]:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[CallbackResult] = loop.create_future()

    async def callback(request: web.Request) -> web.Response:
        if future.done():
            raise web.HTTPNotFound()
        expected_host = f"127.0.0.1:{port}"
        if (
            request.method != "GET"
            or request.path != CALLBACK_PATH
            or request.host != expected_host
        ):
            raise web.HTTPNotFound()
        if len(request.query.getall("state", [])) != 1:
            return web.Response(status=400, text="Estado de inicio de sesión inválido.")
        returned_state = request.query.get("state", "")
        if not secrets.compare_digest(returned_state, state):
            return web.Response(status=400, text="Estado de inicio de sesión inválido.")
        if request.query.get("error"):
            future.set_exception(
                ChatGPTOAuthError("ChatGPT sign-in was declined or cancelled")
            )
            return web.Response(text="Inicio de sesión cancelado. Podés cerrar esta pestaña.")
        if len(request.query.getall("code", [])) != 1 or len(request.query.getall("client_id", [])) > 1:
            future.set_exception(ChatGPTOAuthError("ChatGPT registration is incomplete"))
            return web.Response(status=400, text="Registro incompleto.")
        code = request.query.get("code", "")
        returned_client = request.query.get("client_id")
        client_id = returned_client or saved_client_id or ""
        if (
            not code
            or not client_id
            or client_id == DYNAMIC_CLIENT_ID
            or (
                saved_client_id
                and returned_client is not None
                and returned_client != saved_client_id
            )
        ):
            future.set_exception(ChatGPTOAuthError("ChatGPT registration is incomplete"))
            return web.Response(status=400, text="Registro incompleto.")
        future.set_result(CallbackResult(code=code, client_id=client_id))
        return web.Response(
            text="0liviA ya recibió la autorización. Podés cerrar esta pestaña.",
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    app = web.Application()
    app.router.add_get(CALLBACK_PATH, callback)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    try:
        await site.start()
    except OSError as exc:
        await runner.cleanup()
        raise ChatGPTOAuthError(
            f"callback port {port} is unavailable"
        ) from exc
    return future, runner, f"http://127.0.0.1:{port}{CALLBACK_PATH}"


async def list_models(
    session: aiohttp.ClientSession,
    access_token: str,
) -> list[dict[str, str]]:
    async with session.get(
        RESOURCE + "/models",
        headers={"Authorization": f"Bearer {access_token}"},
    ) as response:
        if response.status >= 400:
            return []
        body = await response.json(content_type=None)
    models = body.get("models") if isinstance(body, dict) else None
    if not isinstance(models, list):
        return []
    result: list[dict[str, str]] = []
    for item in models:
        if not isinstance(item, dict) or item.get("visibility") != "list":
            continue
        slug = item.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        result.append(
            {
                "slug": slug,
                "display_name": str(item.get("display_name") or slug),
            }
        )
    return result


async def disconnect_profile(
    *,
    profile_path: Path,
    session_factory=aiohttp.ClientSession,
    sleep=asyncio.sleep,
) -> bool:
    """Revoke the renewable ChatGPT session, then remove local credentials.

    Returns True when OpenAI confirmed revocation. Local credentials are removed
    even when remote revocation cannot be confirmed, matching the official
    recovery guidance.
    """
    profile_path = profile_path.expanduser()
    profile = load_existing_profile(profile_path)
    if profile is None:
        return True

    refresh_token = profile.get("refresh_token")
    client_id = profile.get("client_id")
    if not isinstance(refresh_token, str) or not refresh_token:
        profile_path.unlink(missing_ok=True)
        return False
    if not isinstance(client_id, str) or not client_id:
        profile_path.unlink(missing_ok=True)
        return False

    confirmed = False
    try:
        try:
            timeout = aiohttp.ClientTimeout(total=20, sock_connect=10, sock_read=15)
            async with session_factory(timeout=timeout) as session:
                oidc = await discover(session)
                endpoint = oidc["revocation_endpoint"]
                for attempt in range(3):
                    try:
                        async with session.post(
                            endpoint,
                            data={
                                "token": refresh_token,
                                "token_type_hint": "refresh_token",
                                "client_id": client_id,
                            },
                            headers={
                                "Accept": "application/json",
                                "Content-Type": "application/x-www-form-urlencoded",
                            },
                        ) as response:
                            if response.status == 200:
                                confirmed = True
                                break
                            if response.status < 500:
                                break
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        pass
                    if attempt < 2:
                        await sleep(0.25 * (2**attempt))
        except (ChatGPTOAuthError, aiohttp.ClientError, asyncio.TimeoutError):
            confirmed = False
    finally:
        profile_path.unlink(missing_ok=True)
    return confirmed


async def authorize_local(
    *,
    profile_path: Path,
    host_id_path: Path,
    port: int = 1455,
    open_browser: bool = True,
    timeout_s: float = 300,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    host_id = load_or_create_host_id(host_id_path)
    previous = load_existing_profile(profile_path)
    saved_client = (
        str(previous.get("client_id"))
        if previous and previous.get("client_id")
        else None
    )
    client_id = saved_client or DYNAMIC_CLIENT_ID
    tx = new_transaction()

    timeout = aiohttp.ClientTimeout(total=30, sock_connect=10, sock_read=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        oidc = await discover(session)
        callback_future, runner, redirect_uri = await start_callback_listener(
            port=port,
            state=tx.state,
            saved_client_id=saved_client,
        )
        try:
            url_previous = previous if open_browser else {
                **(previous or {}),
                "id_token": "",
            }
            auth_url = build_authorization_url(
                oidc["authorization_endpoint"],
                redirect_uri=redirect_uri,
                host_id=host_id,
                transaction=tx,
                client_id=client_id,
                previous=url_previous,
            )
            if open_browser:
                if not webbrowser.open(auth_url, new=1, autoraise=True):
                    raise ChatGPTOAuthError(
                        "No pude abrir el navegador. Reintentá con --no-browser."
                    )
            else:
                print("Abrí esta URL en tu navegador:")
                print(auth_url)

            try:
                result = await asyncio.wait_for(callback_future, timeout=timeout_s)
            except TimeoutError as exc:
                raise ChatGPTOAuthError("ChatGPT sign-in timed out") from exc

            tokens = await exchange_code(
                session,
                oidc["token_endpoint"],
                client_id=result.client_id,
                code=result.code,
                verifier=tx.verifier,
                redirect_uri=redirect_uri,
            )
            id_token = tokens.get("id_token")
            if not isinstance(id_token, str) or not id_token:
                raise ChatGPTOAuthError("OpenAI did not return an ID token")
            jwks = await fetch_jwks(session, oidc["jwks_uri"])
            claims = validate_id_token(
                id_token,
                jwks=jwks,
                issuer=oidc["issuer"],
                client_id=result.client_id,
                nonce=tx.nonce,
            )
            if previous and previous.get("subject") and claims["sub"] != previous["subject"]:
                raise ChatGPTOAuthError(
                    "The returned ChatGPT identity does not match this saved profile"
                )
            profile = build_profile(
                tokens,
                claims=claims,
                client_id=result.client_id,
                host_id=host_id,
            )
            models = await list_models(session, profile["access_token"])
            profile["model_catalog"] = models
            preferred = next(
                (item["slug"] for item in models if item["slug"] == "gpt-6-astra"),
                "",
            )
            if preferred:
                profile["recommended_model"] = preferred
            save_profile(profile_path, profile)
            return profile, models
        finally:
            await runner.cleanup()
