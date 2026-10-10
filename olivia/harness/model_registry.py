"""Strict, account-scoped model admission for the future Agent Fabric.

Entitlements are owner-reviewed *evidence*, not promises inferred from a
model catalog or a provider's daily request limit. The caller must load
attestations from a trusted server-side source, never model-generated text.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from ipaddress import ip_address
from typing import Iterable
from urllib.parse import urlsplit

from olivia.router import ProviderSpec, _forbidden_model_route

_CAPABILITIES = frozenset({"chat", "code", "review", "research", "vision"})
_ALLOWED_COST = frozenset({"local", "free_hard_cap"})


@dataclass(frozen=True)
class ModelAttestation:
    provider: str
    model: str
    account_id: str
    cost_mode: str
    evidence_ref: str
    reviewed_at: date
    expires_at: date
    production_permitted: bool
    no_credit_overage_verified: bool
    capabilities: frozenset[str]
    max_input_tokens: int
    max_output_tokens: int
    daily_request_cap: int

    def __post_init__(self) -> None:
        if not self.provider or not self.model or not self.account_id or not self.evidence_ref:
            raise ValueError("attestation missing identity or evidence")
        if _forbidden_model_route(self.provider, self.model):
            raise ValueError("forbidden model")
        if self.cost_mode not in _ALLOWED_COST:
            raise ValueError("unsupported cost mode")
        if self.reviewed_at > self.expires_at:
            raise ValueError("invalid attestation review window")
        if not self.capabilities or not self.capabilities.issubset(_CAPABILITIES):
            raise ValueError("unknown capability")
        for field in ("max_input_tokens", "max_output_tokens", "daily_request_cap"):
            value = getattr(self, field)
            if type(value) is not int or value <= 0:
                raise ValueError(f"invalid {field}")


@dataclass(frozen=True)
class ParentBudget:
    max_input_tokens: int
    max_output_tokens: int
    max_total_tokens: int


@dataclass(frozen=True)
class ModelAdmission:
    allowed: bool
    reason: str
    provider: str = ""
    model: str = ""
    account_id: str = ""
    capability: str = ""
    reserved_input_tokens: int = 0
    reserved_output_tokens: int = 0
    daily_request_cap: int = 0


def _local_loopback(spec: ProviderSpec) -> bool:
    parts = urlsplit(spec.base_url)
    if parts.scheme not in {"http", "https"} or parts.username or parts.password:
        return False
    hostname = parts.hostname
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


class ModelRegistry:
    def __init__(
        self,
        providers: Iterable[ProviderSpec],
        attestations: Iterable[ModelAttestation] = (),
        *,
        today: date | None = None,
    ) -> None:
        self._today = today
        self._providers: dict[str, ProviderSpec] = {}
        self._evidence: dict[tuple[str, str], ModelAttestation] = {}
        for spec in providers:
            if spec.name in self._providers:
                raise ValueError("duplicate provider identity")
            if _forbidden_model_route(spec.name, spec.model):
                raise ValueError("forbidden model")
            self._providers[spec.name] = spec
        for item in attestations:
            key = (item.provider, item.model)
            if key in self._evidence:
                raise ValueError("duplicate model attestation")
            self._evidence[key] = item

    def admit(
        self,
        provider: str,
        capability: str,
        max_input: int,
        max_output: int,
        parent_budget: ParentBudget | None = None,
    ) -> ModelAdmission:
        def deny(reason: str) -> ModelAdmission:
            return ModelAdmission(False, reason)

        spec = self._providers.get(provider)
        if spec is None:
            return deny("unknown_provider")
        if _forbidden_model_route(spec.name, spec.model):
            return deny("forbidden_model")
        if capability not in _CAPABILITIES or capability not in spec.capabilities:
            return deny("capability_not_allowed")
        if type(max_input) is not int or type(max_output) is not int:
            return deny("invalid_token_budget")
        if max_input <= 0 or max_output <= 0:
            return deny("invalid_token_budget")
        record = self._evidence.get((spec.name, spec.model))
        if record is None:
            return deny("account_model_not_attested")
        if record.cost_mode != spec.cost_mode or record.capabilities.isdisjoint({capability}):
            return deny("attestation_mismatch")
        if not record.production_permitted or not record.no_credit_overage_verified:
            return deny("production_or_no_overage_unverified")
        if record.reviewed_at > (self._today or date.today()) or record.expires_at < (self._today or date.today()):
            return deny("attestation_expired_or_future")
        if spec.cost_mode not in _ALLOWED_COST:
            return deny("cost_mode_unverified")
        if spec.cost_mode == "local":
            if not _local_loopback(spec):
                return deny("local_model_not_loopback")
        elif not spec.base_url.startswith("https://") or not spec.daily_limit:
            return deny("remote_endpoint_or_quota_unverified")
        if max_input > record.max_input_tokens or max_output > record.max_output_tokens:
            return deny("model_token_limit_exceeded")
        if parent_budget is not None:
            limits = (parent_budget.max_input_tokens, parent_budget.max_output_tokens,
                      parent_budget.max_total_tokens)
            if any(type(x) is not int or x <= 0 for x in limits):
                return deny("invalid_parent_budget")
            if (max_input > limits[0] or max_output > limits[1]
                    or max_input + max_output > limits[2]):
                return deny("parent_budget_exceeded")
        daily_limit = record.daily_request_cap
        if spec.daily_limit:
            daily_limit = min(spec.daily_limit, daily_limit)
        return ModelAdmission(
            True, "permitted", spec.name, spec.model, record.account_id, capability,
            max_input, max_output, daily_limit
        )
