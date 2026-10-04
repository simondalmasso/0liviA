#!/usr/bin/env bash
set -euo pipefail

BASE="${1:?usage: smoke.sh https://host TOKEN}"
TOKEN="${2:?usage: smoke.sh https://host TOKEN}"

health="$(curl -fsS --max-time 10 "${BASE}/healthz")"
printf 'health: %s\n' "${health}"

session_json="$(curl -fsS --max-time 10 \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"title":"deploy-smoke"}' \
  "${BASE}/api/sessions")"
printf 'session: %s\n' "${session_json}"

session_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${session_json}")"

printf 'chat stream:\n'
curl -fsSN --max-time 45 \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Respondé solamente: listo"}' \
  "${BASE}/api/chat/${session_id}"

printf '\nsmoke complete\n'
