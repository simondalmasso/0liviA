#!/usr/bin/env bash
set -euo pipefail

# 0liviA A1 bootstrap.
# Hard rule: this script configures only a local inference lane and cannot spend API money.

REPO_URL="${REPO_URL:-https://github.com/simondalmasso/0liviA.git}"
REF="${REF:-arch/gpt-synthesis-v1}"
APP_ROOT="${APP_ROOT:-/opt/0liviA}"
STATE_ROOT="${STATE_ROOT:-/var/lib/0livia}"
ETC_ROOT="${ETC_ROOT:-/etc/0livia}"
OLLAMA_VERSION="${OLLAMA_VERSION:-v0.35.1}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:1.7b}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends   ca-certificates curl git jq python3 python3-pip python3-venv zstd caddy

if ! id olivia >/dev/null 2>&1; then
  useradd --system --home "${STATE_ROOT}" --shell /usr/sbin/nologin olivia
fi

install -d -o root -g root -m 0755 "${APP_ROOT}"
install -d -o olivia -g olivia -m 0700 "${STATE_ROOT}"
install -d -o root -g olivia -m 0750 "${ETC_ROOT}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone --filter=blob:none --depth 1 --branch "${REF}" "${REPO_URL}" "$tmp/repo"
rm -rf "${APP_ROOT}/current"
install -d -o root -g root -m 0755 "${APP_ROOT}/current"
cp -a "$tmp/repo/." "${APP_ROOT}/current/"
rm -rf "${APP_ROOT}/current/.git"

python3 -m venv "${APP_ROOT}/venv"
"${APP_ROOT}/venv/bin/pip" install --upgrade pip
"${APP_ROOT}/venv/bin/pip" install "${APP_ROOT}/current"

install -o root -g root -m 0644   "${APP_ROOT}/current/deploy/0livia.service"   /etc/systemd/system/olivia.service

# Pinned official Ollama installer. This is the only local inference runtime.
curl -fL   "https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}/install.sh"   -o "$tmp/ollama-install.sh"
chmod 0755 "$tmp/ollama-install.sh"
OLLAMA_VERSION="${OLLAMA_VERSION}" "$tmp/ollama-install.sh"

systemctl enable --now ollama
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:11434/api/version >/dev/null

# Pull one small CPU-capable model. If this fails, text UI still boots but health is degraded.
if ! ollama pull "${OLLAMA_MODEL}"; then
  echo "WARNING: local model pull failed: ${OLLAMA_MODEL}" >&2
fi

TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"

cat > "${ETC_ROOT}/olivia.env" <<EOF
OLIVIA_DATA_DIR=${STATE_ROOT}
OLIVIA_BIND=127.0.0.1
OLIVIA_PORT=8080
OLIVIA_HARD_ZERO_COST=1
OLIVIA_GATEWAY_TOKEN=${TOKEN}
OLIVIA_MAX_HISTORY=24
OLIVIA_TTFT_TIMEOUT_S=30
OLIVIA_STREAM_IDLE_TIMEOUT_S=120
OLIVIA_MAX_PROVIDER_ATTEMPTS=1
OLIVIA_PROVIDERS_JSON=[{"name":"local-qwen","base_url":"http://127.0.0.1:11434/v1","model":"${OLLAMA_MODEL}","api_key_env":"","priority":10,"daily_limit":0,"cost_mode":"local"}]
EOF
chown root:olivia "${ETC_ROOT}/olivia.env"
chmod 0640 "${ETC_ROOT}/olivia.env"

systemctl daemon-reload
systemctl enable --now olivia

# Direct-to-Oracle HTTPS; Cloudflare is not in the runtime path.
PUBLIC_IP=""
for _ in $(seq 1 30); do
  PUBLIC_IP="$(curl -4fsS --max-time 4 https://api.ipify.org 2>/dev/null || true)"
  [[ -n "${PUBLIC_IP}" ]] && break
  sleep 2
done
if [[ -z "${PUBLIC_IP}" ]]; then
  echo "could not determine public IPv4" >&2
  exit 1
fi
HOST="${PUBLIC_IP}.nip.io"

cat > /etc/caddy/Caddyfile <<EOF
${HOST} {
  encode zstd gzip
  reverse_proxy 127.0.0.1:8080
}
EOF
systemctl enable --now caddy
systemctl restart caddy

cat > "${STATE_ROOT}/bootstrap-info" <<EOF
URL=https://${HOST}
TOKEN=${TOKEN}
MODEL=${OLLAMA_MODEL}
COST_MODE=local
EOF
chown root:adm "${STATE_ROOT}/bootstrap-info"
chmod 0640 "${STATE_ROOT}/bootstrap-info"

for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:8080/healthz
echo
echo "0liviA bootstrap complete: https://${HOST}"
