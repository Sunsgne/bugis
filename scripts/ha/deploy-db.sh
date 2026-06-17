#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/ha/lib.sh"

HOST="${1:?db host}"
REMOTE="$(ha_remote_dir)"
ARCHIVE="/tmp/bugis-ha-src.tar.gz"

[[ -f "$ARCHIVE" ]] || ha_package_source "$ARCHIVE" "$ROOT"

ENV_FILE="$(mktemp)"
cat >"$ENV_FILE" <<EOF
POSTGRES_USER=${POSTGRES_USER:-bugis}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB:-bugis}
HA_DB_PORT=${HA_DB_PORT:-5432}
HA_DB_BIND=${HA_DB_BIND:-127.0.0.1}
EOF

ha_ssh "$HOST" "mkdir -p '$REMOTE'"
ha_scp "$ARCHIVE" "${HA_SSH_USER:-root}@${HOST}:${REMOTE}/bugis-ha-src.tar.gz"
ha_scp "$ENV_FILE" "${HA_SSH_USER:-root}@${HOST}:${REMOTE}/db.env"
rm -f "$ENV_FILE"

ha_ssh "$HOST" "cd '$REMOTE' && \
  tar -xzf bugis-ha-src.tar.gz && \
  docker compose -f docker-compose.ha-db.yml --env-file db.env up -d && \
  rm -f bugis-ha-src.tar.gz"

echo "DB primary ready on ${HOST}:${HA_DB_PORT:-5432}"
