#!/usr/bin/env bash
set -euo pipefail

# 0liviA cloud bootstrap.
# Recurring-cost invariant: local inference only. No metered API can be reached
# through the generated provider configuration.

REPO_URL="${REPO_URL:-https://github.com/simondalmasso/0liviA.git}"
REF="${REF:-}"
ALLOW_MUTABLE_REF="${ALLOW_MUTABLE_REF:-0}"
APP_ROOT="${APP_ROOT:-/opt/0livia}"
STATE_ROOT="${STATE_ROOT:-/var/lib/0livia}"
ETC_ROOT="${ETC_ROOT:-/etc/0livia}"
LLAMA_ROOT="${LLAMA_ROOT:-/opt/llama}"
LLAMA_BUILD="${LLAMA_BUILD:-b11388}"
MODEL_ROOT="${MODEL_ROOT:-${STATE_ROOT}/models}"
MODEL_PROFILE="${MODEL_PROFILE:-auto}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root" >&2
  exit 2
fi

if [[ "$REF" =~ ^[0-9a-fA-F]{40}$ ]]; then
  :
elif [[ "$ALLOW_MUTABLE_REF" == "1" && -n "$REF" ]]; then
  echo "WARNING: mutable REF allowed explicitly for development: $REF" >&2
else
  echo "REF must be an exact 40-hex commit SHA (or set ALLOW_MUTABLE_REF=1 for development)" >&2
  exit 2
fi

arch="$(uname -m)"
case "${arch}" in
  aarch64|arm64)
    llama_asset="llama-${LLAMA_BUILD}-bin-ubuntu-arm64.tar.gz"
    llama_sha256="9f454c895ab49d4173cfb3995a39e4f8fe21b364787db8e1ca2778ee7f39aa36"
    ;;
  x86_64|amd64)
    llama_asset="llama-${LLAMA_BUILD}-bin-ubuntu-x64.tar.gz"
    llama_sha256="43bfc230e612d20efd483be7d1ce98ff5f7a0ec6e82a7ec959586b3313ee239f"
    ;;
  *) echo "unsupported architecture: ${arch}" >&2; exit 2 ;;
esac

mem_kb="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
cpu_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc || echo 1)"
if [[ "${MODEL_PROFILE}" == "auto" ]]; then
  if (( mem_kb >= 5 * 1024 * 1024 )); then
    MODEL_PROFILE="a1"
  else
    MODEL_PROFILE="micro"
  fi
fi

case "${MODEL_PROFILE}" in
  a1)
    MODEL_NAME="Qwen3-1.7B-Q4_K_M.gguf"
    MODEL_URL="https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/9193700074c255639d2e18a086707686a88279a7/Qwen3-1.7B-Q4_K_M.gguf"
    MODEL_SHA256="b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897"
    LLAMA_CTX=4096
    LLAMA_THREADS="$(( cpu_count > 2 ? 2 : cpu_count ))"
    ;;
  micro)
    MODEL_NAME="Qwen3-0.6B-Q4_K_M.gguf"
    MODEL_URL="https://huggingface.co/lmstudio-community/Qwen3-0.6B-GGUF/resolve/3334d820ab76652cf6e242d7c6302b10f0951f23/Qwen3-0.6B-Q4_K_M.gguf"
    MODEL_SHA256="cd47557a67d7e8f2891d98b5e1dbf2988544569fdf4f1bdb30e92b71aa61b548"
    LLAMA_CTX=1024
    LLAMA_THREADS=1
    ;;
  *)
    echo "unknown MODEL_PROFILE=${MODEL_PROFILE}" >&2
    exit 2
    ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends   ca-certificates curl git python3 python3-pip python3-venv zstd caddy libgomp1 openssl

if ! id olivia >/dev/null 2>&1; then
  useradd --system --home "${STATE_ROOT}" --shell /usr/sbin/nologin olivia
fi

install -d -o root -g root -m 0755 "${APP_ROOT}" "${LLAMA_ROOT}"
install -d -o olivia -g olivia -m 0700 "${STATE_ROOT}" "${MODEL_ROOT}"
install -d -o root -g olivia -m 0750 "${ETC_ROOT}"

# The 1 GB micro fallback needs swap to survive model load. A1 does not.
if (( mem_kb < 2 * 1024 * 1024 )) && ! swapon --show=NAME --noheadings | grep -q .; then
  if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile >/dev/null
  fi
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

if [[ "$REF" =~ ^[0-9a-fA-F]{40}$ ]]; then
  git init -q "${tmp}/repo"
  git -C "${tmp}/repo" remote add origin "${REPO_URL}"
  git -C "${tmp}/repo" fetch --depth 1 origin "$REF"
  git -C "${tmp}/repo" checkout -q --detach FETCH_HEAD
  test "$(git -C "${tmp}/repo" rev-parse HEAD)" = "$REF"
else
  git clone --filter=blob:none --depth 1 --branch "$REF" "${REPO_URL}" "${tmp}/repo"
fi
rm -rf "${APP_ROOT}/current"
install -d -o root -g root -m 0755 "${APP_ROOT}/current"
cp -a "${tmp}/repo/." "${APP_ROOT}/current/"
rm -rf "${APP_ROOT}/current/.git"

python3 -m venv "${APP_ROOT}/venv"
"${APP_ROOT}/venv/bin/pip" install --upgrade pip
"${APP_ROOT}/venv/bin/pip" install "${APP_ROOT}/current"

install -o root -g root -m 0644   "${APP_ROOT}/current/deploy/0livia.service"   /etc/systemd/system/olivia.service
install -o root -g root -m 0644   "${APP_ROOT}/current/deploy/llama-local.service"   /etc/systemd/system/llama-local.service

# llama.cpp prebuilt is ~tens of MB, not a multi-GB runtime.
curl -fL --retry 3 --retry-delay 2   "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_BUILD}/${llama_asset}"   -o "${tmp}/llama.tar.gz"
printf '%s  %s\n' "${llama_sha256}" "${tmp}/llama.tar.gz" | sha256sum -c -
rm -rf "${LLAMA_ROOT:?}/"*
tar -xzf "${tmp}/llama.tar.gz" -C "${LLAMA_ROOT}" --strip-components=1
test -x "${LLAMA_ROOT}/llama-server"

MODEL_PATH="${MODEL_ROOT}/${MODEL_NAME}"
if [[ ! -s "${MODEL_PATH}" ]]; then
  curl -fL --retry 3 --retry-delay 3 "${MODEL_URL}" -o "${MODEL_PATH}.part"
  test "$(stat -c %s "${MODEL_PATH}.part")" -gt 100000000
  printf '%s  %s\n' "${MODEL_SHA256}" "${MODEL_PATH}.part" | sha256sum -c -
  mv "${MODEL_PATH}.part" "${MODEL_PATH}"
fi
printf '%s  %s\n' "${MODEL_SHA256}" "${MODEL_PATH}" | sha256sum -c -
chown olivia:olivia "${MODEL_PATH}"
chmod 0600 "${MODEL_PATH}"

cat > "${ETC_ROOT}/llama.env" <<EOF
LLAMA_MODEL_PATH=${MODEL_PATH}
LLAMA_CTX=${LLAMA_CTX}
LLAMA_THREADS=${LLAMA_THREADS}
EOF
chown root:olivia "${ETC_ROOT}/llama.env"
chmod 0640 "${ETC_ROOT}/llama.env"

TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
REGISTRATION_TOKEN="$(python3 - <<'PY'
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
OLIVIA_REGISTRATION_TOKEN=${REGISTRATION_TOKEN}
OLIVIA_MAX_HISTORY=24
OLIVIA_TTFT_TIMEOUT_S=45
OLIVIA_STREAM_IDLE_TIMEOUT_S=120
OLIVIA_MAX_PROVIDER_ATTEMPTS=1
OLIVIA_PROVIDERS_JSON=[{"name":"local-qwen","base_url":"http://127.0.0.1:11434/v1","model":"local-qwen","api_key_env":"","priority":10,"daily_limit":0,"cost_mode":"local"}]
EOF
chown root:olivia "${ETC_ROOT}/olivia.env"
chmod 0640 "${ETC_ROOT}/olivia.env"

systemctl daemon-reload
systemctl enable --now llama-local
for _ in $(seq 1 120); do
  if curl -fsS http://127.0.0.1:11434/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:11434/health >/dev/null

systemctl enable --now olivia

# Direct-to-Oracle HTTPS. Cloudflare remains outside chat/voice/memory.
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
  reverse_proxy 127.0.0.1:8080 {
    flush_interval -1
  }
  header {
    Strict-Transport-Security "max-age=31536000"
    X-Content-Type-Options nosniff
    X-Frame-Options DENY
    Referrer-Policy no-referrer
    Permissions-Policy "camera=(), geolocation=(), payment=(), usb=()"
  }
}
EOF
systemctl enable --now caddy
systemctl restart caddy

cat > "${STATE_ROOT}/bootstrap-info" <<EOF
URL=https://${HOST}
REGISTRATION=first-run
SETUP_URL=https://${HOST}/#setup=${REGISTRATION_TOKEN}
MODEL_PROFILE=${MODEL_PROFILE}
MODEL=${MODEL_NAME}
MODEL_SHA256=${MODEL_SHA256}
RUNTIME=llama.cpp-${LLAMA_BUILD}
RUNTIME_SHA256=${llama_sha256}
COST_MODE=local
SOURCE_REF=${REF}
EOF
chown root:root "${STATE_ROOT}/bootstrap-info"
chmod 0600 "${STATE_ROOT}/bootstrap-info"
unset TOKEN REGISTRATION_TOKEN

for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:8080/healthz
echo
echo "0liviA bootstrap complete: https://${HOST}"
