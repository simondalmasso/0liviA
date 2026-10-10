"""Agent Fabric PR-C2: sealed, read-only GitHub Actions status adapter tests.

No network, no real GitHub token, no model call or job dispatch in tests.
"""
from __future__ import annotations

import pytest

from olivia.harness.agents import AgentFabric
from olivia.harness.github_status import (
    GitHubStatusAdapter, PreparedStatusQuery, seal_status_query,
)
from olivia.harness.tools import ToolGateway, ToolRule, ToolOutcomeUnknown, ToolConflict

SHA = "a" * 64


class FakeWorker:
    repo = "simondalmasso/private-jobs"
    def __init__(self, response=None):
        self.status_calls = []
        self.dispatch_calls = 0
        self.response = response
    async def status(self, job_id):
        self.status_calls.append(job_id)
        return self.response
    async def dispatch(self, *args, **kwargs):
        self.dispatch_calls += 1
        raise AssertionError("Status bridge must never dispatch")


def active(tmp_path, tool):
    f = AgentFabric(
        tmp_path / "core.sqlite3",
        owner_verifier=lambda agent, digest, proof: proof == "owner",
        executor_verifier=lambda rid, proof: proof == "trusted",
        clock=lambda: 1000.0,
    )
    f.propose("researcher", "proposal1", "researcher", (tool,), 1000, 4)
    f.approve("researcher", proof="owner")
    f.create_run("researcher", "run1", "request1", SHA)
    lease = f.claim("run1", proof="trusted")
    return f, lease


@pytest.mark.asyncio
async def test_coding_status_adapter_never_dispatches_a_job(tmp_path):
    f, lease = active(tmp_path, "github.read")
    worker = FakeWorker({
        "remote_run_id": 42, "remote_status": "completed",
        "remote_conclusion": "success", "remote_head_sha": SHA,
        "remote_url": "https://github.com/example/runs/42",
    })
    q = seal_status_query("r-status", "0123456789abcdef", "coding", worker.repo)
    adapter = GitHubStatusAdapter(worker, kind="coding", prepared=[q])
    g = ToolGateway(f, {"github.read": (
        ToolRule("github.read", frozenset({"get"}), read_only=True), adapter
    )})
    reply = await g.execute("run1", lease, q.request_id, "github.read", "get", q.args_sha256)
    assert reply.state == "completed"
    assert len(reply.evidence_sha256) == 64
    assert worker.status_calls == [q.job_id]
    assert worker.dispatch_calls == 0
    assert g.get_action(q.request_id)["state"] == "completed"


@pytest.mark.asyncio
async def test_browser_pending_job_is_accepted_not_certified_completed(tmp_path):
    f, lease = active(tmp_path, "browser.read")
    worker = FakeWorker({
        "remote_run_id": 99, "remote_status": "in_progress",
        "remote_conclusion": None,
    })
    q = seal_status_query("browser-1", "0123456789abcdef", "browser", worker.repo)
    adapter = GitHubStatusAdapter(worker, kind="browser", prepared=[q])
    g = ToolGateway(f, {"browser.read": (
        ToolRule("browser.read", frozenset({"get"}), read_only=True), adapter
    )})
    reply = await g.execute("run1", lease, q.request_id, "browser.read", "get", q.args_sha256)
    assert reply.state == "accepted"
    assert worker.dispatch_calls == 0
    with pytest.raises(ToolConflict, match="duplicate_or_uncertain_action"):
        await g.execute("run1", lease, q.request_id, "browser.read", "get", q.args_sha256)


@pytest.mark.asyncio
async def test_unseen_remote_job_is_not_falsely_certified(tmp_path):
    f, lease = active(tmp_path, "github.read")
    worker = FakeWorker(None)
    q = seal_status_query("unknown1", "0123456789abcdef", "coding", worker.repo)
    adapter = GitHubStatusAdapter(worker, kind="coding", prepared=[q])
    g = ToolGateway(f, {"github.read": (
        ToolRule("github.read", frozenset({"get"}), read_only=True), adapter
    )})
    got = await g.execute("run1", lease, q.request_id, "github.read", "get", q.args_sha256)
    assert got.state == "accepted"
    assert worker.status_calls == [q.job_id]
    assert worker.dispatch_calls == 0


@pytest.mark.asyncio
async def test_digest_substitution_fails_closed_without_query(tmp_path):
    f, lease = active(tmp_path, "github.read")
    worker = FakeWorker(None)
    q = seal_status_query("status1", "0123456789abcdef", "coding", worker.repo)
    adapter = GitHubStatusAdapter(worker, kind="coding", prepared=[q])
    g = ToolGateway(f, {"github.read": (
        ToolRule("github.read", frozenset({"get"}), read_only=True), adapter
    )})
    with pytest.raises(ToolOutcomeUnknown, match="remote_outcome_uncertain"):
        await g.execute("run1", lease, q.request_id, "github.read", "get", "0"*64)
    assert worker.status_calls == []
    assert worker.dispatch_calls == 0
    assert g.get_action(q.request_id)["state"] == "uncertain"


def test_cross_repo_or_invalid_job_ids_refuse_prepared_registration():
    worker = FakeWorker(None)
    q = seal_status_query("op1", "0123456789abcdef", "coding", worker.repo)
    with pytest.raises(ValueError, match="worker_repo_mismatch"):
        GitHubStatusAdapter(FakeWorker(), kind="coding", prepared=[
            seal_status_query("op1", "0123456789abcdef", "coding", "another/repo")
        ])
    with pytest.raises(ValueError, match="invalid_job_id"):
        seal_status_query("op1", "../../unsafe", "coding", worker.repo)
    with pytest.raises(ValueError, match="invalid_worker_kind"):
        seal_status_query("op1", q.job_id, "arbitrary-shell", worker.repo)
    with pytest.raises(ValueError, match="invalid_worker_kind"):
        GitHubStatusAdapter(worker, kind="shell", prepared=[q])


@pytest.mark.asyncio
async def test_worker_malformed_result_does_not_claim_completion(tmp_path):
    f, lease = active(tmp_path, "github.read")
    worker = FakeWorker({"remote_run_id": 42, "remote_status": "completed",
                         "remote_conclusion": {"bad": "value"}})
    q = seal_status_query("op1", "0123456789abcdef", "coding", worker.repo)
    adapter = GitHubStatusAdapter(worker, kind="coding", prepared=[q])
    g = ToolGateway(f, {"github.read": (
        ToolRule("github.read", frozenset({"get"}), read_only=True), adapter
    )})
    with pytest.raises(ToolOutcomeUnknown, match="remote_outcome_uncertain"):
        await g.execute("run1", lease, "op1", "github.read", "get", q.args_sha256)
    assert g.get_action("op1")["state"] == "uncertain"
    assert worker.dispatch_calls == 0
