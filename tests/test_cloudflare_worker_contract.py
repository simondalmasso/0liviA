from pathlib import Path

WORKER = Path("cloudflare/worker.mjs").read_text(encoding="utf-8")


def test_cloudflare_keeps_canonical_surface_public_shell_only():
    assert "const PUBLIC_SHELL_ONLY = true;" in WORKER
    assert "const TRANSITIONAL_BRIDGE_ENABLED = false;" in WORKER
    assert 'api_mode: "public_shell"' in WORKER
    assert "provider_ready: false" in WORKER
    assert "inference_enabled: false" in WORKER
    assert "web_read: false" in WORKER
    assert "hard_zero_cost: !demoReady" in WORKER
    assert "demo_cost_guaranteed: false" in WORKER
    assert 'canonical_backend: "self_hosted_python_core"' in WORKER


def test_public_demo_is_isolated_and_fail_closed_until_zero_cost_is_confirmed():
    assert 'const DEMO_MODEL = "@cf/zai-org/glm-4.7-flash";' in WORKER
    assert 'const DEMO_PROVIDER = "workers-ai-demo";' in WORKER
    assert "OLIVIA_DEMO_ZERO_COST_CONFIRMED" in WORKER
    assert 'env?.OLIVIA_DEMO_ZERO_COST_CONFIRMED === "1"' in WORKER
    assert "env?.AI" in WORKER
    assert "env?.COST_GUARD" in WORKER
    assert 'url.pathname === "/api/demo-chat"' in WORKER
    assert "await env.AI.run(DEMO_MODEL" in WORKER
    assert "demo_provider_ready" in WORKER
    assert "canonical: false" in WORKER


def test_cloudflare_demo_has_no_external_provider_credentials_or_fetch_bridge():
    for forbidden in (
        "NVIDIA_API_KEY",
        "NVIDIA_NIM_PRODUCTION_ENTITLED",
        "integrate.api.nvidia.com",
        "text.pollinations.ai",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        assert forbidden not in WORKER
    assert "await fetch(" not in WORKER


def test_canonical_api_routes_still_fail_closed():
    assert 'url.pathname === "/api/chat"' in WORKER
    assert 'url.pathname === "/api/read-url"' in WORKER
    assert 'url.pathname.startsWith("/api/")' in WORKER
    assert 'error: "bridge_disabled"' in WORKER
    assert "status: 503" in WORKER


def test_demo_bounds_context_output_and_daily_usage():
    assert "const DEMO_DAILY_REQUEST_LIMIT = 25;" in WORKER
    assert "const DEMO_MAX_TOTAL_CHARS = 8000;" in WORKER
    assert "const DEMO_MAX_MESSAGES = 8;" in WORKER
    assert "const DEMO_MAX_OUTPUT_TOKENS = 256;" in WORKER
    assert "contentLength > 16_384" in WORKER
    assert "if (totalChars > DEMO_MAX_TOTAL_CHARS)" in WORKER
    assert "if (count >= DEMO_DAILY_REQUEST_LIMIT)" in WORKER
    assert 'lastUser.content.startsWith("/")' in WORKER


def test_demo_redacts_secret_shapes_before_provider_egress():
    for marker in (
        r"\bbearer\s+",
        r"\bsk-",
        r"\bnvapi-",
        "api[_-]?key",
        "authorization",
        "password",
        "[redacted]",
    ):
        assert marker in WORKER


def test_cloudflare_serves_static_assets_outside_health_and_api():
    assert "return env.ASSETS.fetch(request)" in WORKER
    assert 'url.pathname === "/healthz"' in WORKER


def test_cost_guard_is_active_only_for_explicit_demo_route():
    assert "export class CostGuard" in WORKER
    assert 'url.pathname !== "/allow"' in WORKER
    assert 'env.COST_GUARD.idFromName("public-demo-global")' in WORKER
    assert "this.state.storage.get" in WORKER
    assert "this.state.storage.put" in WORKER


def test_demo_rejects_unknown_origins_and_bounds_stream_before_inference():
    assert 'const origin = request.headers.get("origin")' in WORKER
    assert "if (!trustedDemoOrigin(request))" in WORKER
    assert "origin_forbidden" in WORKER
    assert "totalBytes > 16_384" in WORKER
    assert "readDemoBody(request)" in WORKER
    assert "await request.text()" not in WORKER


def test_demo_identity_is_instance_neutral():
    assert "la IA personal de Simón" not in WORKER
    assert "demostración pública" in WORKER
    assert "No tenés identidad de propietario" in WORKER
