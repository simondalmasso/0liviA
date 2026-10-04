from pathlib import Path

WORKER = Path("cloudflare/worker.mjs").read_text(encoding="utf-8")


def test_cloudflare_identity_and_web_caps_are_explicit():
    assert 'const MODEL = "@cf/qwen/qwen3-30b-a3b-fp8";' in WORKER
    assert "const MAX_CALLS_PER_UTC_DAY = 80;" in WORKER
    assert "const MAX_URLS_PER_TURN = 2;" in WORKER
    assert "const MAX_WEB_CHARS_PER_URL = 12000;" in WORKER
    assert "Qwen3-30B-A3B-FP8, corriendo en Cloudflare Workers AI." in WORKER


def test_cloudflare_web_reader_fails_closed_on_missing_origin_and_redirects():
    assert "if (!origin) return false;" in WORKER
    assert 'const MAX_REDIRECTS = 3;' in WORKER
    assert 'redirect: "manual"' in WORKER
    assert "response.status >= 300 && response.status < 400" in WORKER
    assert 'response.headers.get("location")' in WORKER


def test_cloudflare_web_reader_blocks_additional_reserved_networks():
    for literal in (
        "100.64.",
        "192.0.2.",
        "198.51.100.",
        "203.0.113.",
        "fc00",
        "fe80",
        "2001:db8",
    ):
        assert literal in WORKER


def test_health_declares_web_read_once():
    assert WORKER.count("web_read: true") == 1
