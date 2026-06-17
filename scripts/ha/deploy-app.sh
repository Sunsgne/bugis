#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/ha/lib.sh"

HOST="${1:?app host}"
INDEX="${2:-1}"
SCHED="${3:-false}"
MIGRATE="${4:-false}"
NODE_ID="${5:-bugis-app-1}"
DB_URL="${6:?database url}"

REMOTE="$(ha_remote_dir)"
ARCHIVE="/tmp/bugis-ha-src.tar.gz"

[[ -f "$ARCHIVE" ]] || ha_package_source "$ARCHIVE" "$ROOT"

ENV_FILE="$(mktemp)"
cat >"$ENV_FILE" <<EOF
BUGIS_DATABASE_URL=${DB_URL}
BUGIS_SECRET_KEY=${BUGIS_SECRET_KEY}
BUGIS_DRY_RUN=${BUGIS_DRY_RUN:-false}
BUGIS_SCHEDULER_ENABLED=${SCHED}
BUGIS_SCHEDULER_INTERVAL_SECONDS=${BUGIS_SCHEDULER_INTERVAL_SECONDS:-30}
BUGIS_CONTROLLER_NODE_ID=${NODE_ID}
BUGIS_RUN_MIGRATIONS=${MIGRATE}
BUGIS_RUN_SEED=${BUGIS_RUN_SEED:-false}
BUGIS_RUN_DEMO=${BUGIS_RUN_DEMO:-false}
BUGIS_EXPOSE_OPENAPI=false
HA_APP_HTTP_PORT=${HA_APP_HTTP_PORT:-3300}
HA_APP_METRICS_BIND=${HA_APP_METRICS_BIND:-127.0.0.1}
HA_APP_METRICS_PORT=8000
EOF

ha_ssh "$HOST" "mkdir -p '$REMOTE'"
ha_scp "$ARCHIVE" "${HA_SSH_USER:-root}@${HOST}:${REMOTE}/bugis-ha-src.tar.gz"
ha_scp "$ENV_FILE" "${HA_SSH_USER:-root}@${HOST}:${REMOTE}/app.env"
rm -f "$ENV_FILE"

ha_ssh "$HOST" "cd '$REMOTE' && \
  tar -xzf bugis-ha-src.tar.gz && \
  docker compose -f docker-compose.ha-app.yml --env-file app.env up -d --build && \
  rm -f bugis-ha-src.tar.gz"

echo "App node ${INDEX} ready on ${HOST}:${HA_APP_HTTP_PORT:-3300} (scheduler=${SCHED}, migrate=${MIGRATE})"
