"""Fail-closed single-provider bounded adapter contract for Agent Fabric PR-A.

This has no live cloud adapter and MUST NOT be wired into canonical chat yet.
An adapter must send the exact sealed JSON bytes it prepared, and demonstrate
that its API's selected cap limits all output tokens including reasoning.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from .budget import BudgetDenied, BudgetGuard
from .model_registry import ModelRegistry, ParentBudget


class DeniedModelInvocation(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundedRequest:
    model: str
    body_json: str
    endpoint_kind: str
    output_cap_parameter: str
    max_output_tokens: int


def _verify_prepared_request(
    prepared: BoundedRequest,
    *,
    exact_model: str,
    messages: list[dict[str, str]],
    max_input_tokens: int,
    max_output_tokens: int,
) -> None:
    if not isinstance(prepared, BoundedRequest):
        raise DeniedModelInvocation("bounded_adapter_contract_missing")
    valid_caps = {
        "chat_completions": {"max_tokens", "max_completion_tokens"},
        "responses": {"max_output_tokens"},
    }
    if (prepared.endpoint_kind not in valid_caps
            or prepared.output_cap_parameter not in valid_caps[prepared.endpoint_kind]):
        raise DeniedModelInvocation("unsupported_output_cap")
    if prepared.model != exact_model or prepared.max_output_tokens != max_output_tokens:
        raise DeniedModelInvocation("prepared_model_or_output_mismatch")
    if not isinstance(prepared.body_json, str):
        raise DeniedModelInvocation("invalid_prepared_body")
    size = len(prepared.body_json.encode("utf-8"))
    # One serialized UTF-8 byte per token is deliberately conservative.
    # Includes tools, reasoning configuration, system messages and metadata.
    if size > max_input_tokens or size > 250_000:
        raise DeniedModelInvocation("serialized_input_exceeds_token_reservation")
    try:
        payload = json.loads(prepared.body_json)
    except (ValueError, TypeError) as exc:
        raise DeniedModelInvocation("invalid_prepared_json") from exc
    if not isinstance(payload, dict) or payload.get("model") != exact_model:
        raise DeniedModelInvocation("prepared_body_model_mismatch")
    if prepared.endpoint_kind == "chat_completions":
        if payload.get("messages") != messages:
            raise DeniedModelInvocation("prepared_messages_mismatch")
    else:
        if payload.get("input") != messages:
            raise DeniedModelInvocation("prepared_messages_mismatch")
    active = prepared.output_cap_parameter
    if (type(payload.get(active)) is not int
            or payload[active] != max_output_tokens
            or any(other in payload for other in
                   {"max_tokens", "max_completion_tokens", "max_output_tokens"} - {active})
            or type(payload.get("n", 1)) is not int or payload.get("n", 1) != 1
            or type(payload.get("best_of", 1)) is not int or payload.get("best_of", 1) != 1):
        raise DeniedModelInvocation("output_cap_not_enforced")


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
        raise DeniedModelInvocation(
            admission.reason if not admission.allowed else "identity_mismatch"
        )
    # Existing adapters only expose .stream(messages), which has no output
    # bound. Reject them rather than silently treating a ledger as a cap.
    prepare = getattr(provider, "prepare_bounded", None)
    stream_prepared = getattr(provider, "stream_prepared", None)
    if not callable(prepare) or not callable(stream_prepared):
        raise DeniedModelInvocation("bounded_adapter_contract_missing")
    try:
        prepared = prepare(messages, max_output_tokens=output_tokens)
    except Exception as exc:
        raise DeniedModelInvocation("bounded_adapter_prepare_failed") from exc
    _verify_prepared_request(
        prepared, exact_model=admission.model, messages=messages,
        max_input_tokens=input_tokens, max_output_tokens=output_tokens,
    )
    try:
        budget.reserve(admission, request_id=request_id, scope_id=scope_id)
    except BudgetDenied as exc:
        raise DeniedModelInvocation(str(exc)) from exc
    try:
        async for chunk in stream_prepared(prepared):
            yield chunk
    except BaseException:
        budget.settle(request_id, uncertain=True)
        raise
    else:
        budget.settle(request_id, uncertain=False)
