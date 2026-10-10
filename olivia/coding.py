from __future__ import annotations

import asyncio
import base64
import os
import re
from dataclasses import dataclass
from typing import Any

import aiohttp


_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REF = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


class CodingWorkerError(RuntimeError):
    pass


class CodingDispatchUncertainError(CodingWorkerError):
    """Transport failed after dispatch may already have reached GitHub."""


@dataclass(frozen=True)
class CodingJobRequest:
    task: str
    base_ref: str
    mode: str = "implement"
    publish_branch: bool = False


class GitHubActionsCodingWorker:
    """Dispatches isolated coding jobs to one preconfigured GitHub repository."""

    def __init__(
        self,
        repo: str,
        *,
        workflow: str = "coding-agent.yml",
        token_env: str = "OLIVIA_GITHUB_TOKEN",
        api_base: str = "https://api.github.com",
        session_factory=aiohttp.ClientSession,
    ):
        repo = repo.strip()
        workflow = workflow.strip()
        if not _REPO.fullmatch(repo):
            raise ValueError("repo must be owner/name")
        if not workflow or "/" in workflow or "\\" in workflow:
            raise ValueError("workflow must be a workflow filename")
        self.repo = repo
        self.workflow = workflow
        self.token_env = token_env
        self.api_base = api_base.rstrip("/")
        self._session_factory = session_factory

    @property
    def configured(self) -> bool:
        return bool(os.getenv(self.token_env))

    def _headers(self) -> dict[str, str]:
        token = os.getenv(self.token_env, "")
        if not token:
            raise CodingWorkerError(f"missing {self.token_env}")
        return {
            "authorization": f"Bearer {token}",
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
            "content-type": "application/json",
            "user-agent": "0liviA-coding-worker/0.1",
        }

    @staticmethod
    def validate_request(request: CodingJobRequest) -> None:
        if not request.task.strip() or len(request.task) > 12_000:
            raise ValueError("task must be 1..12000 characters")
        if request.mode not in {"implement", "repair", "review"}:
            raise ValueError("mode must be implement, repair, or review")
        if (
            not _REF.fullmatch(request.base_ref)
            or ".." in request.base_ref
            or request.base_ref.startswith("/")
            or request.base_ref.endswith("/")
        ):
            raise ValueError("invalid base_ref")

    async def dispatch(self, job_id: str, request: CodingJobRequest) -> dict[str, Any]:
        self.validate_request(request)
        url = (
            f"{self.api_base}/repos/{self.repo}/actions/workflows/"
            f"{self.workflow}/dispatches"
        )
        payload = {
            "ref": request.base_ref,
            "inputs": {
                "olivia_job_id": job_id,
                "task": request.task,
                "base_ref": request.base_ref,
                "mode": request.mode,
                "publish_branch": "true" if request.publish_branch else "false",
            },
        }
        timeout = aiohttp.ClientTimeout(total=20)
        # The POST and the session teardown are both part of the dispatch boundary.
        try:
            async with self._session_factory(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=self._headers()) as response:
                    # A 5xx cannot prove that the remote side effect was rejected.
                    if response.status >= 500:
                        raise CodingDispatchUncertainError(
                            f"github dispatch HTTP {response.status}: outcome uncertain"
                        )
                    if response.status != 204:
                        detail = (await response.text())[:500]
                        raise CodingWorkerError(
                            f"github dispatch HTTP {response.status}: {detail}"
                        )
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            raise CodingDispatchUncertainError(
                "github dispatch transport outcome uncertain"
            ) from exc
        return {
            "repo": self.repo,
            "workflow": self.workflow,
            "remote_status": "dispatched",
        }

    async def review_report(self, run_id: int | str) -> str | None:
        try:
            numeric_run_id = int(run_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("run_id must be an integer") from exc
        if numeric_run_id <= 0:
            raise ValueError("run_id must be positive")

        branch = f"agent/coding-{numeric_run_id}"
        url = f"{self.api_base}/repos/{self.repo}/contents/AGENT_REVIEW.md"
        timeout = aiohttp.ClientTimeout(total=20)
        async with self._session_factory(timeout=timeout) as session:
            async with session.get(
                url,
                params={"ref": branch},
                headers=self._headers(),
            ) as response:
                if response.status == 404:
                    return None
                if response.status != 200:
                    raise CodingWorkerError(
                        f"github review report HTTP {response.status}"
                    )
                body = await response.json()

        if str(body.get("encoding") or "").lower() != "base64":
            raise CodingWorkerError("github review report encoding is not base64")
        try:
            raw = base64.b64decode(
                str(body.get("content") or "").encode("ascii"),
                validate=False,
            )
        except (ValueError, UnicodeEncodeError) as exc:
            raise CodingWorkerError("github review report is invalid base64") from exc
        if len(raw) > 128 * 1024:
            raise CodingWorkerError("github review report is too large")
        return raw.decode("utf-8", errors="replace")[:40_000]

    async def status(self, job_id: str) -> dict[str, Any] | None:
        url = (
            f"{self.api_base}/repos/{self.repo}/actions/workflows/"
            f"{self.workflow}/runs?event=workflow_dispatch&per_page=30"
        )
        timeout = aiohttp.ClientTimeout(total=20)
        async with self._session_factory(timeout=timeout) as session:
            async with session.get(url, headers=self._headers()) as response:
                if response.status != 200:
                    detail = (await response.text())[:500]
                    raise CodingWorkerError(
                        f"github status HTTP {response.status}: {detail}"
                    )
                body = await response.json()

        needle = f"0liviA code {job_id}"
        for run in body.get("workflow_runs", []):
            if str(run.get("display_title") or "") != needle:
                continue
            return {
                "remote_run_id": run.get("id"),
                "remote_status": run.get("status"),
                "remote_conclusion": run.get("conclusion"),
                "remote_url": run.get("html_url"),
                "remote_head_sha": run.get("head_sha"),
            }
        return None


def coding_worker_from_env() -> GitHubActionsCodingWorker | None:
    enabled = os.getenv("OLIVIA_CODING_WORKER_ENABLED", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return None
    repo = os.getenv("OLIVIA_CODING_REPO", "").strip()
    if not repo:
        raise CodingWorkerError("OLIVIA_CODING_REPO is required when coding worker is enabled")
    workflow = os.getenv("OLIVIA_CODING_WORKFLOW", "coding-agent.yml").strip()
    return GitHubActionsCodingWorker(repo, workflow=workflow)
