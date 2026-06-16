#!/usr/bin/env bash
# Deploy Bugis HA stack to all nodes defined in deploy/ha/inventory.env
#
# Prerequisites on each target host:
#   - Docker Engine 24+ and Docker Compose v2
#   - Open ports per role (see docs/ha-deployment.md)
#   - SSH key or HA_SSH_PASSWORD
#
# Usage:
#   cp deploy/ha/inventory.env.example deploy/ha/inventory.env   # edit
#   # or: ./scripts/ha/generate-inventory.sh
#   source deploy/ha/inventory.env && ./scripts/ha/deploy-ha.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/ha/lib.sh"

INVENTORY="${ROOT}/deploy/ha/inventory.env"
if [[ -f "$INVENTORY" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$INVENTORY" && set +a
fi

: "${HA_DB_HOST:?set HA_DB_HOST in deploy/ha/inventory.env}"
: "${HA_APP_HOSTS:?set HA_APP_HOSTS}"
: "${HA_LB_HOSTS:?set HA_LB_HOSTS}"
: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}"
: "${BUGIS_SECRET_KEY:?set BUGIS_SECRET_KEY}"

ARCHIVE="/tmp/bugis-ha-src.tar.gz"
ha_package_source "$ARCHIVE" "$ROOT"

IFS=',' read -r -a APP_HOSTS <<<"${HA_APP_HOSTS}"
IFS=',' read -r -a LB_HOSTS <<<"${HA_LB_HOSTS}"

DB_URL="postgresql+psycopg://${POSTGRES_USER:-bugis}:${POSTGRES_PASSWORD}@${HA_DB_HOST}:${HA_DB_PORT:-5432}/${POSTGRES_DB:-bugis}"

echo "==> [1/4] Deploy PostgreSQL primary on ${HA_DB_HOST}"
"${ROOT}/scripts/ha/deploy-db.sh" "$HA_DB_HOST"

if [[ -n "${HA_DB_STANDBY_HOST:-}" ]]; then
  echo "==> [1b] DB standby ${HA_DB_STANDBY_HOST} — configure streaming replica manually (see docs/ha-deployment.md)"
fi

echo "==> [2/4] Deploy application nodes"
idx=0
for host in "${APP_HOSTS[@]}"; do
  host="$(echo "$host" | xargs)"
  [[ -z "$host" ]] && continue
  idx=$((idx + 1))
  if [[ "$idx" -eq 1 ]]; then
    SCHED=true
    MIGRATE=true
    NODE_ID="bugis-app-${idx}"
  else
    SCHED=false
    MIGRATE=false
    NODE_ID="bugis-app-${idx}"
  fi
  "${ROOT}/scripts/ha/deploy-app.sh" "$host" "$idx" "$SCHED" "$MIGRATE" "$NODE_ID" "$DB_URL"
done

if [[ -n "${HA_OBS_HOST:-}" ]]; then
  echo "==> [3/4] Deploy observability on ${HA_OBS_HOST}"
  "${ROOT}/scripts/ha/deploy-obs.sh" "$HA_OBS_HOST" "${APP_HOSTS[@]}"
else
  echo "==> [3/4] Skip observability (HA_OBS_HOST empty)"
fi

echo "==> [4/4] Deploy load balancer(s)"
for lb in "${LB_HOSTS[@]}"; do
  lb="$(echo "$lb" | xargs)"
  [[ -z "$lb" ]] && continue
  "${ROOT}/scripts/ha/deploy-lb.sh" "$lb" "${APP_HOSTS[@]}"
done

rm -f "$ARCHIVE"

ENTRY="${LB_HOSTS[0]}"
ENTRY="$(echo "$ENTRY" | xargs)"
echo ""
echo "HA deploy finished."
echo "  Entry: http://${ENTRY}:${HA_LB_HTTP_PORT:-80}/"
echo "  Health: http://${ENTRY}:${HA_LB_HTTP_PORT:-80}/health"
echo "  Verify: source deploy/ha/inventory.env && ./scripts/ha/verify-ha.sh"
