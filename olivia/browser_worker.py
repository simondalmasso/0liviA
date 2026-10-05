from __future__ import annotations

import io
import json
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import aiohttp

from .web import WebReadError, validate_public_url


_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REF = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
_SENSITIVE_QUERY_KEYS = frozenset({
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "code",
    "credential",
    "key",
    "password",
    "secret",
    "session",
    "sessionid",
    "sig",
    "signature",
    "token",
})


class BrowserWorkerError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserJobRequest:
    url: str
    objective: str
    base_ref: str


class GitHubActionsBrowserWorker:
    """Dispatches bounded JS-browser jobs to a public GitHub Actions runner."""

    def __init__(
        self,
        repo: str,
        *,
        workflow: str = "browser-agent.yml",
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
            raise BrowserWorkerError(f"missing {self.token_env}")
        return {
            "authorization": f"Bearer {token}",
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
            "content-type": "application/json",
            "user-agent": "0liviA-browser-worker/0.1",
        }

    @staticmethod
    def validate_request(request: BrowserJobRequest) -> None:
        try:
            normalized = validate_public_url(request.url)
        except WebReadError as exc:
            raise ValueError(f"invalid browser URL: {exc}") from exc
        query_keys = {
            key.strip().lower()
            for key, _ in parse_qsl(urlsplit(normalized).query, keep_blank_values=True)
        }
        if query_keys & _SENSITIVE_QUERY_KEYS:
            raise ValueError("browser URL contains a sensitive query parameter")
        if len(request.objective) > 4_000:
            raise ValueError("objective must be at most 4000 characters")
        if (
            not _REF.fullmatch(request.base_ref)
            or ".." in request.base_ref
            or request.base_ref.startswith("/")
            or request.base_ref.endswith("/")
        ):
            raise ValueError("invalid base_ref")

    async def dispatch(self, job_id: str, request: BrowserJobRequest) -> dict[str, Any]:
        self.validate_request(request)
        normalized_url = validate_public_url(request.url)
        url = (
            f"{self.api_base}/repos/{self.repo}/actions/workflows/"
            f"{self.workflow}/dispatches"
        )
        payload = {
            "ref": request.base_ref,
            "inputs": {
                "olivia_job_id": job_id,
                "url": normalized_url,
                "base_ref": request.base_ref,
            },
        }
        timeout = aiohttp.ClientTimeout(total=20)
        async with self._session_factory(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=self._headers()) as response:
                if response.status != 204:
                    detail = (await response.text())[:500]
                    raise BrowserWorkerError(
                        f"github browser dispatch HTTP {response.status}: {detail}"
                    )
        return {
            "repo": self.repo,
            "workflow": self.workflow,
            "remote_status": "dispatched",
        }

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
                    raise BrowserWorkerError(
                        f"github browser status HTTP {response.status}: {detail}"
                    )
                body = await response.json()

        needle = f"0liviA browse {job_id}"
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

    async def result(self, run_id: int | str) -> dict[str, Any] | None:
        try:
            numeric_run_id = int(run_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("run_id must be an integer") from exc
        if numeric_run_id <= 0:
            raise ValueError("run_id must be positive")

        headers = self._headers()
        timeout = aiohttp.ClientTimeout(total=25)
        list_url = (
            f"{self.api_base}/repos/{self.repo}/actions/runs/"
            f"{numeric_run_id}/artifacts"
        )
        async with self._session_factory(timeout=timeout) as session:
            async with session.get(list_url, headers=headers) as response:
                if response.status != 200:
                    detail = (await response.text())[:500]
                    raise BrowserWorkerError(
                        f"github browser artifacts HTTP {response.status}: {detail}"
                    )
                body = await response.json()

            artifact_id = None
            for artifact in body.get("artifacts", []):
                if (
                    artifact.get("name") == "browser-result"
                    and not artifact.get("expired")
                ):
                    artifact_id = artifact.get("id")
                    break
            if not artifact_id:
                return None

            download_url = (
                f"{self.api_base}/repos/{self.repo}/actions/artifacts/"
                f"{artifact_id}/zip"
            )
            async with session.get(download_url, headers=headers) as response:
                if response.status != 200:
                    detail = (await response.text())[:500]
                    raise BrowserWorkerError(
                        f"github browser artifact download HTTP {response.status}: {detail}"
                    )
                raw = await response.read()

        if len(raw) > 2 * 1024 * 1024:
            raise BrowserWorkerError("browser artifact too large")
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                info = archive.getinfo("browser-result.json")
                if info.file_size > 512 * 1024:
                    raise BrowserWorkerError("browser result too large")
                payload = json.loads(archive.read(info).decode("utf-8"))
        except (KeyError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BrowserWorkerError("invalid browser artifact") from exc
        if not isinstance(payload, dict):
            raise BrowserWorkerError("invalid browser result")
        return payload


def browser_worker_from_env() -> GitHubActionsBrowserWorker | None:
    enabled = os.getenv("OLIVIA_BROWSER_WORKER_ENABLED", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return None
    repo = os.getenv("OLIVIA_BROWSER_REPO", "").strip()
    if not repo:
        raise BrowserWorkerError(
            "OLIVIA_BROWSER_REPO is required when browser worker is enabled"
        )
    workflow = os.getenv("OLIVIA_BROWSER_WORKFLOW", "browser-agent.yml").strip()
    return GitHubActionsBrowserWorker(repo, workflow=workflow)
