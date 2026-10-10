"""Agent Fabric PR-C1: mock-only tool gateway authorization and uncertainty."""
from __future__ import annotations

import sqlite3

import pytest

from olivia.harness.agents import AgentFabric
from olivia.harness.tools import (
    ToolGateway, ToolRule, ToolReceipt, ToolDenied, ToolConflict, ToolOutcomeUnknown,
)

SHA = "a" * 64
RESULT_SHA = "b" * 64


def setup_runtime(tmp_path, *, calls=5, tools=("github.read", "github.pr")):
    path = tmp_path / "fabric.sqlite3"
    clock = [1000.0]
    f = AgentFabric(
        path,
        owner_verifier=lambda aid, digest, proof: proof == "owner-trusted",
        executor_verifier=lambda run, proof: proof == "worker-trusted",
        clock=lambda: clock[0],
    )
    f.propose("root", "proposal1", "planner", tools, 3000, calls)
    f.approve("root", proof="owner-trusted")
    f.create_run("root", "run1", "task1", SHA)
    lease = f.claim("run1", proof="worker-trusted", lease_seconds=60)
    return f, lease, clock


class FakeAdapter:
    def __init__(self, *, fail=False, accepted=False):
        self.calls = 0
        self.fail = fail
        self.accepted = accepted

    async def invoke(self, *, action, request_id, args_sha256, sandbox_id):
        self.calls += 1
        if self.fail:
            raise TimeoutError("unknown remote outcome")
        return ToolReceipt(
            state="accepted" if self.accepted else "completed",
            evidence_sha256=RESULT_SHA,
        )


def gateway(fabric, read=None, write=None, *, owner=True, sandbox=True,
            max_calls=4):
    registry = {}
    if read is not None:
        registry["github.read"] = (
            ToolRule("github.read", frozenset({"get"}), read_only=True), read
        )
    if write is not None:
        registry["github.pr"] = (
            ToolRule("github.pr", frozenset({"open"}), read_only=False,
                     sandbox_kind="github-actions"), write
        )
    return ToolGateway(
        fabric, registry,
        owner_action_verifier=(
            lambda request, run, tool, action, digest, proof: proof == "owner-action"
        ) if owner else None,
        sandbox_verifier=(
            lambda kind, sid, tool, proof: (
                kind == "github-actions" and sid == "isolated-worktree"
                and proof == "sandbox-attested"
            )
        ) if sandbox else None,
        max_actions_per_run=max_calls,
    )


@pytest.mark.asyncio
async def test_empty_gateway_does_not_run_any_tool(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    g = gateway(f)
    with pytest.raises(ToolDenied, match="unregistered_tool"):
        await g.execute("run1", lease, "op1", "github.read", "get", SHA)
    assert g.audit_events("run1") == []


@pytest.mark.asyncio
async def test_readonly_tool_requires_approved_agent_and_valid_lease(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    adapter = FakeAdapter()
    g = gateway(f, read=adapter)
    with pytest.raises(ToolDenied, match="lease_token_invalid"):
        await g.execute("run1", "forged", "opbad", "github.read", "get", SHA)
    answer = await g.execute("run1", lease, "op1", "github.read", "get", SHA)
    assert answer.state == "completed"
    assert answer.evidence_sha256 == RESULT_SHA
    assert adapter.calls == 1
    assert g.get_action("op1")["state"] == "completed"
    assert g.get_action("op1")["args_sha256"] == SHA
    assert not hasattr(g, "call_model")


@pytest.mark.asyncio
async def test_write_tool_needs_owner_action_proof_and_isolated_sandbox(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    write = FakeAdapter()
    g = gateway(f, write=write)
    for kwargs, reason in (
        ({}, "owner_action_approval_required"),
        ({"approval_proof": "model-self-approved"}, "owner_action_approval_required"),
        ({"approval_proof": "owner-action"}, "sandbox_attestation_required"),
        ({"approval_proof": "owner-action", "sandbox_id": "isolated-worktree",
          "sandbox_proof": "fake-sandbox"}, "sandbox_attestation_required"),
    ):
        with pytest.raises(ToolDenied, match=reason):
            await g.execute("run1", lease, "op1", "github.pr", "open", SHA, **kwargs)
    assert write.calls == 0
    done = await g.execute(
        "run1", lease, "op1", "github.pr", "open", SHA,
        approval_proof="owner-action", sandbox_id="isolated-worktree",
        sandbox_proof="sandbox-attested",
    )
    assert done.state == "completed" and write.calls == 1


@pytest.mark.asyncio
async def test_unknown_actions_cannot_bypass_explicit_tool_allowlist(tmp_path):
    f, lease, _ = setup_runtime(tmp_path, tools=("github.read",))
    g = gateway(f, read=FakeAdapter(), write=FakeAdapter())
    with pytest.raises(ToolDenied, match="tool_not_permitted"):
        await g.execute("run1", lease, "op1", "github.pr", "open", SHA)
    with pytest.raises(ToolDenied, match="action_not_permitted"):
        await g.execute("run1", lease, "op2", "github.read", "delete", SHA)
    with pytest.raises(ToolDenied, match="invalid_argument_digest"):
        await g.execute("run1", lease, "op3", "github.read", "get", "secret prompt")


@pytest.mark.asyncio
async def test_crash_uncertain_effect_is_never_retried_even_after_restart(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    crashing = FakeAdapter(fail=True)
    g = gateway(f, read=crashing)
    with pytest.raises(ToolOutcomeUnknown, match="remote_outcome_uncertain"):
        await g.execute("run1", lease, "op1", "github.read", "get", SHA)
    assert crashing.calls == 1
    assert g.get_action("op1")["state"] == "uncertain"
    restored = gateway(f, read=crashing)
    with pytest.raises(ToolConflict, match="duplicate_or_uncertain_action"):
        await restored.execute("run1", lease, "op1", "github.read", "get", SHA)
    assert crashing.calls == 1
    with pytest.raises(ToolDenied, match="owner_action_approval_required"):
        restored.reconcile("op1", "model-approved", RESULT_SHA, success=True)
    restored.reconcile("op1", "owner-action", RESULT_SHA, success=False)
    assert restored.get_action("op1")["state"] == "failed"
    assert crashing.calls == 1


@pytest.mark.asyncio
async def test_accepted_async_receipt_is_not_confused_with_completion(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    accepted = FakeAdapter(accepted=True)
    g = gateway(f, read=accepted)
    res = await g.execute("run1", lease, "op1", "github.read", "get", SHA)
    assert res.state == "accepted"
    assert g.get_action("op1")["state"] == "accepted"
    with pytest.raises(ToolConflict, match="duplicate_or_uncertain_action"):
        await g.execute("run1", lease, "op1", "github.read", "get", SHA)


@pytest.mark.asyncio
async def test_cancel_and_expired_lease_block_new_tool_effects(tmp_path):
    f, lease, clock = setup_runtime(tmp_path)
    adapter = FakeAdapter()
    g = gateway(f, read=adapter)
    clock[0] = 1061
    with pytest.raises(ToolDenied, match="lease_expired"):
        await g.execute("run1", lease, "op1", "github.read", "get", SHA)
    assert adapter.calls == 0
    f.expire_leases()
    with pytest.raises(ToolDenied, match="run_not_leased"):
        await g.execute("run1", lease, "op2", "github.read", "get", SHA)
    assert adapter.calls == 0


@pytest.mark.asyncio
async def test_cancelled_agent_blocks_tool_when_lease_still_live(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    adapter = FakeAdapter()
    g = gateway(f, read=adapter)
    f.cancel_agent("root", proof="owner-trusted")
    with pytest.raises(ToolDenied, match="agent_not_approved"):
        await g.execute("run1", lease, "op1", "github.read", "get", SHA)
    assert adapter.calls == 0


@pytest.mark.asyncio
async def test_action_count_is_bounded_and_never_refunded(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    adapter = FakeAdapter()
    g = gateway(f, read=adapter, max_calls=2)
    for i in range(2):
        await g.execute("run1", lease, f"op{i}", "github.read", "get", SHA)
    with pytest.raises(ToolDenied, match="tool_action_budget_exhausted"):
        await g.execute("run1", lease, "op3", "github.read", "get", SHA)
    assert adapter.calls == 2
    assert len(g.audit_events("run1")) == 4


def test_invalid_write_registration_cannot_disable_approval_or_sandbox(tmp_path):
    f, _, _ = setup_runtime(tmp_path)
    with pytest.raises(ValueError, match="write_tool_requires_sandbox"):
        ToolRule("github.pr", frozenset({"open"}), read_only=False)
    with pytest.raises(ValueError, match="invalid_tool_registration"):
        gateway(f, read=object())


@pytest.mark.asyncio
async def test_write_approval_is_bound_to_exact_request_id_and_digest(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    adapter = FakeAdapter()
    g = ToolGateway(
        f, {"github.pr": (
            ToolRule("github.pr", frozenset({"open"}), read_only=False,
                     sandbox_kind="github-actions"), adapter
        )},
        owner_action_verifier=(
            lambda req, rid, tool, action, digest, proof:
            req == "specific1" and rid == "run1" and digest == SHA
            and proof == "single-approved-receipt"
        ),
        sandbox_verifier=(
            lambda kind, sid, tool, proof: sid == "isolated-worktree"
            and proof == "sandbox-attested"
        ),
    )
    kw = {"approval_proof": "single-approved-receipt",
          "sandbox_id": "isolated-worktree",
          "sandbox_proof": "sandbox-attested"}
    with pytest.raises(ToolDenied, match="owner_action_approval_required"):
        await g.execute("run1", lease, "specific2", "github.pr", "open", SHA, **kw)
    assert adapter.calls == 0
    value = await g.execute("run1", lease, "specific1", "github.pr", "open", SHA, **kw)
    assert value.state == "completed"
    assert adapter.calls == 1
    with pytest.raises(ToolConflict, match="duplicate_or_uncertain_action"):
        await g.execute("run1", lease, "specific1", "github.pr", "open", SHA, **kw)


@pytest.mark.asyncio
async def test_crash_left_reserved_action_never_replays_and_can_be_reconciled(tmp_path):
    f, lease, _ = setup_runtime(tmp_path)
    adapter = FakeAdapter()
    g = gateway(f, read=adapter)
    g._reserve("run1", lease, "crash1", "github.read", "get", SHA, "", "", "")
    assert g.get_action("crash1")["state"] == "reserved"
    assert adapter.calls == 0
    with pytest.raises(ToolDenied, match="owner_action_approval_required"):
        g.reconcile("crash1", "model-owner", RESULT_SHA, success=False)
    g.reconcile("crash1", "owner-action", RESULT_SHA, success=False)
    assert g.get_action("crash1")["state"] == "failed"
    with pytest.raises(ToolConflict, match="duplicate_or_uncertain_action"):
        await g.execute("run1", lease, "crash1", "github.read", "get", SHA)
    assert adapter.calls == 0
