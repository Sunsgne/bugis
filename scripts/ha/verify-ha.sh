#!/usr/bin/env bash
# Post-deploy smoke test for HA entry (via load balancer).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/ha/lib.sh"

INVENTORY="${ROOT}/deploy/ha/inventory.env"
if [[ -f "$INVENTORY" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$INVENTORY" && set +a
fi

LB="${1:-}"
if [[ -z "$LB" ]]; then
  IFS=',' read -r -a LB_HOSTS <<<"${HA_LB_HOSTS:?}"
  LB="$(echo "${LB_HOSTS[0]}" | xargs)"
fi

PORT="${HA_LB_HTTP_PORT:-80}"
BASE="http://${LB}:${PORT}"

echo "==> Health ${BASE}/health"
curl -fsS "${BASE}/health" | python3 -m json.tool

echo "==> Branding (public)"
curl -fsS "${BASE}/api/v1/system/branding" >/dev/null && echo OK

echo "==> Login"
TOKEN=$(curl -fsS -X POST "${BASE}/api/v1/auth/login/json" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token') or '')" 2>/dev/null || true)

if [[ -z "$TOKEN" ]]; then
  echo "WARN: default admin login failed — set password on leader app node or use MFA"
else
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "${BASE}/api/v1/circuits")
  echo "Circuits API -> ${CODE}"
fi

echo "==> Scheduler status (leader should be running)"
if [[ -n "${HA_APP_HOSTS:-}" ]]; then
  IFS=',' read -r -a APP_HOSTS <<<"$HA_APP_HOSTS"
  LEADER="$(echo "${APP_HOSTS[0]}" | xargs)"
  echo "Check leader app: ssh ${HA_SSH_USER:-root}@${LEADER} 'docker logs \$(docker ps -qf name=backend) 2>&1 | tail -5'"
fi

echo "HA verify done."
