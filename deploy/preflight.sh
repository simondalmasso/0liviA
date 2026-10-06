#!/usr/bin/env bash
set -euo pipefail

MIN_MEMORY_MB="${OLIVIA_PREFLIGHT_MIN_MEMORY_MB:-768}"
MIN_DISK_MB="${OLIVIA_PREFLIGHT_MIN_DISK_MB:-4096}"

fail() {
  printf 'PREFLIGHT_FAIL=%s\n' "$1" >&2
  exit 1
}

[[ "$(uname -s)" == "Linux" ]] || fail "linux_required"

arch="$(uname -m)"
case "$arch" in
  x86_64|aarch64) ;;
  *) fail "unsupported_architecture_${arch}" ;;
esac

command -v bash >/dev/null 2>&1 || fail "bash_missing"
command -v apt-get >/dev/null 2>&1 || fail "apt_get_missing"
command -v systemctl >/dev/null 2>&1 || fail "systemd_missing"

if [[ "${EUID}" -eq 0 ]]; then
  privilege="root"
else
  command -v sudo >/dev/null 2>&1 || fail "sudo_missing"
  sudo -n true >/dev/null 2>&1 || fail "passwordless_sudo_required"
  privilege="sudo-nopasswd"
fi

mem_kb="$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo)"
[[ "$mem_kb" =~ ^[0-9]+$ ]] || fail "memory_probe_failed"
mem_mb="$(( mem_kb / 1024 ))"
(( mem_mb >= MIN_MEMORY_MB )) || fail "memory_below_${MIN_MEMORY_MB}mb"

disk_mb="$(df -Pm / | awk 'NR==2 {print $4}')"
[[ "$disk_mb" =~ ^[0-9]+$ ]] || fail "disk_probe_failed"
(( disk_mb >= MIN_DISK_MB )) || fail "disk_below_${MIN_DISK_MB}mb"

swap_required="NO"
if (( mem_kb < 2 * 1024 * 1024 )); then
  swap_required="YES"
  command -v fallocate >/dev/null 2>&1 || fail "fallocate_missing_for_micro"
  command -v mkswap >/dev/null 2>&1 || fail "mkswap_missing_for_micro"
  command -v swapon >/dev/null 2>&1 || fail "swapon_missing_for_micro"
fi

printf 'PREFLIGHT_OK=YES\n'
printf 'ARCH=%s\n' "$arch"
printf 'MEMORY_MB=%s\n' "$mem_mb"
printf 'DISK_FREE_MB=%s\n' "$disk_mb"
printf 'PRIVILEGE=%s\n' "$privilege"
printf 'SWAP_REQUIRED=%s\n' "$swap_required"
