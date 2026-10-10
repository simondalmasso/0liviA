"""Agent Fabric PR-A: no inference network calls; synthetic providers only."""
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import replace
from datetime import date, timedelta

import pytest

from olivia.harness.budget import BudgetDenied, BudgetGuard
from olivia.harness.execution import DeniedModelInvocation, guarded_stream
from olivia.harness.model_registry import (
    ModelAdmission, ModelAttestation, ModelRegistry, ParentBudget,
)
from olivia.router import ProviderSpec


TODAY = date(2026, 10, 10)


def spec(**changes):
    defaults = dict(
        name="safe", base_url="https://api.safe.example/v1", model="model-1",
        api_key_env="SAFE_KEY", cost_mode="free_hard_cap", daily_limit=3,
        capabilities=("chat", "code"),
    )
    defaults.update(changes)
    return ProviderSpec(**defaults)


def evidence(**changes):
    defaults = dict(
        provider="safe", model="model-1", account_id="owner-safely-identified",
        cost_mode="free_hard_cap", evidence_ref="github-issue:97/account-review",
        reviewed_at=TODAY, expires_at=TODAY + timedelta(days=1),
        production_permitted=True, no_credit_overage_verified=True,
        capabilities=frozenset({"chat", "code"}),
        max_input_tokens=1000, max_output_tokens=256, daily_request_cap=2,
    )
    defaults.update(changes)
    return ModelAttestation(**defaults)


def admitted(**changes):
    r = ModelRegistry([spec()], [evidence(**changes)], today=TODAY)
    return r.admit("safe", "chat", 100, 50)


def test_empty_registry_and_unattested_provider_are_denied():
    assert ModelRegistry([]).admit("a", "chat", 1, 1).reason == "unknown_provider"
    record = ModelRegistry([spec()], today=TODAY).admit("safe", "chat", 20, 20)
    assert not record.allowed
    assert record.reason == "account_model_not_attested"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"production_permitted": False}, "production_or_no_overage_unverified"),
        ({"no_credit_overage_verified": False}, "production_or_no_overage_unverified"),
        ({"expires_at": TODAY - timedelta(days=1), "reviewed_at": TODAY - timedelta(days=3)}, "attestation_expired_or_future"),
        ({"reviewed_at": TODAY + timedelta(days=1), "expires_at": TODAY + timedelta(days=2)}, "attestation_expired_or_future"),
        ({"max_input_tokens": 50}, "model_token_limit_exceeded"),
        ({"max_output_tokens": 30}, "model_token_limit_exceeded"),
        ({"cost_mode": "local"}, "attestation_mismatch"),
        ({"capabilities": frozenset({"code"})}, "attestation_mismatch"),
    ],
)
def test_missing_entitlement_rights_time_or_token_limit_denies(changes, reason):
    data = admitted(**changes)
    assert not data.allowed
    assert data.reason == reason


@pytest.mark.parametrize("mode", ["free_unverified", "paid", "plan_included"])
def test_credit_prototype_paid_or_plan_routes_not_admitted(mode):
    # This is an Agent Fabric policy, not a migration of the canonical router.
    if mode == "plan_included":
        with pytest.raises(ValueError, match="unsupported cost mode"):
            evidence(cost_mode=mode)
    else:
        r = ModelRegistry([spec(cost_mode=mode)], [evidence()], today=TODAY)
        assert not r.admit("safe", "chat", 100, 50).allowed


def test_local_attestation_requires_real_loopback():
    local = spec(name="local", model="small", base_url="http://127.0.0.1:9000/v1",
                 cost_mode="local", daily_limit=0)
    ev = evidence(provider="local", model="small", cost_mode="local", account_id="localhost")
    registry = ModelRegistry([local], [ev], today=TODAY)
    assert registry.admit("local", "chat", 1, 1).allowed
    malicious = replace(local, base_url="http://local.internal:9000/v1")
    assert ModelRegistry([malicious], [ev], today=TODAY).admit("local", "chat", 1, 1).reason == "local_model_not_loopback"


def test_alias_nemotron_rejected_before_any_admission():
    with pytest.raises(ValueError, match="forbidden model"):
        evidence(provider="clean", model="nemo\u200btron-3")
    with pytest.raises(Exception, match="forbidden model"):
        spec(model="@cf/nvidia/nemotron-3-120b-a12b")


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "100"])
def test_token_requests_must_be_positive_integers(value):
    record = ModelRegistry([spec()], [evidence()], today=TODAY).admit("safe", "chat", value, 50)
    assert record.reason == "invalid_token_budget"


def test_parent_cannot_delegate_more_than_owned():
    r = ModelRegistry([spec()], [evidence()], today=TODAY)
    assert r.admit("safe", "chat", 100, 50, ParentBudget(100, 50, 100)).reason == "parent_budget_exceeded"
    assert r.admit("safe", "chat", 100, 50, ParentBudget(100, 50, 150)).allowed


def test_exact_identity_capability_and_daily_limit():
    r = ModelRegistry([spec()], [evidence()], today=TODAY)
    assert r.admit("safe", "research", 1, 1).reason == "capability_not_allowed"
    assert r.admit("safe", "chat", 100, 50).daily_request_cap == 2
    assert r.admit("safe", "chat", 1001, 1).reason == "model_token_limit_exceeded"
    assert r.admit("safe", "chat", 1, 257).reason == "model_token_limit_exceeded"
    with pytest.raises(ValueError, match="duplicate model attestation"):
        ModelRegistry([spec()], [evidence(), evidence()])


def test_nested_scope_atomic_budget_and_no_auto_replays(tmp_path):
    file = tmp_path / "same.sqlite3"
    budget = BudgetGuard(file, today=TODAY)
    budget.create_scope("root", max_tokens=240, max_calls=2)
    budget.create_scope("childA", max_tokens=200, max_calls=2, parent_scope_id="root")
    budget.create_scope("childB", max_tokens=200, max_calls=2, parent_scope_id="root")
    m = admitted()
    assert m.allowed
    budget.reserve(m, request_id="job1", scope_id="childA")
    with pytest.raises(BudgetDenied, match="duplicate_or_uncertain_request"):
        budget.reserve(m, request_id="job1", scope_id="childA")
    budget.settle("job1", uncertain=True)
    with pytest.raises(BudgetDenied, match="duplicate_or_uncertain_request"):
        BudgetGuard(file, today=TODAY).reserve(m, request_id="job1", scope_id="childA")
    with pytest.raises(BudgetDenied, match="scope_budget_exhausted"):
        budget.reserve(m, request_id="job2", scope_id="childB")
    assert budget.inspect_scope("root")["reserved_calls"] == 1
    assert budget.inspect_scope("root")["reserved_tokens"] == 150


def test_daily_limit_shared_across_independent_job_scopes_and_restart(tmp_path):
    file = tmp_path / "guard.sqlite3"
    bg = BudgetGuard(file, today=TODAY)
    for i in range(3):
        bg.create_scope(f"job{i}", max_tokens=150, max_calls=1)
    m = admitted()
    bg.reserve(m, request_id="id1", scope_id="job0")
    BudgetGuard(file, today=TODAY).reserve(m, request_id="id2", scope_id="job1")
    with pytest.raises(BudgetDenied, match="daily_request_budget_exhausted"):
        BudgetGuard(file, today=TODAY).reserve(m, request_id="id3", scope_id="job2")


def test_scope_child_cannot_exceed_parent_or_elevate_later(tmp_path):
    guard = BudgetGuard(tmp_path / "budget.sqlite3", today=TODAY)
    guard.create_scope("parent", max_tokens=200, max_calls=2)
    with pytest.raises(BudgetDenied, match="child_scope_exceeds_parent"):
        guard.create_scope("child", max_tokens=300, max_calls=1, parent_scope_id="parent")
    guard.create_scope("child", max_tokens=150, max_calls=1, parent_scope_id="parent")
    guard.create_scope("child", max_tokens=150, max_calls=1, parent_scope_id="parent")
    with pytest.raises(BudgetDenied, match="cannot_change_existing_scope"):
        guard.create_scope("child", max_tokens=190, max_calls=1, parent_scope_id="parent")


@pytest.mark.asyncio
async def test_guarded_model_execution_denies_without_touching_provider(tmp_path):
    class Fake:
        def __init__(self):
            self.spec = spec()
            self.calls = 0

        async def stream(self, _messages):
            self.calls += 1
            yield "should not happen"

    fake = Fake()
    guard = BudgetGuard(tmp_path / "budget.sqlite3", today=TODAY)
    guard.create_scope("job", max_tokens=1000, max_calls=1)
    registry = ModelRegistry([fake.spec], today=TODAY)
    with pytest.raises(DeniedModelInvocation, match="account_model_not_attested"):
        _ = [t async for t in guarded_stream(registry=registry, budget=guard,
            provider=fake, messages=[], capability="chat", input_tokens=10,
            output_tokens=10, scope_id="job", request_id="r1")]
    assert fake.calls == 0
    assert guard.inspect_scope("job")["reserved_calls"] == 0


@pytest.mark.asyncio
async def test_guarded_model_execution_one_call_no_retry_when_outcome_uncertain(tmp_path):
    class Fake:
        def __init__(self):
            self.spec = spec()
            self.calls = 0
        async def stream(self, _messages):
            self.calls += 1
            yield "visible"
            raise RuntimeError("stream interruption")

    fake = Fake()
    guard = BudgetGuard(tmp_path / "budget.sqlite3", today=TODAY)
    guard.create_scope("job", max_tokens=300, max_calls=2)
    registry = ModelRegistry([fake.spec], [evidence()], today=TODAY)
    with pytest.raises(RuntimeError, match="interruption"):
        _ = [t async for t in guarded_stream(registry=registry, budget=guard,
            provider=fake, messages=[], capability="chat", input_tokens=100,
            output_tokens=50, scope_id="job", request_id="r1")]
    with pytest.raises(DeniedModelInvocation, match="duplicate_or_uncertain_request"):
        _ = [t async for t in guarded_stream(registry=registry, budget=guard,
            provider=fake, messages=[], capability="chat", input_tokens=100,
            output_tokens=50, scope_id="job", request_id="r1")]
    assert fake.calls == 1
    assert guard.inspect_scope("job")["reserved_tokens"] == 150


@pytest.mark.asyncio
async def test_success_marks_receipt_and_no_double_settlement(tmp_path):
    class Fake:
        def __init__(self):
            self.spec = spec()
        async def stream(self, _messages):
            yield "ok"

    bg = BudgetGuard(tmp_path / "b.sqlite3", today=TODAY)
    bg.create_scope("s", max_tokens=150, max_calls=1)
    provider = Fake()
    registry = ModelRegistry([provider.spec], [evidence()], today=TODAY)
    assert [x async for x in guarded_stream(registry=registry,budget=bg,provider=provider,
        messages=[], capability="chat",input_tokens=100,output_tokens=50,
        scope_id="s",request_id="job")] == ["ok"]
    with pytest.raises(BudgetDenied, match="reservation_already_settled"):
        bg.settle("job")


def test_daily_limit_atomic_with_multiple_connections(tmp_path):
    file = tmp_path / "same.sqlite3"
    BudgetGuard(file, today=TODAY).create_scope("root", max_tokens=1000, max_calls=10)
    m = admitted(daily_request_cap=1)
    BudgetGuard(file, today=TODAY).reserve(m, request_id="first", scope_id="root")
    with pytest.raises(BudgetDenied, match="daily_request_budget_exhausted"):
        BudgetGuard(file, today=TODAY).reserve(m, request_id="second", scope_id="root")
    assert BudgetGuard(file, today=TODAY).inspect_scope("root")["reserved_calls"] == 1
