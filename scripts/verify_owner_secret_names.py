#!/usr/bin/env python3
"""Fail-closed, read-only validation of Worker owner-auth secret *names*.

Input is the JSON output of Wrangler secret list; it never contains secret values.
No Cloudflare credentials, owner identity, or secret names are printed in CI.
"""
from __future__ import annotations

import json
import sys

REQUIRED = frozenset({
    "OLIVIA_AUTH0_ISSUER",
    "OLIVIA_AUTH0_AUDIENCE",
    "OLIVIA_OWNER_AUTH0_SUB",
    "OLIVIA_OWNER_EMAIL",
    "OLIVIA_OWNER_SESSION_VERSION",
    "OLIVIA_OWNER_REVOKED_BEFORE",
})


def owner_secrets_present(payload: object) -> bool:
    if not isinstance(payload, list) or len(payload) > 100:
        return False
    names: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            return False
        name = item.get("name")
        if not isinstance(name, str) or len(name) > 128 or name in names:
            return False
        if item.get("type") != "secret_text":
            # Binding from another source is not proof of a private Worker secret.
            return False
        names.add(name)
    return REQUIRED <= names


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if owner_secrets_present(payload):
            print("OWNER_AUTH0_SECRET_NAMES=PASS (values unread)")
            return 0
    except (OSError, ValueError, TypeError):
        pass
    print("BLOCKED: owner Auth0 secrets missing or unverified", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
