"""OpenAI-compatible streaming router with per-provider reliability."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Protocol

import aiohttp

from .config import Settings
from .health import FailureKind, ProviderHealth, redact
from .store import Store

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))

ZERO_COST_ALLOWED_MODES = frozenset({"local", "free_hard_cap", "plan_included"})
_PROVIDER_COST_MODES = ZERO_COST_ALLOWED_MODES | frozenset({"free_unverified", "paid"})
_PROVIDER_CAPABILITIES = frozenset({"chat", "code", "review", "research", "vision"})
_FALLBACK_POLICIES = frozenset({"allow", "stop"})
_AUTH_MODES = frozenset({"bearer", "none"})


def is_visible_segment(text: str | None) -> bool:
    if not text:
        return False
    return bool(str(text).translate(_ZERO_WIDTH).strip())


class ProviderError(RuntimeError):
    pass


class AllProvidersFailed(ProviderError):
    pass


class ProviderStreamInterrupted(ProviderError):
    pass


class ProviderConfigError(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    pass


class ProviderHTTPError(ProviderError):
    def __init__(
        self,
        provider: str,
        status: int,
        detail: str = "",
        retry_after_s: float | None = None,
    ):
        self.provider = provider
        self.status = int(status)
        self.detail = redact(detail, max_len=300)
        self.retry_after_s = retry_after_s
        suffix = f": {self.detail}" if self.detail else ""
        super().__init__(f"{provider}: HTTP {self.status}{suffix}")


class _AttemptFailed(Exception):
    def __init__(self, kind: Any, detail: str, retry_after_s: float | None = None):
        self.kind = kind.value if isinstance(kind, FailureKind) else str(kind)
        self.detail = redact(detail, max_len=300)
        self.retry_after_s = retry_after_s
        super().__init__(self.detail)


def _parse_retry_after(raw: Any) -> float | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when is None or when.tzinfo is None:
        return None
    return max(0.0, when.timestamp() - time.time())


@dataclass(frozen=True)
class RouteEvent:
    type: str
    provider: str | None = None
    text: str | None = None
    detail: str | None = None


class StreamProvider(Protocol):
    name: str
    priority: int
    daily_limit: int

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        ...


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    base_url: str
    model: str
    api_key_env: str
    priority: int = 100
    daily_limit: int = 0
    cost_mode: str = "free_unverified"
    kind: str = "openai_compatible"
    profile_path: str = ""
    no_credit_overage_verified: bool = False
    capabilities: tuple[str, ...] = ("chat",)
    fallback_policy: str = "allow"
    auth_mode: str = "bearer"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProviderSpec":
        kind = str(raw.get("kind", "openai_compatible")).strip().lower()
        if kind not in {"openai_compatible", "chatgpt_plan"}:
            raise ProviderConfigError(
                f"invalid provider kind for {raw.get('name', 'provider')}: {kind}"
            )
        cost_mode = str(raw.get("cost_mode", "free_unverified")).strip().lower()
        if cost_mode not in _PROVIDER_COST_MODES:
            raise ProviderConfigError(
                f"invalid cost_mode for {raw.get('name', 'provider')}: {cost_mode}"
            )
        if cost_mode == "plan_included" and kind != "chatgpt_plan":
            raise ProviderConfigError(
                "plan_included is reserved for kind=chatgpt_plan"
            )
        default_base = "https://api.openai.com/v1" if kind == "chatgpt_plan" else ""
        default_model = "gpt-6-astra" if kind == "chatgpt_plan" else ""
        base_url = str(raw.get("base_url", default_base)).rstrip("/")
        model = str(raw.get("model", default_model)).strip()
        if not base_url:
            raise ProviderConfigError(f"{raw.get('name', 'provider')}: base_url is required")
        if not model:
            raise ProviderConfigError(f"{raw.get('name', 'provider')}: model is required")
        if kind == "chatgpt_plan" and base_url != "https://api.openai.com/v1":
            raise ProviderConfigError(
                "chatgpt_plan provider must use https://api.openai.com/v1"
            )
        raw_capabilities = raw.get("capabilities", ("chat",))
        if isinstance(raw_capabilities, str):
            parts = [part.strip().lower() for part in raw_capabilities.split(",")]
        elif isinstance(raw_capabilities, (list, tuple, set)):
            parts = [str(part).strip().lower() for part in raw_capabilities]
        else:
            raise ProviderConfigError(
                f"invalid capabilities for {raw.get('name', 'provider')}"
            )
        capabilities = tuple(dict.fromkeys(part for part in parts if part))
        if not capabilities:
            capabilities = ("chat",)
        unknown = sorted(set(capabilities) - _PROVIDER_CAPABILITIES)
        if unknown:
            raise ProviderConfigError(
                f"invalid capabilities for {raw.get('name', 'provider')}: "
                + ",".join(unknown)
            )
        fallback_policy = str(raw.get("fallback_policy", "allow")).strip().lower()
        if fallback_policy not in _FALLBACK_POLICIES:
            raise ProviderConfigError(
                f"invalid fallback_policy for {raw.get('name', 'provider')}: "
                f"{fallback_policy}"
            )
        auth_mode = str(raw.get("auth_mode", "bearer")).strip().lower()
        if auth_mode not in _AUTH_MODES:
            raise ProviderConfigError(
                f"invalid auth_mode for {raw.get('name', 'provider')}: {auth_mode}"
            )
        if kind == "chatgpt_plan" and auth_mode != "bearer":
            raise ProviderConfigError("chatgpt_plan manages its own authenticated transport")
        if auth_mode == "none" and cost_mode not in {"local", "free_hard_cap"}:
            raise ProviderConfigError(
                "auth_mode=none requires cost_mode=local or free_hard_cap"
            )
        return cls(
            name=str(raw["name"]),
            base_url=base_url,
            model=model,
            api_key_env=str(raw.get("api_key_env", "")),
            priority=int(raw.get("priority", 100)),
            daily_limit=int(raw.get("daily_limit", 0)),
            cost_mode=cost_mode,
            kind=kind,
            profile_path=str(raw.get("profile_path", "")),
            no_credit_overage_verified=bool(
                raw.get("no_credit_overage_verified", False)
            ),
            capabilities=capabilities,
            fallback_policy=fallback_policy,
            auth_mode=auth_mode,
        )


class OpenAICompatibleProvider:
    def __init__(self, spec: ProviderSpec):
        self.spec = spec
        self.name = spec.name
        self.priority = spec.priority
        self.daily_limit = spec.daily_limit
        self.cost_mode = spec.cost_mode
        self.capabilities = spec.capabilities
        self.fallback_policy = spec.fallback_policy

    @property
    def configured(self) -> bool:
        if self.cost_mode == "local" or self.spec.auth_mode == "none":
            return True
        return bool(self.spec.api_key_env and os.getenv(self.spec.api_key_env))

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        api_key = os.getenv(self.spec.api_key_env) if self.spec.api_key_env else ""
        if (
            self.spec.auth_mode != "none"
            and self.spec.cost_mode != "local"
            and not api_key
        ):
            raise ProviderConfigError(f"{self.name}: missing {self.spec.api_key_env}")

        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=90)
        payload = {"model": self.spec.model, "messages": messages, "stream": True}
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.spec.base_url + "/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status >= 400:
                        retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                        body = (await response.text())[:1000]
                        raise ProviderHTTPError(
                            self.name,
                            response.status,
                            body,
                            retry_after,
                        )

                    async for raw in response.content:
                        line = raw.decode("utf-8", "ignore").strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            obj = json.loads(data)
                            token = obj["choices"][0]["delta"].get("content")
                        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                            continue
                        if token:
                            yield str(token)
        except asyncio.CancelledError:
            raise
        except ProviderError:
            raise
        except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as exc:
            raise ProviderTimeout(f"{self.name}: {type(exc).__name__}") from exc
        except aiohttp.ClientError as exc:
            raise ProviderError(
                f"{self.name}: network {type(exc).__name__}: {redact(str(exc), max_len=160)}"
            ) from exc


class ChatGPTPlanProvider:
    """Official Sign in with ChatGPT plan route.

    Credentials live in a protected server-side profile file. This transport uses
    only the public Responses API and never accepts an OpenAI API key.
    """

    PLAN_SCOPE = "chatgpt.tokens.use.direct"
    TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
    RESOURCE = "https://api.openai.com/v1"

    def __init__(
        self,
        spec: ProviderSpec,
        *,
        session_factory=aiohttp.ClientSession,
        clock: Callable[[], float] | None = None,
    ):
        if spec.kind != "chatgpt_plan":
            raise ProviderConfigError("ChatGPTPlanProvider requires kind=chatgpt_plan")
        if spec.cost_mode != "plan_included":
            raise ProviderConfigError(
                "chatgpt_plan requires cost_mode=plan_included"
            )
        if not spec.no_credit_overage_verified:
            raise ProviderConfigError(
                "chatgpt_plan requires no_credit_overage_verified=true"
            )
        if not spec.profile_path:
            raise ProviderConfigError("chatgpt_plan requires profile_path")
        self.spec = spec
        self.name = spec.name
        self.model = spec.model
        self.priority = spec.priority
        self.daily_limit = spec.daily_limit
        self.cost_mode = spec.cost_mode
        self.capabilities = spec.capabilities
        self.fallback_policy = spec.fallback_policy
        self.profile_path = Path(spec.profile_path).expanduser()
        self._session_factory = session_factory
        self._clock = clock or time.time
        self._profile_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        try:
            self._load_profile()
        except (ProviderConfigError, OSError):
            return False
        return True

    @staticmethod
    def _scope_set(value: Any) -> set[str]:
        if isinstance(value, str):
            return {part for part in value.split() if part}
        if isinstance(value, list):
            return {str(part) for part in value if str(part)}
        return set()

    def _validate_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        required = ("client_id", "access_token", "refresh_token", "expires_at")
        missing = [key for key in required if not profile.get(key)]
        if missing:
            raise ProviderConfigError(
                f"{self.name}: incomplete ChatGPT profile ({','.join(missing)})"
            )
        scopes = self._scope_set(profile.get("scope"))
        required = {self.PLAN_SCOPE, "resource.invoke", "offline_access"}
        if not required.issubset(scopes):
            raise ProviderConfigError(
                f"{self.name}: required ChatGPT plan scopes not granted"
            )
        return profile

    def _load_profile(self) -> dict[str, Any]:
        try:
            mode = self.profile_path.stat().st_mode & 0o777
        except FileNotFoundError as exc:
            raise ProviderConfigError(
                f"{self.name}: ChatGPT plan profile not found"
            ) from exc
        if mode & 0o077:
            raise ProviderConfigError(
                f"{self.name}: ChatGPT plan profile must be mode 0600"
            )
        try:
            profile = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderConfigError(
                f"{self.name}: invalid ChatGPT plan profile"
            ) from exc
        if not isinstance(profile, dict):
            raise ProviderConfigError(
                f"{self.name}: invalid ChatGPT plan profile"
            )
        return self._validate_profile(profile)

    def _save_profile(self, profile: dict[str, Any]) -> None:
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.profile_path.with_name(self.profile_path.name + ".tmp")
        tmp.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.profile_path)

    async def _access_token(self) -> str:
        async with self._profile_lock:
            profile = self._load_profile()
            try:
                expires_at = float(profile["expires_at"])
            except (TypeError, ValueError) as exc:
                raise ProviderConfigError(
                    f"{self.name}: invalid ChatGPT token expiry"
                ) from exc
            now = self._clock()
            if expires_at > now + 120:
                return str(profile["access_token"])
            try:
                earliest_refresh_at = float(profile.get("earliest_refresh_at") or 0)
            except (TypeError, ValueError) as exc:
                raise ProviderConfigError(
                    f"{self.name}: invalid ChatGPT earliest refresh time"
                ) from exc
            if earliest_refresh_at > now:
                if expires_at > now:
                    return str(profile["access_token"])
                raise ProviderConfigError(
                    f"{self.name}: ChatGPT token expired before refresh became eligible"
                )

            timeout = aiohttp.ClientTimeout(total=20, sock_connect=10, sock_read=15)
            async with self._session_factory(timeout=timeout) as session:
                async with session.post(
                    self.TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": str(profile["client_id"]),
                        "refresh_token": str(profile["refresh_token"]),
                        "resource": self.RESOURCE,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    if response.status >= 400:
                        body = (await response.text())[:1000]
                        raise ProviderHTTPError(
                            self.name,
                            response.status,
                            body,
                            _parse_retry_after(response.headers.get("Retry-After")),
                        )
                    body = await response.json()

            if not isinstance(body, dict) or not body.get("access_token"):
                raise ProviderConfigError(
                    f"{self.name}: invalid ChatGPT token refresh response"
                )
            updated = dict(profile)
            updated["access_token"] = str(body["access_token"])
            if body.get("refresh_token"):
                updated["refresh_token"] = str(body["refresh_token"])
            if body.get("scope"):
                updated["scope"] = body["scope"]
            try:
                expires_in = max(60, int(body.get("expires_in", 3600)))
            except (TypeError, ValueError):
                expires_in = 3600
            updated["expires_at"] = int(self._clock()) + expires_in
            if body.get("earliest_refresh_at") is not None:
                try:
                    refresh_floor = int(body["earliest_refresh_at"])
                except (TypeError, ValueError) as exc:
                    raise ProviderConfigError(
                        f"{self.name}: invalid ChatGPT earliest refresh time"
                    ) from exc
                if refresh_floor < 0:
                    raise ProviderConfigError(
                        f"{self.name}: invalid ChatGPT earliest refresh time"
                    )
                updated["earliest_refresh_at"] = refresh_floor
            else:
                updated.pop("earliest_refresh_at", None)
            self._validate_profile(updated)
            self._save_profile(updated)
            return str(updated["access_token"])

    @staticmethod
    def _responses_payload(
        model: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        instructions = "\n\n".join(
            str(item.get("content", "")).strip()
            for item in messages
            if item.get("role") in {"system", "developer"}
            and str(item.get("content", "")).strip()
        )
        input_items = [
            {
                "role": str(item.get("role")),
                "content": str(item.get("content", "")),
            }
            for item in messages
            if item.get("role") in {"user", "assistant"}
            and str(item.get("content", "")).strip()
        ]
        payload: dict[str, Any] = {
            "model": model,
            "input": input_items,
            "store": False,
            "stream": True,
        }
        if instructions:
            payload["instructions"] = instructions
        return payload

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        token = await self._access_token()
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=120)
        payload = self._responses_payload(self.model, messages)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        completed = False
        try:
            async with self._session_factory(timeout=timeout) as session:
                async with session.post(
                    self.spec.base_url + "/responses",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status >= 400:
                        body = (await response.text())[:1000]
                        raise ProviderHTTPError(
                            self.name,
                            response.status,
                            body,
                            _parse_retry_after(response.headers.get("Retry-After")),
                        )
                    async for raw in response.content:
                        for line_bytes in raw.splitlines():
                            line = line_bytes.decode("utf-8", "ignore").strip()
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if not data or data == "[DONE]":
                                continue
                            try:
                                event = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            event_type = str(event.get("type") or "")
                            if event_type == "response.output_text.delta":
                                delta = event.get("delta")
                                if delta:
                                    yield str(delta)
                                continue
                            if event_type == "response.completed":
                                completed = True
                                continue
                            if event_type == "response.failed":
                                error = (event.get("response") or {}).get("error") or {}
                                code = str(error.get("code") or "response_failed")
                                if code == "subscription_sharing_usage_limit_exceeded":
                                    raise ProviderHTTPError(self.name, 429, code)
                                if code == "subscription_sharing_usage_unavailable":
                                    raise ProviderHTTPError(self.name, 503, code)
                                if code == "subscription_sharing_user_not_eligible":
                                    raise ProviderHTTPError(self.name, 403, code)
                                raise ProviderError(f"{self.name}: {code}")
                            if event_type in {"response.incomplete", "error"}:
                                raise ProviderError(
                                    f"{self.name}: {event_type}"
                                )
        except asyncio.CancelledError:
            raise
        except ProviderError:
            raise
        except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as exc:
            raise ProviderTimeout(f"{self.name}: {type(exc).__name__}") from exc
        except aiohttp.ClientError as exc:
            raise ProviderError(
                f"{self.name}: network {type(exc).__name__}: "
                f"{redact(str(exc), max_len=160)}"
            ) from exc
        if not completed:
            raise ProviderError(
                f"{self.name}: stream ended without response.completed"
            )


class ProviderPool:
    def __init__(
        self,
        providers: list[StreamProvider],
        store: Store,
        settings: Settings,
        *,
        health: ProviderHealth | None = None,
        clock: Callable[[], float] | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.settings = settings
        self.store = store
        self._clock = clock or time.time
        self._health = health or ProviderHealth.from_store(
            store,
            settings,
            now=self._clock,
        )
        self._sink = event_sink
        self.telemetry: deque[dict[str, Any]] = deque(maxlen=400)
        self.duplicates: list[str] = []
        self._turns = 0
        self.zero_cost_blocked: list[dict[str, str]] = []

        ordered: list[StreamProvider] = []
        seen: set[str] = set()
        for provider in sorted(providers, key=lambda p: (p.priority, p.name)):
            if provider.name in seen:
                self.duplicates.append(provider.name)
                continue
            seen.add(provider.name)
            ordered.append(provider)
        self.providers = ordered
        if self.duplicates:
            self.emit(
                "pool.duplicates_dropped",
                detail=",".join(sorted(set(self.duplicates))),
            )

    @classmethod
    def from_settings(cls, settings: Settings, store: Store) -> "ProviderPool":
        providers: list[StreamProvider] = []
        blocked: list[dict[str, str]] = []
        for raw in settings.providers:
            spec = ProviderSpec.from_dict(raw)
            cost_blocked = (
                settings.hard_zero_cost
                and (
                    spec.cost_mode not in ZERO_COST_ALLOWED_MODES
                    or (
                        spec.kind == "chatgpt_plan"
                        and not spec.no_credit_overage_verified
                    )
                )
            )
            if cost_blocked:
                blocked.append({"provider": spec.name, "cost_mode": spec.cost_mode})
                continue
            if spec.kind == "chatgpt_plan":
                providers.append(ChatGPTPlanProvider(spec))
            else:
                providers.append(OpenAICompatibleProvider(spec))
        pool = cls(providers, store, settings)
        pool.zero_cost_blocked = blocked
        for item in blocked:
            pool.emit(
                "cost.blocked",
                provider=item["provider"],
                cost_mode=item["cost_mode"],
                detail="provider disabled by hard-zero-cost policy",
            )
        return pool

    @property
    def health(self) -> ProviderHealth:
        return self._health

    @staticmethod
    def _safe(value: Any) -> Any:
        if isinstance(value, str):
            return redact(value, max_len=200)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [ProviderPool._safe(v) for v in value]
        return redact(repr(value), max_len=200)

    def emit(
        self,
        event_kind: str,
        *,
        provider: str | None = None,
        detail: Any = None,
        turn: str | None = None,
        session_id: str | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "ts": round(self._clock(), 3),
            "kind": event_kind,
        }
        if provider:
            record["provider"] = provider
        if turn:
            record["turn"] = turn
        if detail is not None:
            record["detail"] = redact(detail, max_len=200)
        for key, value in fields.items():
            if value is not None:
                record[key] = self._safe(value)

        self.telemetry.append(record)
        if self._sink is not None:
            with contextlib.suppress(Exception):
                self._sink(dict(record))
        record_event = getattr(self.store, "record_event", None)
        if callable(record_event):
            with contextlib.suppress(Exception):
                payload = {k: v for k, v in record.items() if k != "ts"}
                record_event(
                    f"router.{event_kind}",
                    payload,
                    session_id=session_id,
                )
        return record

    def drain_telemetry(self) -> list[dict[str, Any]]:
        out = list(self.telemetry)
        self.telemetry.clear()
        return out

    def catalog(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for provider in self.providers:
            spec = getattr(provider, "spec", None)
            rows.append({
                "name": provider.name,
                "model": str(getattr(spec, "model", "") or ""),
                "priority": int(getattr(provider, "priority", 100)),
                "daily_limit": int(getattr(provider, "daily_limit", 0)),
                "cost_mode": str(getattr(provider, "cost_mode", "free_unverified")),
                "capabilities": list(
                    getattr(provider, "capabilities", ("chat",))
                ),
                "fallback_policy": str(
                    getattr(provider, "fallback_policy", "allow")
                ),
            })
        return rows

    def providers_for(self, capability: str) -> list[StreamProvider]:
        normalized = str(capability or "chat").strip().lower()
        if normalized not in _PROVIDER_CAPABILITIES:
            raise ProviderConfigError(f"invalid routing capability: {normalized}")
        return [
            provider
            for provider in self.providers
            if normalized in set(getattr(provider, "capabilities", ("chat",)))
        ]

    def metrics(self) -> dict[str, Any]:
        return {
            "turns": self._turns,
            "events": dict(Counter(r["kind"] for r in self.telemetry)),
            "providers": self._health.metrics(),
            "duplicates_dropped": sorted(set(self.duplicates)),
            "hard_zero_cost": bool(self.settings.hard_zero_cost),
            "cost_blocked": list(self.zero_cost_blocked),
        }

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        capability: str = "chat",
    ) -> AsyncIterator[RouteEvent]:
        normalized_capability = str(capability or "chat").strip().lower()
        selected_providers = self.providers_for(normalized_capability)
        turn_id = uuid.uuid4().hex[:8]
        errors: list[str] = []
        attempted: set[str] = set()
        attempts = 0
        max_attempts = max(1, int(self.settings.max_provider_attempts))
        self._turns += 1
        self.emit(
            "turn.start",
            turn=turn_id,
            session_id=session_id,
            providers=[p.name for p in selected_providers],
            capability=normalized_capability,
        )

        for provider in selected_providers:
            strict_fallback = (
                str(getattr(provider, "fallback_policy", "allow")) == "stop"
            )
            if attempts >= max_attempts:
                self.emit(
                    "attempts.capped",
                    turn=turn_id,
                    limit=max_attempts,
                    detail="failover ceiling reached",
                )
                errors.append(f"failover ceiling reached ({max_attempts})")
                break

            if provider.name in attempted:
                self.emit(
                    "attempt.duplicate_skipped",
                    provider=provider.name,
                    turn=turn_id,
                )
                continue

            admission = self._health.admit(
                provider.name,
                daily_limit=provider.daily_limit,
            )
            if not admission.allowed:
                if admission.reason == "quota_exhausted":
                    errors.append(f"{provider.name}: daily quota exhausted")
                    self.emit(
                        "quota.exhausted",
                        provider=provider.name,
                        turn=turn_id,
                        state=admission.state,
                        daily_requests=admission.daily_requests,
                        daily_limit=admission.daily_limit,
                    )
                else:
                    errors.append(
                        f"{provider.name}: {admission.reason} "
                        f"({admission.cooldown_remaining_s:.1f}s)"
                    )
                    self.emit(
                        "breaker.skip",
                        provider=provider.name,
                        turn=turn_id,
                        state=admission.state,
                        reason=admission.reason,
                        cooldown_s=round(admission.cooldown_remaining_s, 1),
                    )
                if strict_fallback:
                    self.emit(
                        "fallback.blocked",
                        provider=provider.name,
                        turn=turn_id,
                        reason=admission.reason,
                        detail="provider policy forbids fallback to another model",
                    )
                    break
                continue

            attempted.add(provider.name)
            attempts += 1
            self.emit(
                "attempt",
                provider=provider.name,
                turn=turn_id,
                state=admission.state,
                probe=admission.is_probe,
                attempt_no=attempts,
            )

            box: dict[str, Any] = {"visible": False, "ttft_ms": None}
            started = time.perf_counter()
            chunks = 0
            first_segment = False
            try:
                async for event in self._attempt(provider, messages, box):
                    if event.type == "route" and not first_segment:
                        first_segment = True
                        ttft_ms = float(box.get("ttft_ms") or 0.0)
                        snapshot = self._health.record_success(
                            provider.name,
                            ttft_ms=ttft_ms,
                        )
                        self.emit(
                            "first_segment",
                            provider=provider.name,
                            turn=turn_id,
                            state=snapshot["state"],
                            ttft_ms=round(ttft_ms, 1),
                        )
                        self.emit(
                            "ttft",
                            provider=provider.name,
                            turn=turn_id,
                            ttft_ms=round(ttft_ms, 1),
                            budget_s=self.settings.ttft_timeout_s,
                        )
                    if event.type == "delta" and event.text:
                        chunks += 1
                    yield event
            except asyncio.CancelledError:
                self.emit(
                    "cancelled",
                    provider=provider.name,
                    turn=turn_id,
                    visible=bool(box["visible"]),
                    chunks=chunks,
                )
                raise
            except _AttemptFailed as exc:
                failure_kind = (
                    FailureKind.INTERRUPTED.value
                    if box["visible"]
                    else exc.kind
                )
                snapshot = self._health.record_failure(
                    provider.name,
                    failure_kind,
                    detail=exc.detail,
                    retry_after_s=exc.retry_after_s,
                )
                self.emit(
                    "failure",
                    provider=provider.name,
                    turn=turn_id,
                    failure_kind=failure_kind,
                    detail=exc.detail,
                    state=snapshot["state"],
                    cooldown_s=round(snapshot["cooldown_s"], 1),
                    visible=bool(box["visible"]),
                    chunks=chunks if box["visible"] else None,
                )
                if box["visible"]:
                    raise ProviderStreamInterrupted(
                        f"{provider.name}: stream failed after first visible segment: "
                        f"{redact(exc.detail, max_len=120)}"
                    ) from exc
                errors.append(
                    f"{provider.name}/{exc.kind}: "
                    f"{redact(exc.detail, max_len=120)}"
                )
                if strict_fallback:
                    self.emit(
                        "fallback.blocked",
                        provider=provider.name,
                        turn=turn_id,
                        reason=exc.kind,
                        detail="provider policy forbids fallback to another model",
                    )
                    break
                continue
            finally:
                self._health.release(provider.name)

            total_ms = (time.perf_counter() - started) * 1000
            self.emit(
                "success",
                provider=provider.name,
                turn=turn_id,
                chunks=chunks,
                ms=round(total_ms, 1),
                state="closed",
            )
            return

        detail = (
            "; ".join(errors)
            if errors
            else f"no configured/available providers for capability {normalized_capability}"
        )
        self.emit(
            "turn.failed",
            turn=turn_id,
            detail=detail,
            attempts=attempts,
        )
        raise AllProvidersFailed(redact(detail, max_len=600))

    async def _attempt(
        self,
        provider: StreamProvider,
        messages: list[dict[str, str]],
        box: dict[str, Any],
    ) -> AsyncIterator[RouteEvent]:
        agen = provider.stream(messages)
        started = time.perf_counter()
        budget = float(self.settings.ttft_timeout_s)
        prefix_max = int(self.settings.visible_prefix_max_chars)
        idle = float(self.settings.stream_idle_timeout_s or 0.0)
        try:
            buffered_chunks: list[str] = []
            buffered_chars = 0
            try:
                async with asyncio.timeout(budget):
                    while True:
                        try:
                            token = await anext(agen)
                        except StopAsyncIteration:
                            raise _AttemptFailed(
                                FailureKind.EMPTY_STREAM,
                                f"{provider.name}: stream ended without a visible segment",
                            ) from None
                        if not token:
                            continue
                        buffered_chunks.append(token)
                        buffered_chars += len(token)
                        if is_visible_segment(token):
                            break
                        if buffered_chars > prefix_max:
                            raise _AttemptFailed(
                                FailureKind.EMPTY_STREAM,
                                f"{provider.name}: no visible segment within "
                                f"{prefix_max} chars",
                            )
            except TimeoutError as exc:
                raise _AttemptFailed(
                    FailureKind.TIMEOUT,
                    f"{provider.name}: no first visible segment within {budget}s",
                ) from exc

            box["visible"] = True
            box["ttft_ms"] = (time.perf_counter() - started) * 1000
            yield RouteEvent(type="route", provider=provider.name)
            for chunk in buffered_chunks:
                yield RouteEvent(
                    type="delta",
                    provider=provider.name,
                    text=chunk,
                )

            while True:
                try:
                    if idle:
                        async with asyncio.timeout(idle):
                            token = await anext(agen)
                    else:
                        token = await anext(agen)
                except StopAsyncIteration:
                    return
                except TimeoutError as exc:
                    raise _AttemptFailed(
                        FailureKind.INTERRUPTED,
                        f"{provider.name}: stream idle > {idle}s",
                    ) from exc
                if token:
                    yield RouteEvent(
                        type="delta",
                        provider=provider.name,
                        text=token,
                    )
        except asyncio.CancelledError:
            raise
        except _AttemptFailed:
            raise
        except Exception as exc:
            failure_kind, detail, retry_after = _classify(exc)
            raise _AttemptFailed(
                failure_kind,
                detail,
                retry_after,
            ) from exc
        finally:
            await _shutdown(agen)


def _classify(exc: BaseException) -> tuple[str, str, float | None]:
    if isinstance(exc, ProviderHTTPError):
        kind = (
            FailureKind.RATE_LIMIT
            if exc.status == 429
            else FailureKind.HTTP
        )
        return kind.value, str(exc), exc.retry_after_s
    if isinstance(exc, (ProviderTimeout, asyncio.TimeoutError)):
        return FailureKind.TIMEOUT.value, str(exc) or type(exc).__name__, None
    if isinstance(exc, ProviderConfigError):
        return FailureKind.CONFIG.value, str(exc), None
    if isinstance(exc, (aiohttp.ClientError, OSError)):
        return (
            FailureKind.NETWORK.value,
            f"{type(exc).__name__}: {redact(str(exc), max_len=120)}",
            None,
        )
    if isinstance(exc, ProviderError):
        return FailureKind.HTTP.value, str(exc), None
    return (
        FailureKind.UNKNOWN.value,
        f"{type(exc).__name__}: {redact(str(exc), max_len=120)}",
        None,
    )


async def _shutdown(agen: AsyncIterator[str]) -> None:
    aclose = getattr(agen, "aclose", None)
    if aclose is None:
        return
    with contextlib.suppress(BaseException):
        await aclose()
