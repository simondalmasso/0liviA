#!/usr/bin/env bash
set -euo pipefail

# Install a locally authorized ChatGPT-plan profile on the 0liviA Core.
# This script never prints credential contents and rolls back on failed health.

PROFILE_SOURCE="${1:-}"
MODEL_OVERRIDE="${2:-}"
STATE_ROOT="${STATE_ROOT:-/var/lib/0livia}"
ETC_ROOT="${ETC_ROOT:-/etc/0livia}"
TARGET="${STATE_ROOT}/private/chatgpt-plan.json"
ENV_FILE="${ETC_ROOT}/olivia.env"

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root on the 0liviA host" >&2
  exit 2
fi
if [[ -z "${PROFILE_SOURCE}" || ! -f "${PROFILE_SOURCE}" ]]; then
  echo "usage: sudo $0 /path/to/chatgpt-plan.json [model-slug]" >&2
  exit 2
fi
if [[ "${OLIVIA_CHATGPT_NO_CREDIT_OVERAGE_VERIFIED:-0}" != "1" ]]; then
  echo "refusing to enable: set OLIVIA_CHATGPT_NO_CREDIT_OVERAGE_VERIFIED=1 only after checking ChatGPT Usage controls" >&2
  exit 3
fi
test -f "${ENV_FILE}"

# Validate the staging file before touching a known-good installed profile.
readarray -t META < <(
  python3 - "${PROFILE_SOURCE}" "${MODEL_OVERRIDE}" <<'PY'
import json
import re
import sys

path, override = sys.argv[1:3]
with open(path, "r", encoding="utf-8") as fh:
    profile = json.load(fh)

required = ("client_id", "access_token", "refresh_token", "expires_at", "scope")
missing = [key for key in required if not profile.get(key)]
if missing:
    raise SystemExit("profile missing required fields")

scopes = set(str(profile["scope"]).split())
required_scopes = {
    "offline_access",
    "resource.invoke",
    "chatgpt.tokens.use.direct",
}
if not required_scopes.issubset(scopes):
    raise SystemExit("profile does not grant the complete ChatGPT plan permission")

models = [
    item.get("slug")
    for item in profile.get("model_catalog", [])
    if isinstance(item, dict) and isinstance(item.get("slug"), str)
]
model = override.strip() or str(profile.get("recommended_model") or "").strip()
if not model:
    model = "gpt-6-astra" if "gpt-6-astra" in models else (models[0] if models else "")
if not model or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model):
    raise SystemExit("no safe model slug is available in the OAuth profile")
if models and model not in models:
    raise SystemExit("selected model is not in the signed-in account catalog")

print(model)
PY
)
MODEL="${META[0]}"

backup_dir="$(mktemp -d)"
had_target=0
cleanup() { rm -rf "${backup_dir}"; }
trap cleanup EXIT

cp -p "${ENV_FILE}" "${backup_dir}/olivia.env"
if [[ -f "${TARGET}" ]]; then
  had_target=1
  cp -p "${TARGET}" "${backup_dir}/chatgpt-plan.json"
fi

rollback() {
  echo "ChatGPT plan activation failed; restoring previous 0liviA configuration." >&2
  cp -p "${backup_dir}/olivia.env" "${ENV_FILE}"
  chown root:olivia "${ENV_FILE}"
  chmod 0640 "${ENV_FILE}"
  if (( had_target == 1 )); then
    install -o olivia -g olivia -m 0600 "${backup_dir}/chatgpt-plan.json" "${TARGET}"
  else
    rm -f "${TARGET}"
  fi
  systemctl restart olivia >/dev/null 2>&1 || true
}

install -d -o olivia -g olivia -m 0700 "${STATE_ROOT}/private"
install -o olivia -g olivia -m 0600 "${PROFILE_SOURCE}" "${TARGET}"

python3 - "${ENV_FILE}" "${TARGET}" "${MODEL}" <<'PY'
import json
import os
import sys
import tempfile

env_path, profile_path, model = sys.argv[1:4]
with open(env_path, "r", encoding="utf-8") as fh:
    lines = fh.read().splitlines()

providers = []
for line in lines:
    if line.startswith("OLIVIA_PROVIDERS_JSON="):
        raw = line.split("=", 1)[1].strip()
        providers = json.loads(raw or "[]")
        break
if not isinstance(providers, list):
    raise SystemExit("OLIVIA_PROVIDERS_JSON is not a list")

providers = [
    item for item in providers
    if not (isinstance(item, dict) and item.get("name") == "chatgpt-plan")
]
providers.insert(0, {
    "name": "chatgpt-plan",
    "kind": "chatgpt_plan",
    "base_url": "https://api.openai.com/v1",
    "model": model,
    "profile_path": profile_path,
    "priority": 1,
    "daily_limit": 0,
    "cost_mode": "plan_included",
    "no_credit_overage_verified": True,
})

encoded = json.dumps(providers, separators=(",", ":"))
new_lines = []
replaced = False
for line in lines:
    if line.startswith("OLIVIA_PROVIDERS_JSON="):
        new_lines.append("OLIVIA_PROVIDERS_JSON=" + encoded)
        replaced = True
    else:
        new_lines.append(line)
if not replaced:
    new_lines.append("OLIVIA_PROVIDERS_JSON=" + encoded)

directory = os.path.dirname(env_path) or "."
fd, tmp = tempfile.mkstemp(prefix=".olivia.env.", dir=directory, text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(new_lines) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, env_path)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
PY

chown root:olivia "${ENV_FILE}"
chmod 0640 "${ENV_FILE}"

if ! systemctl restart olivia; then
  rollback
  exit 1
fi

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1; then
    echo "ChatGPT plan provider instalado para 0liviA (modelo: ${MODEL})."
    exit 0
  fi
  sleep 1
done

rollback
if curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1; then
  echo "Se restauró la configuración anterior correctamente." >&2
else
  echo "Rollback aplicado, pero 0liviA sigue sin responder; revisá journalctl -u olivia." >&2
fi
exit 1
