"""Sealed, read-only status access to existing GitHub coding/browser workers.

Status lookups are opt-in and require a pre-existing approved PR-B run and PR-C1
ToolGateway lease. No worker dispatch, browser navigation, model call, token
probe, result download or background polling is exposed by this adapter.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .tools import ToolReceipt


_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,79}$")
_JOB_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")
_REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_KINDS = frozenset({"coding", "browser"})
_TERMINAL = frozenset({
    "success", "failure", "cancelled", "timed_out",
    "neutral", "skipped", "action_required", "stale",
})
_KNOWN_STATUS = frozenset({
    "queued", "requested", "waiting", "pending", "in_progress", "completed",
})


def _seal(request_id: str, job_id: str, kind: str, repo: str) -> str:
    body = json.dumps(
        {"repo": repo, "job_id": job_id, "kind": kind},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PreparedStatusQuery:
    request_id: str
    job_id: str
    kind: str
    repo: str
    args_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not _ID_RE.fullmatch(self.request_id):
            raise ValueError("invalid_request_id")
        if not isinstance(self.job_id, str) or not _JOB_RE.fullmatch(self.job_id):
            raise ValueError("invalid_job_id")
        if self.kind not in _KINDS:
            raise ValueError("invalid_worker_kind")
        if not isinstance(self.repo, str) or not _REPO_RE.fullmatch(self.repo):
            raise ValueError("invalid_worker_repo")
        if (not isinstance(self.args_sha256, str)
                or not _SHA_RE.fullmatch(self.args_sha256)
                or self.args_sha256 != _seal(
                    self.request_id, self.job_id, self.kind, self.repo
                )):
            raise ValueError("invalid_prepared_digest")


def seal_status_query(
    request_id: str, job_id: str, kind: str, repo: str,
) -> PreparedStatusQuery:
    # Constructor performs all validation before any prepared query can exist.
    return PreparedStatusQuery(
        request_id=request_id, job_id=job_id, kind=kind, repo=repo,
        args_sha256=_seal(request_id, job_id, kind, repo),
    )


class GitHubStatusAdapter:
    """One exact authenticated worker's read-only status() method.

    An authorized Core control-plane must seal each query and register it in
    the adapter BEFORE the gateway executes it. Callers cannot replace worker,
    kind, repo or job ID by passing an arbitrary hash from a prompt.
    """

    def __init__(
        self, worker: Any, *, kind: str,
        prepared: Iterable[PreparedStatusQuery] = (),
    ) -> None:
        if kind not in _KINDS:
            raise ValueError("invalid_worker_kind")
        repo = getattr(worker, "repo", None)
        if not isinstance(repo, str) or not _REPO_RE.fullmatch(repo):
            raise ValueError("invalid_worker_repo")
        if not inspect.iscoroutinefunction(getattr(worker, "status", None)):
            raise ValueError("missing_readonly_status_method")
        self._worker = worker
        self._kind = kind
        self._queries: dict[str, PreparedStatusQuery] = {}
        for query in prepared:
            if not isinstance(query, PreparedStatusQuery):
                raise ValueError("invalid_prepared_query")
            if query.kind != kind or query.repo != repo:
                raise ValueError("worker_repo_mismatch")
            if query.request_id in self._queries:
                raise ValueError("duplicate_prepared_query")
            self._queries[query.request_id] = query

    async def invoke(
        self, *, action: str, request_id: str,
        args_sha256: str, sandbox_id: str,
    ) -> ToolReceipt:
        if action != "get" or sandbox_id:
            raise ValueError("status_is_read_only")
        query = self._queries.get(request_id)
        if query is None or query.args_sha256 != args_sha256:
            raise ValueError("unsealed_or_mismatched_status_query")
        # Explicitly call only .status(); NEVER .dispatch() or .result().
        item = await self._worker.status(query.job_id)
        if item is None:
            snapshot: dict[str, Any] = {
                "observed": False, "kind": self._kind, "job_id": query.job_id,
            }
            final = False
        else:
            if not isinstance(item, dict):
                raise ValueError("invalid_worker_status")
            run_id = item.get("remote_run_id")
            status = item.get("remote_status")
            conclusion = item.get("remote_conclusion")
            head = item.get("remote_head_sha")
            if (type(run_id) is not int or run_id <= 0
                    or status not in _KNOWN_STATUS
                    or conclusion is not None and (
                        not isinstance(conclusion, str)
                        or conclusion not in _TERMINAL
                    )
                    or head is not None and (
                        not isinstance(head, str)
                        or len(head) not in (40, 64)
                        or not all(ch in "0123456789abcdef" for ch in head)
                    )):
                raise ValueError("invalid_worker_status")
            final = status == "completed" and conclusion in _TERMINAL
            snapshot = {
                "observed": True, "kind": self._kind,
                "job_id": query.job_id, "remote_run_id": run_id,
                "remote_status": status, "remote_conclusion": conclusion,
                "remote_head_sha": head,
            }
        digest = hashlib.sha256(
            json.dumps(
                snapshot, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return ToolReceipt(
            state="completed" if final else "accepted",
            evidence_sha256=digest,
        )
