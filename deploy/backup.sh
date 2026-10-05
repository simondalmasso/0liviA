#!/usr/bin/env bash
set -euo pipefail
umask 077

DB_PATH="${OLIVIA_DB_PATH:-/var/lib/0livia/olivia.sqlite3}"
BACKUP_DIR="${OLIVIA_BACKUP_DIR:-/var/lib/0livia/backups}"
PASSPHRASE="${OLIVIA_BACKUP_PASSPHRASE:-}"
OUT="${1:-}"

if [[ -z "${PASSPHRASE}" || "${#PASSPHRASE}" -lt 16 ]]; then
  echo "OLIVIA_BACKUP_PASSPHRASE must be at least 16 characters" >&2
  exit 2
fi
if [[ ! -f "${DB_PATH}" ]]; then
  echo "database not found: ${DB_PATH}" >&2
  exit 2
fi

if [[ -z "${OUT}" ]]; then
  mkdir -p "${BACKUP_DIR}"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  OUT="${BACKUP_DIR}/olivia-${stamp}.sqlite3.enc"
else
  mkdir -p "$(dirname "${OUT}")"
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT
snapshot="${tmpdir}/snapshot.sqlite3"

python3 - "${DB_PATH}" "${snapshot}" <<'PY'
import sqlite3
import sys

source, target = sys.argv[1:3]
src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
dst = sqlite3.connect(target)
try:
    src.backup(dst)
    row = dst.execute("PRAGMA integrity_check").fetchone()
    if not row or row[0] != "ok":
        raise SystemExit("backup integrity_check failed")
finally:
    dst.close()
    src.close()
PY

openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -md sha256 \
  -pass env:OLIVIA_BACKUP_PASSPHRASE \
  -in "${snapshot}" -out "${OUT}"
chmod 0600 "${OUT}"
checksum="$(sha256sum "${OUT}" | awk '{print $1}')"
printf '%s  %s\n' "${checksum}" "$(basename "${OUT}")" > "${OUT}.sha256"
chmod 0600 "${OUT}.sha256"
printf '%s\n' "${OUT}"
