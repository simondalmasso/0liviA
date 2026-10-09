#!/usr/bin/env python3
"""NVIDIA NIM trial-only, single-request entitlement probe.

Run manually from the dedicated Actions workflow. Never use as public inference.
No user/project prompts, no credentials in output, no retry/fallback.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "deepseek-ai/deepseek-v4.1-flash"


def main() -> int:
    if os.environ.get("NVIDIA_NIM_TRIAL_NONBILLABLE_CONFIRMED") != "1":
        print("BLOCKED: trial/no-billing account verification is missing.", file=sys.stderr)
        return 2
    key = os.environ.get("NVIDIA_API_KEY", "")
    if not key or not key.startswith("nvapi-"):
        print("BLOCKED: NVIDIA_API_KEY missing or unrecognized; no request sent.", file=sys.stderr)
        return 2

    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "Respond only with: OK"}],
        "max_tokens": 64,
        "stream": False,
        "temperature": 0,
    }).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                print(f"NVIDIA_NIM_EVAL_FAIL: HTTP {response.status}", file=sys.stderr)
                return 1
            # Bound response data. Never log raw output or prompts.
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
    except urllib.error.HTTPError as exc:
        # Do NOT echo HTTP response: proxies can reflect Authorization headers.
        print(f"NVIDIA_NIM_EVAL_FAIL: HTTP {exc.code}", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        print("NVIDIA_NIM_EVAL_FAIL: transport or response validation", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
