from __future__ import annotations

import socket

import pytest

from olivia.web import PublicResolver, WebReadError, extract_text, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "file:///etc/passwd",
        "http://user:pass@example.com/",
        "https://example.com:8443/",
    ],
)
def test_url_validation_rejects_private_credentials_and_odd_ports(url):
    with pytest.raises(WebReadError):
        validate_public_url(url)


def test_url_validation_accepts_public_http_https_and_strips_fragment():
    assert validate_public_url("https://Example.COM/path?q=1#frag") == "https://example.com/path?q=1"


class _FakeResolver:
    def __init__(self, records):
        self.records = records
        self.closed = False

    async def resolve(self, host, port=0, family=socket.AF_UNSPEC):
        return self.records

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_public_resolver_fails_closed_if_any_dns_answer_is_private():
    resolver = PublicResolver(_FakeResolver([
        {"hostname": "example.com", "host": "93.184.216.34", "port": 443, "family": socket.AF_INET, "proto": 0, "flags": 0},
        {"hostname": "example.com", "host": "127.0.0.1", "port": 443, "family": socket.AF_INET, "proto": 0, "flags": 0},
    ]))
    with pytest.raises(OSError):
        await resolver.resolve("example.com", 443)


def test_html_extraction_drops_scripts_and_caps_text():
    title, text = extract_text(
        b"<html><head><title>Demo</title><script>SECRET_SCRIPT</script></head><body><h1>Hola</h1><p>Texto visible</p></body></html>",
        "text/html",
    )
    assert title == "Demo"
    assert "Hola" in text
    assert "Texto visible" in text
    assert "SECRET_SCRIPT" not in text
