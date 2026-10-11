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


def test_qwen_workflow_is_frozen_without_automatic_provider_deploy():
    raw = WORKFLOW.read_text(encoding="utf-8")
    before_jobs = raw.split("jobs:", 1)[0]
    assert "  workflow_dispatch:" in before_jobs
    assert "  push:" not in before_jobs
    assert "branches: [main]" not in before_jobs
    assert "acknowledge_frozen:" in raw
    assert "No Cloudflare API, no Wrangler deployment" in raw
    assert "CLOUDFLARE_API_TOKEN" not in raw
    assert "wrangler" not in raw.casefold()
    assert "npm exec" not in raw
    assert "/api/demo-chat" not in raw
    assert 'OLIVIA_DEMO_QWEN_ZERO_COST_CONFIRMED' not in raw
