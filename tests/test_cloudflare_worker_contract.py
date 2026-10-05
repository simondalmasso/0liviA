from pathlib import Path

WORKER = Path("cloudflare/worker.mjs").read_text(encoding="utf-8")


def test_cloudflare_surface_is_public_shell_only():
    assert "const PUBLIC_SHELL_ONLY = true;" in WORKER
    assert "const TRANSITIONAL_BRIDGE_ENABLED = false;" in WORKER
    assert 'api_mode: "public_shell"' in WORKER
    assert "provider_ready: false" in WORKER
    assert "inference_enabled: false" in WORKER
    assert "web_read: false" in WORKER
    assert "hard_zero_cost: true" in WORKER
    assert 'cost_reason: "no_inference_or_search_backend"' in WORKER


def test_cloudflare_public_shell_has_no_model_or_provider_credentials():
    for forbidden in (
        "NVIDIA_API_KEY",
        "NVIDIA_NIM_PRODUCTION_ENTITLED",
        "integrate.api.nvidia.com",
        "deepseek-v4",
        "gpt-oss",
        "glm-4",
        "qwen3",
        "env.AI",
        "COST_GUARD.get",
        "COST_GUARD.idFrom",
    ):
        assert forbidden not in WORKER


def test_cloudflare_api_routes_fail_closed_before_any_provider_use():
    assert 'url.pathname === "/api/chat"' in WORKER
    assert 'url.pathname === "/api/read-url"' in WORKER
    assert 'url.pathname.startsWith("/api/")' in WORKER
    assert 'error: "bridge_disabled"' in WORKER
    assert "status: 503" in WORKER
    assert "await fetch(" not in WORKER


def test_cloudflare_serves_only_static_assets_outside_health_and_api():
    assert "return env.ASSETS.fetch(request)" in WORKER
    assert 'url.pathname === "/healthz"' in WORKER


def test_historical_cost_guard_export_is_inert():
    assert "export class CostGuard" in WORKER
    assert 'error: "historical_namespace_inert"' in WORKER
    assert "status: 410" in WORKER
