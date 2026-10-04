#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/simondalmasso/0liviA.git}"
REF="${REF:-arch/gpt-synthesis-v1}"
APP_ROOT="${APP_ROOT:-/opt/0livia}"
STATE_ROOT="${STATE_ROOT:-/var/lib/0livia}"
ETC_ROOT="${ETC_ROOT:-/etc/0livia}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends git python3 python3-venv python3-pip ca-certificates curl caddy

if ! id olivia >/dev/null 2>&1; then
  useradd --system --home "${STATE_ROOT}" --shell /usr/sbin/nologin olivia
fi

install -d -o olivia -g olivia -m 0700 "${STATE_ROOT}"
install -d -o root -g root -m 0755 "${APP_ROOT}"
install -d -o root -g olivia -m 0750 "${ETC_ROOT}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone --filter=blob:none --branch "${REF}" "${REPO_URL}" "${tmp}/repo"
git -C "${tmp}/repo" rev-parse HEAD

rm -rf "${APP_ROOT}/current"
install -d -o root -g root -m 0755 "${APP_ROOT}/current"
cp -a "${tmp}/repo/." "${APP_ROOT}/current/"
rm -rf "${APP_ROOT}/current/.git"

python3 -m venv "${APP_ROOT}/venv"
"${APP_ROOT}/venv/bin/pip" install --upgrade pip
"${APP_ROOT}/venv/bin/pip" install "${APP_ROOT}/current"

install -o root -g root -m 0644 "${APP_ROOT}/current/deploy/0livia.service" /etc/systemd/system/0livia.service

if [[ ! -f "${ETC_ROOT}/olivia.env" ]]; then
  install -o root -g olivia -m 0600 "${APP_ROOT}/current/deploy/olivia.env.example" "${ETC_ROOT}/olivia.env"
  echo "Created ${ETC_ROOT}/olivia.env. Fill token/providers before starting 0liviA." >&2
fi

systemctl daemon-reload
systemctl enable olivia.service

echo "Installed code. Next:"
echo "  1. edit ${ETC_ROOT}/olivia.env"
echo "  2. install /etc/caddy/Caddyfile from deploy/Caddyfile.example with OLIVIA_PUBLIC_HOST/ACME_EMAIL env"
echo "  3. systemctl restart caddy olivia"
echo "  4. deploy/smoke.sh https://YOUR_HOST YOUR_TOKEN"
