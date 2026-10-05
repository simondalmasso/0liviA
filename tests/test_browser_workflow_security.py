from pathlib import Path

WORKFLOW = Path(".github/workflows/browser-agent.yml").read_text(encoding="utf-8")
RUNNER = Path("scripts/browser_snapshot.py").read_text(encoding="utf-8")


def test_browser_workflow_is_manual_public_repo_only_and_least_privilege():
    assert "workflow_dispatch:" in WORKFLOW
    assert "permissions:\n  contents: read" in WORKFLOW
    assert 'test "$REPO_PRIVATE" = "false"' in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW
    assert "timeout-minutes: 8" in WORKFLOW
    assert "publish" not in WORKFLOW.lower()


def test_browser_workflow_pins_runtime_and_blocks_reserved_egress():
    assert "'playwright==1.55.0'" in WORKFLOW
    for cidr in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    ):
        assert cidr in WORKFLOW


def test_browser_runner_guards_all_pages_and_disables_downloads():
    assert 'await context.route("**/*", guard)' in RUNNER
    assert 'await page.route("**/*", guard)' not in RUNNER
    assert "accept_downloads=False" in RUNNER
    assert 'service_workers="block"' in RUNNER
    assert 'request.resource_type in {"media", "websocket"}' in RUNNER
    assert "MAX_REQUESTS = 100" in RUNNER
    assert "MAX_TEXT_CHARS = 30_000" in RUNNER
