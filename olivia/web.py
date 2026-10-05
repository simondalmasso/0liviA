from __future__ import annotations

import asyncio
import html
import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

import aiohttp
from aiohttp.abc import AbstractResolver


MAX_REDIRECTS = 3
MAX_BODY_BYTES = 256 * 1024
MAX_TEXT_CHARS = 12_000
ALLOWED_PORTS = {80, 443}
ALLOWED_TYPES = (
    "text/html",
    "text/plain",
    "application/json",
    "application/xml",
    "text/xml",
)

SENSITIVE_QUERY_KEYS = frozenset({
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "code",
    "credential",
    "key",
    "password",
    "secret",
    "session",
    "sessionid",
    "sig",
    "signature",
    "token",
})


def has_sensitive_query_parameters(value: str) -> bool:
    try:
        query = urlsplit(str(value or "")).query
    except ValueError:
        return False
    keys = {
        key.strip().lower()
        for key, _ in parse_qsl(query, keep_blank_values=True)
    }
    return bool(keys & SENSITIVE_QUERY_KEYS)


class WebReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebDocument:
    url: str
    title: str
    text: str
    content_type: str
    status: int


def _public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def validate_public_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2048:
        raise WebReadError("invalid_url")
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise WebReadError("invalid_url") from exc
    if parts.scheme.lower() not in {"http", "https"}:
        raise WebReadError("scheme_not_allowed")
    if not parts.hostname or parts.username is not None or parts.password is not None:
        raise WebReadError("invalid_authority")
    try:
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise WebReadError("invalid_port") from exc
    if port not in ALLOWED_PORTS:
        raise WebReadError("port_not_allowed")
    host = parts.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise WebReadError("private_host")
    if _looks_like_ip(host) and not _public_ip(host):
        raise WebReadError("private_host")
    netloc = host
    if parts.port:
        netloc = f"[{host}]:{parts.port}" if ":" in host else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


def _looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


class PublicResolver(AbstractResolver):
    """Resolver that refuses any DNS answer that is not globally routable."""

    def __init__(self, inner: AbstractResolver | None = None):
        self.inner = inner or aiohttp.resolver.DefaultResolver()

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC):
        records = await self.inner.resolve(host, port, family)
        if not records:
            raise OSError("dns_empty")
        verified = []
        for record in records:
            address = str(record.get("host") or "")
            if not _public_ip(address):
                raise OSError("dns_private_address")
            verified.append(record)
        return verified

    async def close(self) -> None:
        await self.inner.close()


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "canvas", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag in self.SKIP:
            self._skip_depth += 1
        if tag == "title" and self._skip_depth == 0:
            self._in_title = True
        if tag in {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3", "h4", "tr"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "tr"}:
            self._parts.append("\n")

    def handle_data(self, data: str):
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text[:300]
        self._parts.append(text + " ")

    def text(self) -> str:
        joined = "".join(self._parts)
        joined = re.sub(r"[ \t\f\v]+", " ", joined)
        joined = re.sub(r"\n\s*\n+", "\n\n", joined)
        return joined.strip()


def extract_text(body: bytes, content_type: str) -> tuple[str, str]:
    decoded = body.decode("utf-8", errors="replace")
    if content_type.startswith("text/html"):
        parser = _TextExtractor()
        parser.feed(decoded)
        text = parser.text()
        title = html.unescape(parser.title).strip()
    else:
        text = decoded.strip()
        title = ""
    return title[:300], text[:MAX_TEXT_CHARS]


class SafeWebReader:
    def __init__(
        self,
        *,
        timeout_s: float = 10.0,
        max_redirects: int = MAX_REDIRECTS,
        max_body_bytes: int = MAX_BODY_BYTES,
        resolver: AbstractResolver | None = None,
    ):
        self.timeout_s = max(1.0, min(float(timeout_s), 30.0))
        self.max_redirects = max(0, min(int(max_redirects), 5))
        self.max_body_bytes = max(4096, min(int(max_body_bytes), MAX_BODY_BYTES))
        self._resolver = resolver

    async def read(self, url: str) -> WebDocument:
        current = validate_public_url(url)
        resolver = PublicResolver(self._resolver)
        connector = aiohttp.TCPConnector(resolver=resolver, ttl_dns_cache=0)
        timeout = aiohttp.ClientTimeout(
            total=self.timeout_s,
            connect=min(5.0, self.timeout_s),
            sock_connect=min(5.0, self.timeout_s),
            sock_read=min(6.0, self.timeout_s),
        )
        try:
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                trust_env=False,
                auto_decompress=True,
                headers={
                    "User-Agent": "0liviA/0.1 (+personal research; read-only)",
                    "Accept": "text/html,text/plain,application/json,application/xml;q=0.9,*/*;q=0.1",
                },
            ) as session:
                for hop in range(self.max_redirects + 1):
                    async with session.get(current, allow_redirects=False) as response:
                        if 300 <= response.status < 400:
                            if hop >= self.max_redirects:
                                raise WebReadError("too_many_redirects")
                            location = response.headers.get("Location", "").strip()
                            if not location:
                                raise WebReadError("redirect_without_location")
                            current = validate_public_url(urljoin(current, location))
                            continue

                        if response.status < 200 or response.status >= 300:
                            raise WebReadError(f"http_{response.status}")

                        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                        if not any(content_type.startswith(item) for item in ALLOWED_TYPES):
                            raise WebReadError("content_type_not_allowed")

                        chunks: list[bytes] = []
                        size = 0
                        async for chunk in response.content.iter_chunked(16 * 1024):
                            size += len(chunk)
                            if size > self.max_body_bytes:
                                raise WebReadError("body_too_large")
                            chunks.append(chunk)
                        title, text = extract_text(b"".join(chunks), content_type)
                        if not text:
                            raise WebReadError("empty_document")
                        return WebDocument(
                            url=current,
                            title=title,
                            text=text,
                            content_type=content_type,
                            status=response.status,
                        )
        except asyncio.TimeoutError as exc:
            raise WebReadError("timeout") from exc
        except aiohttp.ClientError as exc:
            raise WebReadError("network_error") from exc
        finally:
            await connector.close()
        raise WebReadError("unreachable")
