from __future__ import annotations

import base64
from pathlib import Path

import pytest

from olivia.coding import CodingJobRequest, GitHubActionsCodingWorker


def test_coding_worker_validates_fixed_repo_and_refs(monkeypatch):
    worker = GitHubActionsCodingWorker("owner/example-repo")
    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "secret")
    assert worker.configured is True

    worker.validate_request(
        CodingJobRequest(
            task="Fix the failing tests.",
            base_ref="arch/gpt-synthesis-v1",
            mode="repair",
            publish_branch=False,
        )
    )
    with pytest.raises(ValueError):
        worker.validate_request(CodingJobRequest(task="", base_ref="main"))
    with pytest.raises(ValueError):
        worker.validate_request(CodingJobRequest(task="x", base_ref="../main"))
    worker.validate_request(CodingJobRequest(task="review", base_ref="main", mode="review"))
    with pytest.raises(ValueError):
        worker.validate_request(CodingJobRequest(task="x", base_ref="main", mode="unknown"))


def test_coding_worker_headers_never_include_token_name(monkeypatch):
    worker = GitHubActionsCodingWorker("owner/example-repo")
    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "top-secret-value")
    headers = worker._headers()
    assert headers["authorization"] == "Bearer top-secret-value"
    assert "OLIVIA_GITHUB_TOKEN" not in repr(headers)


def test_coding_workflow_is_isolated_verified_and_deepseek_backed():
    workflow = Path(".github/workflows/coding-agent.yml").read_text(encoding="utf-8")
    assert 'run-name: "0liviA code ${{ inputs.olivia_job_id }}"' in workflow
    assert "deepseek-ai/deepseek-v4.1-flash" in workflow
    assert "OLIVIA_CODING_API_BASE" in workflow
    assert "OLIVIA_CODING_MODEL" in workflow
    assert "OLIVIA_CODING_API_KEY" in workflow
    assert "OLIVIA_CODING_ZERO_COST_VERIFIED" in workflow
    assert 'test "$ZERO_COST_VERIFIED" = "true"' in workflow
    assert "test -n \"$AIDER_OPENAI_API_KEY\"" in workflow
    assert 'BRANCH="agent/coding-${GITHUB_RUN_ID}"' in workflow
    assert "persist-credentials: false" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "publish:\n    needs: code" in workflow
    assert "contents: write" in workflow
    assert "agent-series.patch" in workflow
    assert "BASE_REF: ${{ inputs.base_ref }}" in workflow
    assert "${{ inputs.base_ref }}..." not in workflow
    assert "git check-ref-format --branch \"$BASE_REF\"" in workflow
    assert "pytest -q" in workflow
    assert "MODE: ${{ inputs.mode }}" in workflow
    assert "--read AGENTS.md" in workflow
    assert "--read docs/ARCHITECTURE.md" in workflow
    assert "repair_pass" in workflow
    assert 'MAX_AGENT_PASSES: "2"' in workflow
    assert '- review' in workflow
    assert 'AGENT_REVIEW.md' in workflow
    assert "review mode modified forbidden path" in workflow
    assert "inputs.mode != 'review'" in workflow
    assert 'if ! git diff --quiet || ! git diff --cached --quiet; then' in workflow
    assert 'git add -A' in workflow
    assert 'git commit -m "agent: persist verified coding result"' in workflow
    assert 'push origin "HEAD:refs/heads/$BRANCH"' in workflow
    assert "pull-requests: write" not in workflow


@pytest.mark.asyncio
async def test_coding_worker_fetches_review_report_from_isolated_run_branch(monkeypatch):
    calls = []

    class FakeResponse:
        status = 200

        async def json(self):
            raw = b"# Senior review\n\nP1: bounded finding."
            return {
                "encoding": "base64",
                "content": base64.b64encode(raw).decode("ascii"),
                "size": len(raw),
            }

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class FakeSession:
        def get(self, url, *, params, headers):
            calls.append((url, params, headers))
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "test-token")
    worker = GitHubActionsCodingWorker(
        "owner/example-repo",
        session_factory=lambda **_: FakeSession(),
    )
    report = await worker.review_report(123)

    assert report == "# Senior review\n\nP1: bounded finding."
    assert len(calls) == 1
    url, params, headers = calls[0]
    assert url.endswith("/contents/AGENT_REVIEW.md")
    assert params == {"ref": "agent/coding-123"}
    assert headers["authorization"] == "Bearer test-token"
