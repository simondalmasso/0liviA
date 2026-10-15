"""Qwen release must not charge Workers Paid or deploy on unproved billing."""
from __future__ import annotations

import importlib.util
import sys
import json
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
    assert "npm exec --yes wrangler" not in raw
    assert "npm exec" not in raw
    assert "/api/demo-chat" not in raw
    assert 'OLIVIA_DEMO_QWEN_ZERO_COST_CONFIRMED' not in raw


def test_billing_proof_uses_only_separate_read_token_and_same_account(monkeypatch, capsys):
    requests = []
    class FakeResponse:
        status = 200
        def read(self, n):
            return json.dumps(payload()).encode()
    class FakeConnection:
        def __init__(self, host, timeout):
            assert host == "api.cloudflare.com"
            requests.append(("connect", timeout))
        def request(self, method, path, headers):
            requests.append((method, path, headers))
        def getresponse(self):
            return FakeResponse()
        def close(self):
            pass

    monkeypatch.setattr(module.http.client, "HTTPSConnection", FakeConnection)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "deployment-only-secret")
    monkeypatch.delenv("CLOUDFLARE_BILLING_READ_TOKEN", raising=False)
    assert module.main() == 2
    assert requests == []  # no fallback to deployment credentials
    assert "deployment-only-secret" not in capsys.readouterr().err

    monkeypatch.setenv("CLOUDFLARE_BILLING_READ_TOKEN", "billing-read-secret")
    assert module.main() == 0
    assert requests[1][0] == "GET"
    assert requests[1][1] == "/client/v4/accounts/" + "a" * 32 + "/subscriptions?per_page=100"
    assert requests[1][2]["Authorization"] == "Bearer billing-read-secret"
    output = capsys.readouterr()
    assert "billing-read-secret" not in output.out + output.err
    assert "deployment-only-secret" not in output.out + output.err


def test_billing_preflight_denies_forbidden_and_oversized_responses(monkeypatch, capsys):
    class FakeResponse:
        def __init__(self, status, body):
            self.status, self.body = status, body
        def read(self, n):
            return self.body[:n]
    class FakeConnection:
        response = FakeResponse(403, b'{"success":false}')
        def __init__(self, host, timeout):
            pass
        def request(self, method, path, headers):
            assert method == "GET"
        def getresponse(self):
            return self.response
        def close(self):
            pass

    monkeypatch.setattr(module.http.client, "HTTPSConnection", FakeConnection)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "b" * 32)
    monkeypatch.setenv("CLOUDFLARE_BILLING_READ_TOKEN", "never-print-this-token")
    for response in (
        FakeResponse(403, b'{"success":false}'),
        FakeResponse(200, b"x" * 128001),
        FakeResponse(200, b'{"success":true,"result":[]}'),
        FakeResponse(200, json.dumps(payload({
            "state": "Paid",
            "rate_plan": {"id": "WORKERS_PAID", "scope": "account"}
        })).encode()),
        FakeResponse(200, json.dumps(payload({
            "state": "Paid",
            "rate_plan": {"id": "AI_GATEWAY", "public_name": "AI Gateway Unified Billing"}
        })).encode()),
    ):
        FakeConnection.response = response
        assert module.main() == 2
    printed = capsys.readouterr()
    assert "never-print-this-token" not in printed.out + printed.err
    assert "WORKERS_PAID" not in printed.out + printed.err


def test_missing_pagination_or_nonzero_workers_free_price_denied():
    assert not module.free_plan_confirmed({"success": True, "result": []})
    assert not module.free_plan_confirmed({"success": True, "result": [],
                                            "result_info": {"total_count": True}})
    assert not module.free_plan_confirmed(payload({
        "state": "Provisioned", "price": 5.0,
        "rate_plan": {"id": "WORKERS_FREE", "scope": "account"}
    }))
