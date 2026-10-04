from __future__ import annotations

from pathlib import Path

import pytest

from olivia.coding import CodingJobRequest, GitHubActionsCodingWorker


def test_coding_worker_validates_fixed_repo_and_refs(monkeypatch):
    worker = GitHubActionsCodingWorker("simondalmasso/0liviA")
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
    with pytest.raises(ValueError):
        worker.validate_request(CodingJobRequest(task="x", base_ref="main", mode="unknown"))


def test_coding_worker_headers_never_include_token_name(monkeypatch):
    worker = GitHubActionsCodingWorker("simondalmasso/0liviA")
    monkeypatch.setenv("OLIVIA_GITHUB_TOKEN", "top-secret-value")
    headers = worker._headers()
    assert headers["authorization"] == "Bearer top-secret-value"
    assert "OLIVIA_GITHUB_TOKEN" not in repr(headers)


def test_coding_workflow_is_isolated_verified_and_deepseek_backed():
    workflow = Path(".github/workflows/coding-agent.yml").read_text(encoding="utf-8")
    assert 'run-name: "0liviA code ${{ inputs.olivia_job_id }}"' in workflow
    assert "deepseek-ai/deepseek-v4.1-flash" in workflow
    assert "https://integrate.api.nvidia.com/v1" in workflow
    assert "test -n \"$AIDER_OPENAI_API_KEY\"" in workflow
    assert 'BRANCH="agent/coding-${GITHUB_RUN_ID}"' in workflow
    assert "persist-credentials: false" in workflow
    assert "BASE_REF: ${{ inputs.base_ref }}" in workflow
    assert "${{ inputs.base_ref }}..." not in workflow
    assert "git check-ref-format --allow-onelevel \"$BASE_REF\"" in workflow
    assert "pytest -q" in workflow
    assert "MODE: ${{ inputs.mode }}" in workflow
    assert "--read AGENTS.md" in workflow
    assert "--read docs/ARCHITECTURE.md" in workflow
    assert "repair_pass" in workflow
    assert "MAX_AGENT_PASSES=2" in workflow
    assert 'if ! git diff --quiet || ! git diff --cached --quiet; then' in workflow
    assert 'git add -A' in workflow
    assert 'git commit -m "agent: persist verified coding result"' in workflow
    assert 'push origin "HEAD:refs/heads/$AGENT_BRANCH"' in workflow
    assert "pull-requests: write" not in workflow
