from __future__ import annotations

import re

REDACTED = "[REDACTED_SECRET]"

_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:API[_-]?KEY|ACCESS[_-]?TOKEN|AUTH[_-]?TOKEN|SECRET|PASSWORD)\s*[=:]\s*"
        r"(["']?)[A-Za-z0-9._~+/=-]{16,}\1",
        re.IGNORECASE,
    ),
)


def contains_secret(value: str) -> bool:
    text = str(value or "")
    return any(pattern.search(text) for pattern in _PATTERNS)


def redact_secrets(value: str) -> str:
    text = str(value or "")
    for pattern in _PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text
