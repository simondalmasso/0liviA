#!/usr/bin/env python3
"""NVIDIA NIM trial-only, single-request entitlement probe.

Run manually from the dedicated Actions workflow. Never use as public inference.
No user/project prompts, no credentials in output, no retry/fallback.
"""
from __future__ import annotations

import http.client
import json
import os
import sys

ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "deepseek-ai/deepseek-v4.1-flash"
ALLOWED_MODELS = {
    "deepseek": MODEL,
    "muse-glimmer": "meta/muse-glimmer-30b",
}


def main() -> int:
    if os.environ.get("NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED") != "1":
        print("BLOCKED: trial/no-billing account verification is missing.", file=sys.stderr)
        return 2
    selected = os.environ.get("NVIDIA_NIM_EVAL_MODEL", "deepseek")
    model = ALLOWED_MODELS.get(selected)
    if not model:
        print("BLOCKED: model not on internal-evaluation allowlist.", file=sys.stderr)
        return 2
    key = os.environ.get("NVIDIA_API_KEY", "")
    if not key or not key.startswith("nvapi-"):
        print("BLOCKED: NVIDIA_API_KEY missing or unrecognized; no request sent.", file=sys.stderr)
        return 2

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Respond only with: OK"}],
        "max_tokens": 64,
        "stream": False,
        "temperature": 1 if selected == "muse-glimmer" else 0,
    }).encode("utf-8")
    # Fixed HTTPS origin/path; http.client never follows redirects, including
    # cross-origin redirects that could otherwise carry a bearer token.
    conn = http.client.HTTPSConnection("integrate.api.nvidia.com", timeout=30)
    try:
        conn.request("POST", "/v1/chat/completions", body, {
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        response = conn.getresponse()
        if response.status != 200:
            # Never print provider response bodies; they might reflect secrets.
            print(f"NVIDIA_NIM_EVAL_FAIL: HTTP {response.status}", file=sys.stderr)
            return 1
        data = response.read(32_769)
        if len(data) > 32_768:
            print("NVIDIA_NIM_EVAL_FAIL: oversized response", file=sys.stderr)
            return 1
        result = json.loads(data)
        if not isinstance(result, dict) or not result.get("choices"):
            print("NVIDIA_NIM_EVAL_FAIL: no model completion", file=sys.stderr)
            return 1
        print("NVIDIA_NIM_TRIAL_EVAL_OK: internal-only; production eligibility NOT verified")
        return 0
    except (http.client.HTTPException, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        print("NVIDIA_NIM_EVAL_FAIL: transport or response validation", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
