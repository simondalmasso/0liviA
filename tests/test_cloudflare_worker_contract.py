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


def test_web_fetch_is_guarded_before_any_external_read():
    chat_start = WORKER.index("async function chat(request, env)")
    web_start = WORKER.index("const webContext = await webContextFor(messages);", chat_start)
    guard_start = WORKER.index("const guard = await takeZeroCostSlot(env);", chat_start)
    assert guard_start < web_start

    read_route = WORKER.index('url.pathname === "/api/read-url"')
    read_guard = WORKER.index("await takeZeroCostSlot(env)", read_route)
    read_fetch = WORKER.index("await fetchWebContext(target)", read_route)
    assert read_guard < read_fetch


def test_web_reader_streams_with_a_hard_body_cap():
    assert "const MAX_WEB_BYTES_PER_URL = 65536;" in WORKER
    assert "response.body?.getReader()" in WORKER
    assert "await reader.cancel()" in WORKER
    assert "await response.text()" not in WORKER


def test_zero_cost_status_fails_closed_until_account_guard_is_verified():
    assert "const ACCOUNT_ZERO_COST_VERIFIED = false;" in WORKER
    assert "hard_zero_cost: ACCOUNT_ZERO_COST_VERIFIED" in WORKER
    assert "local_daily_cap: true" in WORKER
    assert "account_overage_guard_verified: ACCOUNT_ZERO_COST_VERIFIED" in WORKER


def test_provider_catalog_prefers_deepseek_nim_and_has_zero_cost_fallbacks():
    assert 'deepseek-ai/deepseek-v4.1-flash' in WORKER
    assert 'https://integrate.api.nvidia.com/v1/chat/completions' in WORKER
    assert 'NVIDIA_API_KEY' in WORKER
    assert '@cf/zai-org/glm-4.7-flash' in WORKER
    assert '@cf/qwen/qwen3-30b-a3b-fp8' in WORKER
    for forbidden in ('nemotron', 'claude-sonnet', 'apmix', 'compound-mini'):
        assert forbidden not in WORKER.lower()


def test_provider_failover_is_precommit_and_fail_closed():
    assert 'async function generateWithFailover' in WORKER
    assert 'for (const provider of providerCatalog(env))' in WORKER
    assert 'if (!provider.available) continue;' in WORKER
    assert 'attempts.push' in WORKER
    assert 'throw new Error("no_zero_cost_provider_available")' in WORKER


def test_health_exposes_router_without_exposing_secrets():
    assert 'provider_catalog:' in WORKER
    assert 'primary_model:' in WORKER
    assert 'NVIDIA_API_KEY:' not in WORKER
