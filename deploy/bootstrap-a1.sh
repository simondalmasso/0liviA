#!/usr/bin/env bash
set -euo pipefail

# 0liviA cloud bootstrap.
# Recurring-cost invariant: no unverified paid inference.
# Small local models are recovery-only and disabled by default so production
# never silently downgrades normal chat quality.

REPO_URL="${REPO_URL:-https://github.com/simondalmasso/0liviA.git}"
REF="${REF:-}"
ALLOW_MUTABLE_REF="${ALLOW_MUTABLE_REF:-0}"
APP_ROOT="${APP_ROOT:-/opt/0livia}"
RELEASES_ROOT="${APP_ROOT}/releases"
STATE_ROOT="${STATE_ROOT:-/var/lib/0livia}"
ETC_ROOT="${ETC_ROOT:-/etc/0livia}"
LLAMA_ROOT="${LLAMA_ROOT:-/opt/llama}"
LLAMA_BUILD="${LLAMA_BUILD:-b11388}"
MODEL_ROOT="${MODEL_ROOT:-${STATE_ROOT}/models}"
MODEL_PROFILE="${MODEL_PROFILE:-auto}"
LOCAL_RECOVERY_ENABLED="${LOCAL_RECOVERY_ENABLED:-0}"

case "${LOCAL_RECOVERY_ENABLED}" in
  0|1) ;;
  *) echo "LOCAL_RECOVERY_ENABLED must be 0 or 1" >&2; exit 2 ;;
esac

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

install -d -o root -g root -m 0755 "${APP_ROOT}" "${RELEASES_ROOT}" "${LLAMA_ROOT}"
install -d -o olivia -g olivia -m 0700 "${STATE_ROOT}" "${MODEL_ROOT}" "${STATE_ROOT}/private"
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

CADDY_FILE="/etc/caddy/Caddyfile"
CADDY_BACKUP="${tmp}/Caddyfile.previous"
CADDY_WAS_PRESENT=0
if [[ -f "${CADDY_FILE}" ]]; then
  cp -a "${CADDY_FILE}" "${CADDY_BACKUP}"
  CADDY_WAS_PRESENT=1
fi

if [[ "$REF" =~ ^[0-9a-fA-F]{40}$ ]]; then
  git init -q "${tmp}/repo"
  git -C "${tmp}/repo" remote add origin "${REPO_URL}"
  git -C "${tmp}/repo" fetch --depth 1 origin "$REF"
  git -C "${tmp}/repo" checkout -q --detach FETCH_HEAD
else
  git clone --filter=blob:none --depth 1 --branch "$REF" "${REPO_URL}" "${tmp}/repo"
fi

SOURCE_SHA="$(git -C "${tmp}/repo" rev-parse HEAD)"
if [[ "$REF" =~ ^[0-9a-fA-F]{40}$ ]] && [[ "${SOURCE_SHA}" != "$REF" ]]; then
  echo "checked-out commit does not match REF" >&2
  exit 2
fi
RELEASE_DIR="${RELEASES_ROOT}/${SOURCE_SHA}"
STAGE_DIR="${RELEASES_ROOT}/.${SOURCE_SHA}.stage.${BASHPID}"

if [[ ! -f "${RELEASE_DIR}/.ready" ]]; then
  rm -rf "${STAGE_DIR}" "${RELEASE_DIR}"
  install -d -o root -g root -m 0755 "${STAGE_DIR}"
  cp -a "${tmp}/repo/." "${STAGE_DIR}/"
  rm -rf "${STAGE_DIR}/.git"
  mv "${STAGE_DIR}" "${RELEASE_DIR}"
  python3 -m venv "${RELEASE_DIR}/venv"
  "${RELEASE_DIR}/venv/bin/pip" install --upgrade pip
  "${RELEASE_DIR}/venv/bin/pip" install "${RELEASE_DIR}"
  touch "${RELEASE_DIR}/.ready"
fi
test -f "${RELEASE_DIR}/.ready"
test -x "${RELEASE_DIR}/venv/bin/python"
test -f "${RELEASE_DIR}/deploy/0livia.service"

PREVIOUS_RELEASE=""
if [[ -L "${APP_ROOT}/current" ]]; then
  PREVIOUS_RELEASE="$(readlink -f "${APP_ROOT}/current" || true)"
elif [[ -d "${APP_ROOT}/current" ]]; then
  LEGACY_RELEASE="${RELEASES_ROOT}/legacy-$(date -u +%Y%m%dT%H%M%SZ)"
  mv "${APP_ROOT}/current" "${LEGACY_RELEASE}"
  if [[ -d "${APP_ROOT}/venv" ]]; then
    mv "${APP_ROOT}/venv" "${LEGACY_RELEASE}/venv"
  fi
  PREVIOUS_RELEASE="${LEGACY_RELEASE}"
fi

install -o root -g root -m 0644   "${RELEASE_DIR}/deploy/0livia.service"   /etc/systemd/system/olivia.service
install -o root -g root -m 0644   "${RELEASE_DIR}/deploy/llama-local.service"   /etc/systemd/system/llama-local.service

if [[ "${LOCAL_RECOVERY_ENABLED}" == "1" ]]; then
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
fi

ENV_FILE="${ETC_ROOT}/olivia.env"
ENV_BACKUP="${tmp}/olivia.env.previous"

if [[ -f "${ENV_FILE}" ]]; then
  # Upgrade path: preserve the configured provider catalog and signing token.
  cp -a "${ENV_FILE}" "${ENV_BACKUP}"
  ENV_FILE="${ENV_FILE}" BUILD_SHA="${SOURCE_SHA}" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ENV_FILE"])
build_sha = os.environ["BUILD_SHA"]
lines = path.read_text(encoding="utf-8").splitlines()

def set_value(key: str, value: str) -> None:
    prefix = key + "="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = prefix + value
            return
    lines.append(prefix + value)

set_value("OLIVIA_BUILD_SHA", build_sha)
set_value("OLIVIA_HARD_ZERO_COST", "1")
tmp = path.with_name(path.name + ".tmp")
tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(tmp, 0o640)
os.replace(tmp, path)
PY
  REGISTRATION_TOKEN="$(sed -n 's/^OLIVIA_REGISTRATION_TOKEN=//p' "${ENV_FILE}" | head -n1)"
  if [[ -z "${REGISTRATION_TOKEN}" ]]; then
    REGISTRATION_TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
    printf 'OLIVIA_REGISTRATION_TOKEN=%s\n' "${REGISTRATION_TOKEN}" >> "${ENV_FILE}"
  fi
else
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

  PROVIDERS_JSON='[]'
  if [[ "${LOCAL_RECOVERY_ENABLED}" == "1" ]]; then
    PROVIDERS_JSON='[{"name":"local-recovery-qwen","base_url":"http://127.0.0.1:11434/v1","model":"local-qwen","api_key_env":"","priority":1000,"daily_limit":0,"cost_mode":"local"}]'
  fi

  cat > "${ENV_FILE}" <<EOF
OLIVIA_DATA_DIR=${STATE_ROOT}
OLIVIA_BIND=127.0.0.1
OLIVIA_PORT=8080
OLIVIA_BUILD_SHA=${SOURCE_SHA}
OLIVIA_HARD_ZERO_COST=1
OLIVIA_GATEWAY_TOKEN=${TOKEN}
OLIVIA_REGISTRATION_TOKEN=${REGISTRATION_TOKEN}
OLIVIA_MAX_HISTORY=24
OLIVIA_TTFT_TIMEOUT_S=45
OLIVIA_STREAM_IDLE_TIMEOUT_S=120
OLIVIA_MAX_PROVIDER_ATTEMPTS=3
OLIVIA_PROVIDERS_JSON=${PROVIDERS_JSON}
EOF
fi
chown root:olivia "${ENV_FILE}"
chmod 0640 "${ENV_FILE}"

rollback_release() {
  if [[ -f "${CADDY_BACKUP}" ]]; then
    cp -a "${CADDY_BACKUP}" "${CADDY_FILE}"
    systemctl restart caddy || true
  elif [[ "${CADDY_WAS_PRESENT}" == "0" ]]; then
    rm -f "${CADDY_FILE}"
    systemctl stop caddy || true
  fi

  if [[ -n "${PREVIOUS_RELEASE}" && -d "${PREVIOUS_RELEASE}" ]]; then
    rm -f "${APP_ROOT}/.current.rollback"
    ln -s "${PREVIOUS_RELEASE}" "${APP_ROOT}/.current.rollback"
    mv -Tf "${APP_ROOT}/.current.rollback" "${APP_ROOT}/current"
    if [[ -f "${ENV_BACKUP}" ]]; then
      cp -a "${ENV_BACKUP}" "${ETC_ROOT}/olivia.env"
      chown root:olivia "${ETC_ROOT}/olivia.env"
      chmod 0640 "${ETC_ROOT}/olivia.env"
    fi
    systemctl daemon-reload
    systemctl restart olivia || true
  else
    rm -f "${APP_ROOT}/current"
    systemctl stop olivia || true
  fi
}

wait_for_core() {
  for _ in $(seq 1 90); do
    if curl -fsS --max-time 4 http://127.0.0.1:8080/healthz >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

wait_for_public_https() {
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 5 "https://${HOST}/healthz" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

rm -f "${APP_ROOT}/.current.next"
ln -s "${RELEASE_DIR}" "${APP_ROOT}/.current.next"
mv -Tf "${APP_ROOT}/.current.next" "${APP_ROOT}/current"

systemctl daemon-reload
if [[ "${LOCAL_RECOVERY_ENABLED}" == "1" ]]; then
  systemctl enable --now llama-local
  for _ in $(seq 1 120); do
    if curl -fsS http://127.0.0.1:11434/health >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  curl -fsS http://127.0.0.1:11434/health >/dev/null
else
  systemctl disable --now llama-local >/dev/null 2>&1 || true
fi

systemctl enable olivia
if ! systemctl restart olivia; then
  rollback_release
  echo "new 0liviA release failed to start; previous release restored" >&2
  exit 1
fi
if ! wait_for_core; then
  rollback_release
  echo "new 0liviA release failed health check; previous release restored" >&2
  exit 1
fi

# Direct-to-Oracle HTTPS. Cloudflare remains outside chat/voice/memory.
PUBLIC_IP=""
for _ in $(seq 1 30); do
  PUBLIC_IP="$(curl -4fsS --max-time 4 https://api.ipify.org 2>/dev/null || true)"
  [[ -n "${PUBLIC_IP}" ]] && break
  sleep 2
done
if [[ -z "${PUBLIC_IP}" ]]; then
  rollback_release
  echo "could not determine public IPv4; previous release restored" >&2
  exit 1
fi
HOST="${PUBLIC_IP}.nip.io"

cat > "${CADDY_FILE}" <<EOF
${HOST} {
  encode zstd gzip
  reverse_proxy 127.0.0.1:8080 {
    flush_interval -1
    header_up X-Olivia-Client-IP {http.request.remote.host}
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
if ! systemctl enable caddy || ! systemctl restart caddy; then
  rollback_release
  echo "public HTTPS proxy failed to start; previous release restored" >&2
  exit 1
fi
if ! wait_for_public_https; then
  rollback_release
  echo "public HTTPS health check failed; previous release restored" >&2
  exit 1
fi

cat > "${STATE_ROOT}/bootstrap-info" <<EOF
URL=https://${HOST}
REGISTRATION=first-run
SETUP_URL=https://${HOST}/#setup=${REGISTRATION_TOKEN}
LOCAL_RECOVERY_ENABLED=${LOCAL_RECOVERY_ENABLED}
MODEL_PROFILE=${MODEL_PROFILE}
MODEL=${MODEL_NAME}
MODEL_SHA256=${MODEL_SHA256}
RUNTIME=llama.cpp-${LLAMA_BUILD}
RUNTIME_SHA256=${llama_sha256}
COST_MODE=$( [[ "${LOCAL_RECOVERY_ENABLED}" == "1" ]] && printf 'local-recovery' || printf 'no-provider' )
SOURCE_REF=${SOURCE_SHA}
EOF
chown root:root "${STATE_ROOT}/bootstrap-info"
chmod 0600 "${STATE_ROOT}/bootstrap-info"
unset TOKEN REGISTRATION_TOKEN

curl -fsS http://127.0.0.1:8080/healthz
echo
echo "0liviA bootstrap complete: https://${HOST}"
