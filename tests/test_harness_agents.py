"""Agent Fabric PR-B: local-only SQLite lifecycle tests; NO tool or LLM calls."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from olivia.harness.agents import AgentFabric, AgentDenied, AgentConflict


SHA = "a" * 64


def fabric(path: Path, *, owner=True, executor=True, now=None) -> AgentFabric:
    return AgentFabric(
        path,
        owner_verifier=(lambda aid, digest, proof: proof == "owner-approved") if owner else None,
        executor_verifier=(lambda run_id, proof: proof == "trusted-worker") if executor else None,
        clock=(lambda: now) if now is not None else None,
    )


def root(store: AgentFabric):
    return store.propose(
        agent_id="lead", proposal_key="plan-1", role="planner",
        allowed_tools=("github.read", "github.pr", "browser.read"),
        max_tokens=4000, max_calls=4,
    )


def approve_root(store: AgentFabric):
    root(store)
    store.approve("lead", proof="owner-approved")


def test_new_agents_always_start_draft_and_have_no_budget_scope(tmp_path):
    db = tmp_path / "fabric.sqlite3"
    f = fabric(db)
    a = root(f)
    assert a["state"] == "draft"
    assert not a["approved"]
    with pytest.raises(AgentDenied, match="not_approved"):
        f.create_run(agent_id="lead", run_id="run0", request_key="task0", input_sha256=SHA)
    with sqlite3.connect(db) as conn:
        assert not conn.execute(
            "SELECT 1 FROM fabric_scopes WHERE scope_id='agent:lead'"
        ).fetchone()


def test_approval_is_trusted_external_owner_action_and_not_model_proposal(tmp_path):
    f = fabric(tmp_path / "agents.sqlite3", owner=False)
    root(f)
    with pytest.raises(AgentDenied, match="owner_authorization_required"):
        f.approve("lead", proof="owner-approved")
    assert f.get_agent("lead")["state"] == "draft"
    f = fabric(tmp_path / "agents.sqlite3")
    with pytest.raises(AgentDenied, match="owner_authorization_required"):
        f.approve("lead", proof="model-claims-owner")
    f.approve("lead", proof="owner-approved")
    assert f.get_agent("lead")["state"] == "approved"
    with sqlite3.connect(tmp_path / "agents.sqlite3") as conn:
        assert conn.execute(
            "SELECT max_tokens,max_calls FROM fabric_scopes WHERE scope_id='agent:lead'"
        ).fetchone() == (4000, 4)
    with pytest.raises(AgentConflict, match="already_approved"):
        f.approve("lead", proof="owner-approved")


def test_child_permissions_are_strict_subset_and_children_require_own_approval(tmp_path):
    f = fabric(tmp_path / "agents.sqlite3")
    approve_root(f)
    with pytest.raises(AgentDenied, match="permissions_exceed_parent"):
        f.propose("unsafe", "plan-bad", "worker", ("github.delete",), 100, 1,
                  parent_id="lead")
    with pytest.raises(AgentDenied, match="budget_exceeds_parent"):
        f.propose("unsafe", "plan-large", "worker", ("github.read",), 5000, 1,
                  parent_id="lead")
    child = f.propose("reviewer", "plan-review", "auditor", ("github.read",), 800, 2,
                      parent_id="lead")
    assert child["state"] == "draft"
    with pytest.raises(AgentDenied, match="not_approved"):
        f.create_run("reviewer", "r1", "request1", SHA)
    f.approve("reviewer", proof="owner-approved")
    with sqlite3.connect(tmp_path / "agents.sqlite3") as conn:
        assert conn.execute(
            "SELECT parent_scope_id FROM fabric_scopes WHERE scope_id='agent:reviewer'"
        ).fetchone()[0] == "agent:lead"


def test_idempotent_proposal_and_run_key_block_mutated_or_duplicate_work(tmp_path):
    f = fabric(tmp_path / "agents.sqlite3")
    original = root(f)
    assert root(f) == original
    with pytest.raises(AgentConflict, match="proposal_conflict"):
        f.propose("lead", "plan-1", "planner", ("github.read",), 100, 2)
    with pytest.raises(AgentConflict, match="proposal_conflict"):
        f.propose("other", "plan-1", "planner", (), 100, 1)
    f.approve("lead", proof="owner-approved")
    submitted = f.create_run("lead", "r1", "work-key", SHA)
    assert submitted["state"] == "queued"
    assert f.create_run("lead", "r1", "work-key", SHA) == submitted
    with pytest.raises(AgentConflict, match="request_conflict"):
        f.create_run("lead", "r2", "work-key", SHA)
    with pytest.raises(AgentConflict, match="request_conflict"):
        f.create_run("lead", "r1", "different", SHA)


def test_claim_requires_trusted_executor_and_lease_cannot_be_replayed(tmp_path):
    p = tmp_path / "agents.sqlite3"
    f = fabric(p)
    approve_root(f)
    f.create_run("lead", "r1", "task1", SHA)
    no_executor = fabric(p, executor=False)
    with pytest.raises(AgentDenied, match="executor_authorization_required"):
        no_executor.claim("r1", proof="trusted-worker")
    with pytest.raises(AgentDenied, match="executor_authorization_required"):
        f.claim("r1", proof="model-proposed")
    token = f.claim("r1", proof="trusted-worker", lease_seconds=45)
    assert len(token) >= 32
    assert f.get_run("r1")["state"] == "leased"
    with pytest.raises(AgentConflict, match="already_claimed"):
        f.claim("r1", proof="trusted-worker")
    with pytest.raises(AgentDenied, match="lease_token_invalid"):
        f.checkpoint("r1", "bad-token", seq=1, payload={"step": "checked"})
    f.checkpoint("r1", token, seq=1, payload={"step": "checked"})
    assert f.get_run("r1")["checkpoint_seq"] == 1
    with pytest.raises(AgentConflict, match="stale_checkpoint"):
        f.checkpoint("r1", token, seq=1, payload={"step": "replay"})
    f.finish("r1", token, result_sha256="b"*64)
    assert f.get_run("r1")["state"] == "completed"
    with pytest.raises(AgentConflict, match="not_leased"):
        f.finish("r1", token, result_sha256="b"*64)


def test_expired_lease_becomes_uncertain_and_requires_external_owner_reconciliation(tmp_path):
    p = tmp_path / "agents.sqlite3"
    clock = [1000.0]
    f = AgentFabric(p,
        owner_verifier=lambda _a,_d,proof: proof == "owner-approved",
        executor_verifier=lambda _r,proof: proof == "trusted-worker",
        clock=lambda: clock[0])
    approve_root(f)
    f.create_run("lead", "r1", "task1", SHA)
    token = f.claim("r1", proof="trusted-worker", lease_seconds=20)
    clock[0] += 21
    assert f.expire_leases() == 1
    assert f.get_run("r1")["state"] == "uncertain"
    with pytest.raises(AgentConflict, match="not_queued"):
        f.claim("r1", proof="trusted-worker")
    with pytest.raises(AgentConflict, match="not_leased"):
        f.finish("r1", token, result_sha256="b"*64)
    with pytest.raises(AgentDenied, match="owner_authorization_required"):
        f.reconcile("r1", proof="worker-not-owner", result_sha256="b"*64,
                    success=True)
    f.reconcile("r1", proof="owner-approved", result_sha256="b"*64, success=False)
    assert f.get_run("r1")["state"] == "failed"
    assert f.get_run("r1")["result_sha256"] == "b"*64


def test_revocation_recursively_blocks_children_and_preserves_unconfirmed_running(tmp_path):
    f = fabric(tmp_path / "agents.sqlite3")
    approve_root(f)
    f.propose("child", "pchild", "worker", ("github.read",), 200, 1, parent_id="lead")
    f.approve("child", proof="owner-approved")
    f.create_run("lead", "run-a", "work-a", SHA)
    f.create_run("child", "run-b", "work-b", SHA)
    lease = f.claim("run-b", proof="trusted-worker")
    with pytest.raises(AgentDenied, match="owner_authorization_required"):
        f.cancel_agent("lead", proof="unverified")
    f.cancel_agent("lead", proof="owner-approved")
    assert f.get_agent("lead")["state"] == "revoked"
    assert f.get_agent("child")["state"] == "revoked"
    assert f.get_run("run-a")["state"] == "cancelled"
    assert f.get_run("run-b")["state"] == "leased"
    assert f.get_run("run-b")["cancel_requested"]
    with pytest.raises(AgentDenied, match="cancellation_pending"):
        f.finish("run-b", lease, result_sha256="b"*64)
    f.ack_cancel("run-b", lease)
    assert f.get_run("run-b")["state"] == "cancelled"
    with pytest.raises(AgentDenied, match="not_approved"):
        f.create_run("child", "run-c", "work-c", SHA)


def test_durable_restart_preserves_receipts_events_and_does_not_auto_execute(tmp_path):
    p = tmp_path / "agents.sqlite3"
    f = fabric(p)
    approve_root(f)
    f.create_run("lead", "r1", "task1", SHA)
    f2 = fabric(p)
    assert f2.get_run("r1")["state"] == "queued"
    assert [x["kind"] for x in f2.audit_events("r1")] == ["run.queued"]
    assert f2.get_agent("lead")["approved"]
    assert not hasattr(f2, "run_tools")
    assert not hasattr(f2, "dispatch")
    assert not hasattr(f2, "call_model")


def test_invalid_names_payload_and_proof_are_denied(tmp_path):
    f = fabric(tmp_path / "agents.sqlite3")
    with pytest.raises(AgentDenied, match="invalid_identifier"):
        f.propose("../../secrets", "key", "planner", (), 100, 1)
    with pytest.raises(AgentDenied, match="invalid_tool"):
        f.propose("root", "key", "planner", ("*",), 100, 1)
    with pytest.raises(AgentDenied, match="invalid_budget"):
        f.propose("root", "key", "planner", (), True, 1)
    approve_root(f)
    with pytest.raises(AgentDenied, match="invalid_input_digest"):
        f.create_run("lead", "r1", "task1", "raw prompt")
    f.create_run("lead", "r1", "task1", SHA)
    lease = f.claim("r1", proof="trusted-worker")
    with pytest.raises(AgentDenied, match="invalid_checkpoint"):
        f.checkpoint("r1", lease, seq=1, payload={"large": "x"*40000})
    assert f.get_run("r1")["checkpoint_seq"] == 0


def test_child_cannot_be_drafted_under_unapproved_parent(tmp_path):
    f = fabric(tmp_path / "agents.sqlite3")
    root(f)
    with pytest.raises(AgentDenied, match="parent_not_approved"):
        f.propose("child", "child1", "coder", ("github.read",), 100, 1,
                  parent_id="lead")


def test_sibling_agents_share_parent_dispatch_call_budget_without_refunds(tmp_path):
    p = tmp_path / "calls.sqlite3"
    f = fabric(p)
    f.propose("root", "root-1", "planner", ("github.read",), 500, 2)
    f.approve("root", proof="owner-approved")
    for aid in ("alpha", "beta"):
        f.propose(aid, "proposal-"+aid, "auditor", ("github.read",), 300, 2,
                  parent_id="root")
        f.approve(aid, proof="owner-approved")
    f.create_run("alpha", "job-a", "call-a", SHA)
    f.create_run("beta", "job-b", "call-b", SHA)
    assert f.get_agent("root")["reserved_runs"] == 2
    assert f.get_agent("alpha")["reserved_runs"] == 1
    assert f.get_agent("beta")["reserved_runs"] == 1
    with pytest.raises(AgentDenied, match="run_budget_exhausted"):
        f.create_run("alpha", "job-c", "call-c", SHA)
    assert f.get_agent("root")["reserved_runs"] == 2
    assert f.create_run("alpha", "job-a", "call-a", SHA)["run_id"] == "job-a"
    f.cancel_agent("alpha", proof="owner-approved")
    with pytest.raises(AgentDenied, match="run_budget_exhausted"):
        f.create_run("beta", "job-d", "call-d", SHA)
    assert fabric(p).get_agent("root")["reserved_runs"] == 2


def test_checkpoint_is_durable_but_owner_only_to_read(tmp_path):
    p = tmp_path / "checkpoint.sqlite3"
    f = fabric(p)
    approve_root(f)
    f.create_run("lead", "r1", "task1", SHA)
    token = f.claim("r1", proof="trusted-worker")
    f.checkpoint("r1", token, seq=1, payload={"step": "review", "artifact_hash": "0"*64})
    reload_without_auth = fabric(p, owner=False)
    with pytest.raises(AgentDenied, match="owner_authorization_required"):
        reload_without_auth.inspect_checkpoint("r1", proof="owner-approved")
    with pytest.raises(AgentDenied, match="owner_authorization_required"):
        fabric(p).inspect_checkpoint("r1", proof="model-owner")
    value = fabric(p).inspect_checkpoint("r1", proof="owner-approved")
    assert value == {"seq": 1, "checkpoint": {
        "step": "review", "artifact_hash": "0"*64
    }}


def test_expired_lease_cannot_finish_even_during_reconciliation_race(tmp_path):
    p = tmp_path / "deadline.sqlite3"
    times = [100.0]
    store = AgentFabric(p,
        owner_verifier=lambda _a,_h,proof: proof == "owner-approved",
        executor_verifier=lambda _r,proof: proof == "trusted-worker",
        clock=lambda: times[0])
    approve_root(store)
    store.create_run("lead", "race", "race-1", SHA)
    token = store.claim("race", proof="trusted-worker", lease_seconds=2)
    # A lease can expire after explicit expire_leases() but before the
    # optimistic CAS; _get_lease must independently reject it.
    original = store.expire_leases
    def expires_during_race():
        original()
        times[0] = 103.0
        return 0
    store.expire_leases = expires_during_race
    with pytest.raises(AgentConflict, match="lease_expired"):
        store.finish("race", token, result_sha256="b"*64)
    assert store.get_run("race")["state"] != "completed"


def test_fabric_database_file_is_private(tmp_path):
    import os
    p = tmp_path / "agent-private.sqlite3"
    fabric(p)
    if os.name == "posix":
        assert (p.stat().st_mode & 0o077) == 0
