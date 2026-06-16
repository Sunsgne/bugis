#!/usr/bin/env bash
# Shared SSH helpers for HA deployment scripts.
set -euo pipefail

ha_ssh_opts() {
  echo "-o StrictHostKeyChecking=accept-new -p ${HA_SSH_PORT:-22}"
}

ha_ssh() {
  local host="$1"
  shift
  local opts
  opts=$(ha_ssh_opts)
  # shellcheck disable=SC2086
  if [[ -n "${HA_SSH_PASSWORD:-}" ]]; then
    command -v sshpass >/dev/null || { echo "sshpass required when HA_SSH_PASSWORD is set" >&2; exit 1; }
    sshpass -p "$HA_SSH_PASSWORD" ssh $opts "${HA_SSH_USER:-root}@${host}" "$@"
  else
    ssh $opts "${HA_SSH_USER:-root}@${host}" "$@"
  fi
}

ha_scp() {
  local src="$1" dest="$2"
  local opts
  opts=$(ha_ssh_opts)
  # shellcheck disable=SC2086
  if [[ -n "${HA_SSH_PASSWORD:-}" ]]; then
    sshpass -p "$HA_SSH_PASSWORD" scp $opts "$src" "$dest"
  else
    scp $opts "$src" "$dest"
  fi
}

ha_package_source() {
  local archive="$1"
  local root="$2"
  tar -czf "$archive" \
    --exclude='./.git' \
    --exclude='./node_modules' \
    --exclude='./frontend/node_modules' \
    --exclude='./frontend/dist' \
    --exclude='./backend/.pytest_cache' \
    --exclude='./deploy/demo.env' \
    --exclude='./deploy/ha/inventory.env' \
    --exclude='./*.db' \
    --exclude='./backend/*.db' \
    -C "$root" .
}

ha_remote_dir() {
  echo "${HA_REMOTE_DIR:-/opt/bugis}"
}
