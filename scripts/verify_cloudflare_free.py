#!/usr/bin/env python3
"""Read-only Cloudflare subscription proof for an authorized one-time Qwen release.

Never deploy or call Workers AI here. Fail closed if account-plan evidence
cannot be fetched. Credentials are read from environment; no response bodies,
IDs, emails, secrets or subscriptions are printed.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import sys


def free_plan_confirmed(payload: object) -> bool:
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return False
    rows = payload.get("result")
    info = payload.get("result_info", {})
    if not isinstance(rows, list) or not isinstance(info, dict):
        return False
    count = info.get("total_count")
    if count is not None and (not isinstance(count, int) or count > len(rows)):
        return False  # refuse a partial page
    for entry in rows:
        if not isinstance(entry, dict):
            return False
        plan = entry.get("rate_plan") or {}
        if not isinstance(plan, dict):
            return False
        plan_id = str(plan.get("id") or "").upper()
        scope = str(plan.get("scope") or "").upper()
        public_name = str(plan.get("public_name") or "").upper()
        state = str(entry.get("state") or "").upper()
        if state in {"CANCELLED", "EXPIRED", "FAILED"}:
            continue
        if ("WORKER" in plan_id or "WORKER" in scope or "WORKER" in public_name):
            if plan_id not in {"WORKERS_FREE", "WORKERS_FREE_PLAN"}:
                return False  # Workers Paid, enterprise or unknown entitlement
        if "AI GATEWAY" in public_name and "UNIFIED" in public_name:
            return False
    # Cloudflare defaults to Workers Free where no active Workers Paid
    # subscription exists. Only a complete authenticated billing listing counts.
    return True


def main() -> int:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not re.fullmatch(r"[a-f0-9]{32}", account) or not token:
        print("BLOCKED: Cloudflare billing read-only proof unavailable", file=sys.stderr)
        return 2
    connection = http.client.HTTPSConnection("api.cloudflare.com", timeout=15)
    try:
        connection.request(
            "GET",
            f"/client/v4/accounts/{account}/subscriptions?per_page=100",
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        )
        response = connection.getresponse()
        if response.status != 200:
            print("BLOCKED: billing proof HTTP access denied/unavailable", file=sys.stderr)
            return 2
        blob = response.read(128_001)
        if len(blob) > 128_000:
            print("BLOCKED: billing proof unexpectedly large", file=sys.stderr)
            return 2
        if not free_plan_confirmed(json.loads(blob)):
            print("BLOCKED: Workers Free/no-overage could not be proven", file=sys.stderr)
            return 2
        print("WORKERS_FREE_BILLING_PROOF=PASS (account identifiers withheld)")
        return 0
    except (OSError, ValueError, http.client.HTTPException):
        print("BLOCKED: Cloudflare billing verification failed", file=sys.stderr)
        return 2
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
