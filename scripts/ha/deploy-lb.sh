#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/ha/lib.sh"

LB_HOST="${1:?lb host}"
shift
APP_HOSTS=("$@")

REMOTE="$(ha_remote_dir)"
ARCHIVE="/tmp/bugis-ha-src.tar.gz"
[[ -f "$ARCHIVE" ]] || ha_package_source "$ARCHIVE" "$ROOT"

UPSTREAM=""
for h in "${APP_HOSTS[@]}"; do
  h="$(echo "$h" | xargs)"
  [[ -z "$h" ]] && continue
  UPSTREAM="${UPSTREAM}    server ${h}:${HA_APP_HTTP_PORT:-3300} max_fails=3 fail_timeout=30s;"$'\n'
done

SERVER_NAME="${HA_PUBLIC_URL:-_}"
SERVER_NAME="${SERVER_NAME#https://}"
SERVER_NAME="${SERVER_NAME#http://}"
SERVER_NAME="${SERVER_NAME%%/*}"
[[ -z "$SERVER_NAME" ]] && SERVER_NAME="_"

CONF="$(mktemp)"
sed -e "s|@UPSTREAM_SERVERS@|${UPSTREAM}|g" \
    -e "s|@SERVER_NAME@|${SERVER_NAME}|g" \
    "${ROOT}/deploy/ha/lb/nginx.conf.template" >"$CONF"

ha_ssh "$LB_HOST" "mkdir -p '$REMOTE/lb'"
ha_scp "$CONF" "${HA_SSH_USER:-root}@${LB_HOST}:${REMOTE}/lb/nginx.conf"
rm -f "$CONF"

ha_ssh "$LB_HOST" "docker rm -f bugis-ha-lb 2>/dev/null || true; \
  docker run -d --name bugis-ha-lb --restart unless-stopped \
    -p ${HA_LB_HTTP_PORT:-80}:80 \
    -v '${REMOTE}/lb/nginx.conf:/etc/nginx/conf.d/default.conf:ro' \
    nginx:alpine && docker exec bugis-ha-lb nginx -t"

echo "LB ready on ${LB_HOST}:${HA_LB_HTTP_PORT:-80}"
