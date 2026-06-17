#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/ha/lib.sh"

HOST="${1:?obs host}"
shift
APP_HOSTS=("$@")

REMOTE="$(ha_remote_dir)"
ARCHIVE="/tmp/bugis-ha-src.tar.gz"
[[ -f "$ARCHIVE" ]] || ha_package_source "$ARCHIVE" "$ROOT"

TARGETS=""
for h in "${APP_HOSTS[@]}"; do
  h="$(echo "$h" | xargs)"
  [[ -z "$h" ]] && continue
  TARGETS="${TARGETS}          - ${h}:${HA_APP_METRICS_PORT:-8000}"$'\n'
done

PROM="${ROOT}/deploy/ha/prometheus/prometheus.ha.yml"
TMP_PROM="$(mktemp)"
sed "s|@TARGETS@|${TARGETS}|" "$PROM" >"$TMP_PROM"

ENV_FILE="$(mktemp)"
cat >"$ENV_FILE" <<EOF
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:?set GRAFANA_ADMIN_PASSWORD}
HA_PROMETHEUS_PORT=${HA_PROMETHEUS_PORT:-9090}
HA_GRAFANA_PORT=${HA_GRAFANA_PORT:-3000}
EOF

ha_ssh "$HOST" "mkdir -p '$REMOTE'"
ha_scp "$ARCHIVE" "${HA_SSH_USER:-root}@${HOST}:${REMOTE}/bugis-ha-src.tar.gz"
ha_scp "$ENV_FILE" "${HA_SSH_USER:-root}@${HOST}:${REMOTE}/obs.env"
ha_scp "$TMP_PROM" "${HA_SSH_USER:-root}@${HOST}:${REMOTE}/prometheus.ha.yml"
rm -f "$ENV_FILE" "$TMP_PROM"

ha_ssh "$HOST" "cd '$REMOTE' && tar -xzf bugis-ha-src.tar.gz && \
  mkdir -p deploy/ha/prometheus && mv prometheus.ha.yml deploy/ha/prometheus/prometheus.ha.yml && \
  docker compose -f docker-compose.ha-obs.yml --env-file obs.env up -d && \
  rm -f bugis-ha-src.tar.gz"

echo "Observability on ${HOST} (localhost only — SSH tunnel: -L 9090:127.0.0.1:9090 -L 3000:127.0.0.1:3000)"
