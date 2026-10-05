#!/usr/bin/env bash
set -euo pipefail
umask 077

INPUT="${1:-}"
TARGET="${OLIVIA_RESTORE_TARGET:-/var/lib/0livia/olivia.sqlite3}"
PASSPHRASE="${OLIVIA_BACKUP_PASSPHRASE:-}"
ALLOW_OVERWRITE="${OLIVIA_RESTORE_OVERWRITE:-0}"
SERVICE_NAME="${OLIVIA_SERVICE_NAME:-olivia}"

if [[ -z "${INPUT}" || ! -f "${INPUT}" ]]; then
  echo "encrypted backup path is required" >&2
  exit 2
fi
if [[ -z "${PASSPHRASE}" || "${#PASSPHRASE}" -lt 16 ]]; then
  echo "OLIVIA_BACKUP_PASSPHRASE must be at least 16 characters" >&2
  exit 2
fi
if [[ -f "${INPUT}.sha256" ]]; then
  read -r expected_hash _ < "${INPUT}.sha256"
  actual_hash="$(sha256sum "${INPUT}" | awk '{print $1}')"
  if [[ ! "${expected_hash}" =~ ^[0-9a-fA-F]{64}$ ]] || [[ "${actual_hash}" != "${expected_hash,,}" ]]; then
    echo "backup checksum verification failed" >&2
    exit 2
  fi
fi
if [[ -e "${TARGET}" && "${ALLOW_OVERWRITE}" != "1" ]]; then
  echo "target exists; set OLIVIA_RESTORE_OVERWRITE=1 after taking an encrypted backup" >&2
  exit 2
fi

tmpdir="$(mktemp -d)"
restart_service=0
cleanup() {
  rm -rf "${tmpdir}"
  if [[ "${restart_service}" == "1" ]]; then
    systemctl start "${SERVICE_NAME}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
plain="${tmpdir}/restore.sqlite3"

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 \
  -pass env:OLIVIA_BACKUP_PASSPHRASE \
  -in "${INPUT}" -out "${plain}"

python3 - "${plain}" <<'PY'
import sqlite3
import sys

path = sys.argv[1]
conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
try:
    row = conn.execute("PRAGMA integrity_check").fetchone()
    if not row or row[0] != "ok":
        raise SystemExit("restore integrity_check failed")
finally:
    conn.close()
PY

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
  systemctl stop "${SERVICE_NAME}"
  restart_service=1
fi

mkdir -p "$(dirname "${TARGET}")"
rm -f "${TARGET}-wal" "${TARGET}-shm"
install -m 0600 "${plain}" "${TARGET}"
if id olivia >/dev/null 2>&1; then
  chown olivia:olivia "${TARGET}"
fi
printf '%s\n' "${TARGET}"
