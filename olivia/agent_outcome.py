"""Evidence-based agent completion guard, inspired by mini-agi's critic.

Unlike model self-criticism, this costs zero extra inference tokens and accepts
only an external run receipt as evidence of a completed coding/browser job.
No generated text can authorize shell, email, payment or browser side effects.
"""
from __future__ import annotations

from typing import Any


def classify_external_run_status(remote: dict[str, Any]) -> str:
    status = str(remote.get("remote_status") or "").strip().lower()
    if status != "completed":
        return status if status in {"queued", "in_progress", "waiting", "requested"} else "unknown"

    # The provider's outcome is not a model-written "task accomplished" claim.
    # Requiring an attributable positive run ID prevents fake completion badges.
    run_id = remote.get("remote_run_id")
    valid_run_id = (isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0)
    if remote.get("remote_conclusion") == "success" and valid_run_id:
        return "succeeded"
    if remote.get("remote_conclusion") in {"failure", "cancelled", "timed_out", "action_required"}:
        return "failed"
    return "unknown"
