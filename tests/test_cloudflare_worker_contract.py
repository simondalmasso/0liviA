from pathlib import Path

WORKER = Path("cloudflare/worker.mjs").read_text(encoding="utf-8")
STATIC_DEPLOY = Path(".github/workflows/deploy-public-static.yml").read_text(encoding="utf-8")
E2E_WORKFLOW = Path(".github/workflows/e2e.yml").read_text(encoding="utf-8")


def test_public_worker_is_static_only_and_never_uses_auth0_or_google_identity():
    assert "const PUBLIC_SHELL_ONLY = true;" in WORKER
    assert 'api_mode: "public_shell"' in WORKER
    assert "static_only: true" in WORKER
    assert "bridge_enabled: TRANSITIONAL_BRIDGE_ENABLED" in WORKER
    assert "provider_ready: false" in WORKER
    assert "inference_enabled: false" in WORKER
    assert "demo_inference_enabled: false" in WORKER
    assert "demo_provider_ready: false" in WORKER
    assert "hard_zero_cost: true" in WORKER
    assert 'canonical_backend: "self_hosted_python_core"' in WORKER
    assert "owner_auth.mjs" not in WORKER
    assert "OLIVIA_AUTH0_" not in WORKER
    assert "requireOwnerInference" not in WORKER


def test_every_public_api_route_fails_closed_without_identity_or_provider_side_effects():
    assert 'url.pathname.startsWith("/api/")' in WORKER
    assert 'error: "bridge_disabled"' in WORKER
    assert "status: 503" in WORKER
    assert "env.AI.run" not in WORKER
    assert "env.COST_GUARD" not in WORKER
    assert "await fetch(" not in WORKER


def test_public_worker_preserves_security_headers_and_immutable_release_stamp():
    assert "function hardened(response)" in WORKER
    assert 'return hardened(result)' in WORKER
    assert 'url.pathname === "/healthz"' in WORKER
    assert "release_sha: /^[0-9a-f]{40}$/" in WORKER
    static = Path("web/_headers").read_text(encoding="utf-8")
    assert static.startswith("# Cloudflare Workers static assets")
    for header in (
        "X-Content-Type-Options: nosniff", "X-Frame-Options: DENY",
        "Referrer-Policy: no-referrer", "Strict-Transport-Security: max-age=31536000",
        "Content-Security-Policy:", "Permissions-Policy:",
    ):
        assert header in static


def test_retained_durable_object_export_is_inert_and_unbound():
    assert "export class CostGuard" in WORKER
    assert 'return json({ error: "not_found" }, { status: 404 })' in WORKER
    assert "this.state.storage.transaction" not in WORKER
    assert '"exports": {"CostGuard": {"type": "durable-object", "storage": "sqlite"}}' in STATIC_DEPLOY
    assert '"durable_objects":' not in STATIC_DEPLOY
    assert '"ai":' not in STATIC_DEPLOY


def test_only_static_no_inference_workflow_deploys_on_main():
    trigger = STATIC_DEPLOY.split("permissions:", 1)[0]
    assert "  push:" in trigger
    assert "branches: [main]" in trigger
    assert "  workflow_dispatch:" in trigger
    assert '"OLIVIA_STATIC_ONLY": "1"' in STATIC_DEPLOY
    assert '"OLIVIA_DEMO_ZERO_COST_CONFIRMED": "0"' in STATIC_DEPLOY
    assert "npm exec --yes wrangler@4.127.1" in STATIC_DEPLOY
    assert 'body.get("static_only") is True' in STATIC_DEPLOY
    assert 'body.get("demo_inference_enabled") is False' in STATIC_DEPLOY
    assert 'body.get("hard_zero_cost") is True' in STATIC_DEPLOY
    assert "/api/demo-chat" not in STATIC_DEPLOY
    assert "confirm_account_no_overage" not in STATIC_DEPLOY
    assert "run_worker_first" not in STATIC_DEPLOY
    assert not Path(".github/workflows/deploy-public-shell.yml").exists()


def test_static_deploy_uses_exact_sha_and_get_only_live_smoke():
    assert 'git merge-base --is-ancestor "${sha}" origin/main' in STATIC_DEPLOY
    assert '"release_sha": body.get("release_sha") == os.environ["RELEASE_SHA"]' in STATIC_DEPLOY
    assert "for attempt in 1 2 3 4 5 6 7 8;" in STATIC_DEPLOY
    assert "sleep 3" in STATIC_DEPLOY
    assert '[[ "${observed}" == "${RELEASE_SHA}" ]]' in STATIC_DEPLOY
    assert 'curl -fsS --max-time 20 "${base}/healthz?sha=${RELEASE_SHA}"' in STATIC_DEPLOY
    assert "-X POST" not in STATIC_DEPLOY


def test_browser_e2e_expects_inference_disabled_and_does_not_fake_ai_success():
    assert "static public shell is usable but clearly refuses inference" in Path("tests-e2e/public-demo.e2e.ts").read_text(encoding="utf-8")
    assert "GET-only static/no-inference checks" in E2E_WORKFLOW
    assert "Production is not static-only-ready" in E2E_WORKFLOW
    assert "workers-ai-demo" not in E2E_WORKFLOW
    assert "POST /api/demo-chat" not in E2E_WORKFLOW
