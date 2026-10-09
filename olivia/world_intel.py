"""Bounded, opt-in public event brief for the canonical Core.

Adapted concepts (provenance, bounded fetches, staleness and gaps) from
world-intel-mcp, MIT: https://github.com/marc-shade/world-intel-mcp
No daemon, extra infrastructure, user-supplied URLs or provider credentials.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

import aiohttp

FEEDS = {
    "usgs": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
    "eonet": "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=10",
}
MAX_RESPONSE_BYTES = 512_000
CACHE_SECONDS = 600
MAX_STALE_SECONDS = 3_600


def _plain(value: Any, limit: int = 150) -> str:
    """Treat public feed text as untrusted labels, not prompt instructions."""
    return " ".join(str(value or "").split())[:limit]


def _source_link(url: Any, host: str, fallback: str) -> str:
    """Only publish direct HTTPS citations on the expected official host."""
    try:
        parts = urlsplit(str(url))
        if parts.scheme == "https" and parts.hostname == host and not parts.username and not parts.password:
            return str(url).split("#", 1)[0][:1000]
    except ValueError:
        pass
    return fallback


def format_brief(feeds: dict[str, tuple[dict[str, Any] | None, bool]]) -> str:
    """Deterministic, source-attributed digest without invoking an LLM."""
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"Inteligencia pública · consultado {fetched_at}",
        "Fuentes públicas no autenticadas criptográficamente; datos orientativos, no alertas oficiales.",
    ]
    gaps: list[str] = []
    usgs, usgs_stale = feeds.get("usgs", (None, False))
    lines.append("\nSismos M4.5+ · últimas 24 horas [USGS]")
    if usgs is None or not isinstance(usgs.get("features"), list):
        gaps.append("USGS: sin respuesta verificable")
        lines.append("Sin datos disponibles (no significa ausencia de sismos).")
    else:
        if usgs_stale:
            gaps.append("USGS: caché vencida; confirmar antes de actuar")
            lines.append("ATENCIÓN: datos de caché vencida.")
        features = usgs["features"][:5]
        if not features:
            lines.append("El feed consultado no informó eventos.")
        for entry in features:
            if not isinstance(entry, dict):
                continue
            props = entry.get("properties") or {}
            if not isinstance(props, dict):
                continue
            mag = props.get("mag")
            magnitude = f"M{mag:.1f}" if isinstance(mag, (int, float)) and not isinstance(mag, bool) else "Magnitud no publicada"
            title = _plain(props.get("place"), 110) or "Ubicación no informada"
            link = _source_link(props.get("url"), "earthquake.usgs.gov", FEEDS["usgs"])
            lines.append(f"- {magnitude} · {title} · {link}")
    lines.append("Fuente [USGS]: " + FEEDS["usgs"])

    eonet, eonet_stale = feeds.get("eonet", (None, False))
    lines.append("\nEventos naturales abiertos [NASA EONET]")
    if eonet is None or not isinstance(eonet.get("events"), list):
        gaps.append("NASA EONET: sin respuesta verificable")
        lines.append("Sin datos disponibles (no significa ausencia de eventos).")
    else:
        if eonet_stale:
            gaps.append("NASA EONET: caché vencida; confirmar antes de actuar")
            lines.append("ATENCIÓN: datos de caché vencida.")
        events = eonet["events"][:5]
        if not events:
            lines.append("El feed consultado no informó eventos abiertos.")
        for entry in events:
            if not isinstance(entry, dict):
                continue
            title = _plain(entry.get("title"), 120) or "Evento sin título"
            link = _source_link(entry.get("link"), "eonet.gsfc.nasa.gov", FEEDS["eonet"])
            lines.append(f"- {title} · {link}")
    lines.append("Fuente [NASA EONET]: " + FEEDS["eonet"])
    lines.append("\nCobertura: muestra acotada de eventos mundiales; no incluye monitoreo continuo.")
    if gaps:
        lines.append("Lagunas de datos: " + "; ".join(gaps) + ".")
    return "\n".join(lines)


class WorldIntel:
    """On-demand, fixed-origin feeds; 10-minute cache and marked stale fallback."""

    def __init__(self, session_factory: Callable[..., Any] = aiohttp.ClientSession):
        self._session_factory = session_factory
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def _load(self, key: str) -> dict[str, Any]:
        url = FEEDS[key]  # Never derived from a user query or remote redirect.
        timeout = aiohttp.ClientTimeout(total=10)
        async with self._session_factory(timeout=timeout, trust_env=False) as session:
            async with session.get(
                url,
                allow_redirects=False,
                headers={"Accept": "application/json", "User-Agent": "0liviA-world-intel/0.1"},
            ) as response:
                if response.status != 200:
                    raise ValueError(f"feed_http_{response.status}")
                raw = await response.content.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError("feed_too_large")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("feed_bad_shape")
        return value

    async def _get(self, key: str) -> tuple[dict[str, Any] | None, bool]:
        async with self._lock:
            now = time.monotonic()
            cached = self._cache.get(key)
            if cached and now - cached[0] < CACHE_SECONDS:
                return cached[1], False
            try:
                value = await self._load(key)
                self._cache[key] = (time.monotonic(), value)
                return value, False
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, json.JSONDecodeError, OSError):
                if cached and now - cached[0] <= MAX_STALE_SECONDS:
                    return cached[1], True
                return None, False

    async def brief(self) -> str:
        # Sequential under the one-process lock: predictable low-cost outbound behavior.
        return format_brief({
            "usgs": await self._get("usgs"),
            "eonet": await self._get("eonet"),
        })
