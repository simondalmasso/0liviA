#!/usr/bin/env bash
set -euo pipefail

BASE="${1:?usage: smoke.sh https://host TOKEN EXPECTED_SHA}"
TOKEN="${2:?usage: smoke.sh https://host TOKEN EXPECTED_SHA}"
EXPECTED_SHA="${3:?usage: smoke.sh https://host TOKEN EXPECTED_SHA}"

health="$(curl -fsS --max-time 10 "${BASE}/healthz")"
printf 'health: %s\n' "${health}"

HEALTH_JSON="${health}" EXPECTED_SHA="${EXPECTED_SHA}" python3 - <<'PY'
import json
import os
import re

body = json.loads(os.environ["HEALTH_JSON"])
expected = os.environ["EXPECTED_SHA"].strip().lower()

if not re.fullmatch(r"[0-9a-f]{40}", expected):
    raise SystemExit("EXPECTED_SHA must be an exact 40-character commit SHA")

checks = {
    "process_alive": body.get("process_alive") is True,
    "api_mode": body.get("api_mode") == "canonical",
    "build_sha": str(body.get("build_sha") or "").lower() == expected,
    "hard_zero_cost": body.get("hard_zero_cost") is True,
    "provider_ready": body.get("provider_ready") is True,
    "owner_auth_configured": body.get("owner_auth_configured") is True,
    "registration_closed": body.get("registration_open") is False,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("health gate failed: " + ", ".join(failed))

allowed_modes = {"local", "free_hard_cap", "plan_included"}
catalog = body.get("provider_catalog") or []
available = [row for row in catalog if row.get("available")]
if not available:
    raise SystemExit("health gate failed: no available provider")
for row in available:
    mode = str(row.get("cost_mode") or "")
    if mode not in allowed_modes:
        raise SystemExit(
            f"health gate failed: available provider {row.get('name')} has unsafe cost_mode={mode}"
        )
PY

session_json="$(curl -fsS --max-time 10 \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"title":"deploy-smoke"}' \
  "${BASE}/api/sessions")"
printf 'session: %s\n' "${session_json}"

session_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${session_json}")"

printf 'chat stream:\n'
chat_stream="$(curl -fsSN --max-time 45 \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Respondé solamente: listo"}' \
  "${BASE}/api/chat/${session_id}")"
printf '%s\n' "${chat_stream}"

CHAT_STREAM="${chat_stream}" python3 - <<'PY'
import json
import os

events = []
for line in os.environ["CHAT_STREAM"].splitlines():
    if not line.startswith("data: "):
        continue
    raw = line[6:].strip()
    if not raw:
        continue
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit("chat gate failed: malformed SSE event") from exc
    if not isinstance(event, dict):
        raise SystemExit("chat gate failed: invalid event shape")
    events.append(event)

if any(event.get("type") == "error" for event in events):
    raise SystemExit("chat gate failed: provider/stream error present")
route_events = [
    i for i, event in enumerate(events)
    if event.get("type") == "route" and str(event.get("provider") or "").strip()
]
delta_events = [
    i for i, event in enumerate(events)
    if event.get("type") == "delta" and str(event.get("text") or "").strip()
]
done_events = [i for i, event in enumerate(events) if event.get("type") == "done"]

if not route_events:
    raise SystemExit("chat gate failed: no provider route event")
if not delta_events:
    raise SystemExit("chat gate failed: no nonempty assistant answer")
if len(done_events) != 1:
    raise SystemExit("chat gate failed: expected exactly one completion")
if not (route_events[0] < delta_events[0] < done_events[0] == len(events) - 1):
    raise SystemExit("chat gate failed: incorrect stream event order")
if any(i > delta_events[0] for i in route_events):
    raise SystemExit("chat gate failed: provider switched after visible output")
PY

printf '\nsmoke complete: exact canonical zero-cost build verified\n'
