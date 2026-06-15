#!/usr/bin/env bash
# Post-deploy smoke checks for Bugis demo (local or remote URL).
set -euo pipefail

BASE="${1:-http://203.117.117.196:3300}"
USER="${BUGIS_DEMO_USER:-admin}"
PASS="${BUGIS_DEMO_PASS:-admin123}"

echo "==> Health $BASE/health"
curl -fsS "$BASE/health" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok', d"

echo "==> Login"
TOKEN=$(curl -sS -X POST "$BASE/api/v1/auth/login" \
  -d "username=$USER&password=$PASS" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH=(-H "Authorization: Bearer $TOKEN")

check() {
  local path="$1"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" "${AUTH[@]}" "$BASE$path")
  echo "  $path -> $code"
  [[ "$code" == "200" ]] || { echo "FAIL $path"; exit 1; }
}

echo "==> Core APIs"
check "/api/v1/circuits?page=1&page_size=10"
check "/api/v1/devices?page=1&page_size=10"
check "/api/v1/system/settings"
check "/api/v1/system/snmp"
check "/api/v1/system/snmp/mibs"
check "/api/v1/system/branding"
check "/api/v1/telemetry/dashboard"

echo "==> Active circuits"
python3 - <<PY
import json, urllib.request
req = urllib.request.Request("$BASE/api/v1/circuits?page=1&page_size=50", headers={"Authorization": "Bearer $TOKEN"})
data = json.load(urllib.request.urlopen(req))
active = [c for c in data["items"] if c.get("status") == "active"]
print(f"  circuits total={data['total']} active={len(active)}")
assert data["total"] > 0, "expected seeded circuits"
PY

echo "OK — demo smoke passed ($BASE)"
