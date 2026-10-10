"""Minimal bounded single-model execution contract for Agent Fabric PR-A.

This deliberately does not call the canonical router directly: PR-C will
bridge the verified admission and reservation path into its 2-attempt pool.
No background calls, probing, or fallback.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .budget import BudgetDenied, BudgetGuard
from .model_registry import ModelRegistry, ParentBudget


class DeniedModelInvocation(RuntimeError):
    pass


async def guarded_stream(
    *,
    registry: ModelRegistry,
    budget: BudgetGuard,
    provider: Any,
    messages: list[dict[str, str]],
    capability: str,
    input_tokens: int,
    output_tokens: int,
    scope_id: str,
    request_id: str,
    parent_budget: ParentBudget | None = None,
) -> AsyncIterator[str]:
    spec = getattr(provider, "spec", None)
    if spec is None:
        raise DeniedModelInvocation("provider_spec_required")
    admission = registry.admit(
        spec.name, capability, input_tokens, output_tokens, parent_budget
    )
    if not admission.allowed or admission.model != spec.model:
        raise DeniedModelInvocation(admission.reason if not admission.allowed else "identity_mismatch")
    try:
        budget.reserve(admission, request_id=request_id, scope_id=scope_id)
    except BudgetDenied as exc:
        raise DeniedModelInvocation(str(exc)) from exc
    try:
        async for chunk in provider.stream(messages):
            yield chunk
    except BaseException:
        budget.settle(request_id, uncertain=True)
        raise
    else:
        budget.settle(request_id, uncertain=False)
