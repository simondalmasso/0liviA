"""Qwen release must not charge Workers Paid or deploy on unproved billing."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_cloudflare_free.py"
WORKFLOW = ROOT / ".github" / "workflows" / "activate-qwen-once.yml"
spec = importlib.util.spec_from_file_location("verify_cloudflare_free", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def payload(*entries):
    return {
        "success": True, "result": list(entries),
        "result_info": {"total_count": len(entries)},
    }


def test_empty_verified_subscriptions_mean_default_workers_free():
    assert module.free_plan_confirmed(payload())


def test_workers_free_subscription_is_admitted():
    assert module.free_plan_confirmed(payload({
        "state": "Provisioned",
        "rate_plan": {"id": "WORKERS_FREE", "scope": "account"},
    }))


def test_paid_and_unknown_workers_plans_are_rejected():
    for plan in ("WORKERS_PAID", "WORKERS_ENTERPRISE", "WORKERS_TEST"):
        assert not module.free_plan_confirmed(payload({
            "state": "Paid",
            "rate_plan": {"id": plan, "scope": "account"},
        }))
    assert not module.free_plan_confirmed(payload({
        "state": "Paid",
        "rate_plan": {"id": "mystery", "public_name": "Workers Something"},
    }))


def test_not_authenticated_partial_page_or_bad_payload_rejected():
    assert not module.free_plan_confirmed(None)
    assert not module.free_plan_confirmed({"success": False, "result": []})
    assert not module.free_plan_confirmed({"success": True, "result": "oops"})
    assert not module.free_plan_confirmed({
        "success": True, "result": [],
        "result_info": {"total_count": 2},
    })


def test_paid_zone_subscription_not_misread_as_workers_subscription():
    assert module.free_plan_confirmed(payload({
        "state": "Paid",
        "rate_plan": {"id": "pro", "scope": "zone", "public_name": "Pro Plan"},
    }))


def test_workflow_only_once_and_secret_safety():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "branches: [main]" in raw
    assert "- .github/workflows/activate-qwen-once.yml" in raw
    assert "on:" in raw
    assert "WORKERS_FREE_BILLING_PROOF" not in raw
    assert "OWNER_ATTESTED_NOT_API_VERIFIED" in raw
    assert 'test "${OLIVIA_DEMO_ZERO_COST_CONFIRMED}" = "1"' in raw
    assert "python3 scripts/verify_cloudflare_free.py" not in raw
    assert "OLIVIA_DEMO_QWEN_ZERO_COST_CONFIRMED" in raw
    assert '"@cf/qwen/qwen3.8-27b"' in raw
    assert "QWEN_ROLLED_BACK=YES" in raw
    assert "if: failure() && steps.deploy.outcome == 'success'" in raw
    assert "npm exec --yes wrangler@4.127.1" in raw
    assert "CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}" in raw


def test_live_qwen_canary_waits_for_exact_sha_without_spending_quota():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "Wait for exact immutable release at the public edge" in raw
    assert "for attempt in $(seq 1 24)" in raw
    assert 'h.get("release_sha") == os.environ["RELEASE_SHA"]' in raw
    assert raw.index("EXACT_SHA_EDGE_READY=TRUE") < raw.index(
        "Live Qwen3.8 model canary (one inference request)"
    )
    assert raw.count('--data \'{"model":"qwen"') == 1
    assert "QWEN_ROLLED_BACK=YES" in raw


def test_qwen_canary_diagnoses_http_failures_without_echoing_provider_body():
    yaml = WORKFLOW.read_text(encoding="utf-8")
    assert "QWEN_CANARY_HTTP_STATUS=" in yaml
    assert "QWEN_CANARY_ERROR=" in yaml
    assert "re.fullmatch" in yaml
    assert '"unclassified"' in yaml
    assert 'if [[ "${status}" != "200" ]]; then' in yaml
    assert "QWEN_ROLLED_BACK=YES" in yaml


def test_qwen_edge_retries_only_before_inference():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert '"${status}" == "503" && "${canary_error}" == "qwen_unavailable"' in raw
    assert "for attempt in $(seq 1 18)" in raw
    assert "WAIT_QWEN_ROUTE_PROPAGATION" in raw
    assert raw.count('env.AI.run(') == 1  # only mentioned in comment
    assert raw.count('--data \'{"model":"qwen"') == 1
    assert 'if [[ "${status}" != "200" ]]; then' in raw
    assert "QWEN_ROLLED_BACK=YES" in raw
