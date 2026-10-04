from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol

import aiohttp

from .config import Settings
from .store import Store


class ProviderError(RuntimeError):
    pass


class AllProvidersFailed(ProviderError):
    pass


class ProviderStreamInterrupted(ProviderError):
    pass


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

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProviderSpec":
        return cls(
            name=str(raw["name"]),
            base_url=str(raw["base_url"]).rstrip("/"),
            model=str(raw["model"]),
            api_key_env=str(raw["api_key_env"]),
            priority=int(raw.get("priority", 100)),
            daily_limit=int(raw.get("daily_limit", 0)),
        )


class OpenAICompatibleProvider:
    def __init__(self, spec: ProviderSpec):
        self.spec = spec
        self.name = spec.name
        self.priority = spec.priority
        self.daily_limit = spec.daily_limit

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        api_key = os.getenv(self.spec.api_key_env)
        if not api_key:
            raise ProviderError(f"{self.name}: missing {self.spec.api_key_env}")

        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=90)
        payload = {
            "model": self.spec.model,
            "messages": messages,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.spec.base_url + "/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status >= 400:
                    body = (await response.text())[:1000]
                    raise ProviderError(f"{self.name}: HTTP {response.status}: {body}")

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


class ProviderPool:
    def __init__(self, providers: list[StreamProvider], store: Store, settings: Settings):
        self.providers = sorted(providers, key=lambda p: p.priority)
        self.store = store
        self.settings = settings

    @classmethod
    def from_settings(cls, settings: Settings, store: Store) -> "ProviderPool":
        providers: list[StreamProvider] = []
        for raw in settings.providers:
            providers.append(OpenAICompatibleProvider(ProviderSpec.from_dict(raw)))
        return cls(providers, store, settings)

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[RouteEvent]:
        errors: list[str] = []
        now = time.time()

        for provider in self.providers:
            state = self.store.provider_state(provider.name)
            if float(state["cooldown_until"]) > now:
                continue
            if provider.daily_limit and int(state["daily_requests"]) >= provider.daily_limit:
                errors.append(f"{provider.name}: daily limit reached")
                continue

            self.store.provider_attempt(provider.name)
            started = time.perf_counter()
            agen = provider.stream(messages)
            try:
                async with asyncio.timeout(self.settings.ttft_timeout_s):
                    first = await anext(agen)
            except StopAsyncIteration:
                first = ""
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failures = int(state["failures"]) + 1
                cooldown = min(
                    self.settings.circuit_base_s * (2 ** max(0, failures - 1)),
                    self.settings.circuit_max_s,
                )
                self.store.provider_failure(provider.name, str(exc), time.time() + cooldown)
                errors.append(f"{provider.name}: {exc}")
                continue

            if not first:
                error = f"{provider.name}: empty stream"
                self.store.provider_failure(
                    provider.name,
                    error,
                    time.time() + self.settings.circuit_base_s,
                )
                errors.append(error)
                continue

            ttft_ms = (time.perf_counter() - started) * 1000
            self.store.provider_success(provider.name, ttft_ms)
            yield RouteEvent(type="route", provider=provider.name)
            yield RouteEvent(type="delta", provider=provider.name, text=first)

            try:
                async for token in agen:
                    yield RouteEvent(type="delta", provider=provider.name, text=token)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise ProviderStreamInterrupted(
                    f"{provider.name}: stream failed after first token: {exc}"
                ) from exc
            return

        detail = "; ".join(errors) if errors else "no configured/available providers"
        raise AllProvidersFailed(detail)
