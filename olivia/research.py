from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import aiohttp


MAX_QUERY_CHARS = 1024
MAX_RESULTS = 10
MAX_RESPONSE_BYTES = 256 * 1024
_BYOK_ALIAS = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SearchUnavailable(RuntimeError):
    pass


class WebSearch(Protocol):
    @property
    def configured(self) -> bool: ...

    async def search(self, query: str, *, limit: int = 5) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SearchItem:
    url: str
    title: str
    description: str = ""


class CloudflareWebSearch:
    """Fail-closed adapter for Cloudflare's Web Search API.

    It is eligible only when the owner has explicitly verified that the
    configured BYOK provider route cannot incur paid usage.
    """

    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        gateway_id: str = "default",
        provider: str = "exa",
        byok_alias: str,
        zero_cost_verified: bool,
        session_factory: Callable[..., Any] = aiohttp.ClientSession,
    ):
        provider = provider.strip().lower()
        if provider not in {"ceramic", "exa", "linkup"}:
            raise ValueError("unsupported web search provider")
        if not account_id.strip() or not api_token.strip():
            raise ValueError("Cloudflare account/token are required")
        alias = byok_alias.strip()
        if not alias:
            raise ValueError("BYOK alias is required to prevent implicit AI Gateway credits")
        if not _BYOK_ALIAS.fullmatch(alias):
            raise ValueError("BYOK alias must match ^[A-Za-z0-9_-]{1,64}$")
        self.account_id = account_id.strip()
        self.api_token = api_token.strip()
        self.gateway_id = gateway_id.strip() or "default"
        self.provider = provider
        self.byok_alias = alias
        self.zero_cost_verified = bool(zero_cost_verified)
        self._session_factory = session_factory

    @property
    def configured(self) -> bool:
        return self.zero_cost_verified

    async def search(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        query = str(query or "").strip()
        if not self.zero_cost_verified:
            raise SearchUnavailable("web_search_zero_cost_unverified")
        if not query or len(query) > MAX_QUERY_CHARS:
            raise ValueError("query must be 1..1024 characters")
        limit = max(1, min(int(limit), MAX_RESULTS))

        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/websearch/"
        )
        payload = {
            "query": query,
            "provider": self.provider,
            "limit": limit,
            "byokAlias": self.byok_alias,
            "options": {"gateway": {"id": self.gateway_id}},
        }
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "0liviA-research/0.1",
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with self._session_factory(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                body = await response.read()
                if len(body) > MAX_RESPONSE_BYTES:
                    raise SearchUnavailable("web_search_response_too_large")
                if response.status != 200:
                    raise SearchUnavailable(f"web_search_http_{response.status}")

        try:
            raw = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SearchUnavailable("web_search_invalid_json") from exc

        items: list[dict[str, str]] = []
        for item in raw.get("items") or []:
            if not isinstance(item, dict):
                continue
            url_value = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url_value or not title:
                continue
            items.append({
                "url": url_value[:2048],
                "title": title[:500],
                "description": str(item.get("description") or "").strip()[:2000],
            })
            if len(items) >= limit:
                break

        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        return {
            "items": items,
            "metadata": {
                "query": str(metadata.get("query") or query)[:MAX_QUERY_CHARS],
                "requestId": str(metadata.get("requestId") or "")[:200],
                "latencyMs": metadata.get("latencyMs"),
                "provider": self.provider,
            },
        }


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def web_search_from_env() -> CloudflareWebSearch | None:
    if not _env_bool("OLIVIA_WEB_SEARCH_ENABLED", False):
        return None
    verified = _env_bool("OLIVIA_WEB_SEARCH_ZERO_COST_VERIFIED", False)
    if not verified:
        raise SearchUnavailable("web_search_zero_cost_unverified")

    return CloudflareWebSearch(
        account_id=os.getenv("OLIVIA_CF_ACCOUNT_ID", ""),
        api_token=os.getenv("OLIVIA_CF_API_TOKEN", ""),
        gateway_id=os.getenv("OLIVIA_CF_AI_GATEWAY_ID", "default"),
        provider=os.getenv("OLIVIA_CF_WEB_SEARCH_PROVIDER", "exa"),
        byok_alias=os.getenv("OLIVIA_CF_WEB_SEARCH_BYOK_ALIAS", ""),
        zero_cost_verified=verified,
    )
