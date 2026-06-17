#!/usr/bin/env bash
# Post-deploy smoke checks for Bugis demo (local or remote URL).
set -euo pipefail

BASE="${1:?usage: verify-demo.sh <base-url>}"
USER="${BUGIS_DEMO_USER:-admin}"
PASS="${BUGIS_DEMO_PASS:?set BUGIS_DEMO_PASS}"

echo "==> Health $BASE/health"
curl -fsS "$BASE/health" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok', d; assert d.get('dry_run') is False, 'demo must run with dry_run=false'"

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
check "/api/v1/system/info"
check "/api/v1/system/snmp"
check "/api/v1/system/snmp/mibs"
check "/api/v1/system/branding"
check "/api/v1/telemetry/dashboard"

echo "==> Production data mode"
python3 - <<PY
import json, urllib.request
req = urllib.request.Request("$BASE/api/v1/system/info", headers={"Authorization": "Bearer $TOKEN"})
info = json.load(urllib.request.urlopen(req))
assert info.get("dry_run") is False, info
assert info.get("telemetry_simulation") is False, info
assert info.get("production_data_mode") is True, info
assert info.get("app_env") == "production", info
print("  production_data_mode OK")
PY

echo "==> Active circuits + probe"
DEMO_CLEAN="${BUGIS_DEMO_CLEAN:-false}" python3 - <<PY
import json, os, urllib.request
clean = os.environ.get("DEMO_CLEAN") == "true"
req = urllib.request.Request("$BASE/api/v1/circuits?page=1&page_size=50", headers={"Authorization": "Bearer $TOKEN"})
data = json.load(urllib.request.urlopen(req))
active = [c for c in data["items"] if c.get("status") == "active"]
print(f"  circuits total={data['total']} active={len(active)}")
if clean:
    assert data["total"] == 0, f"clean demo must have no circuits, got {data['total']}"
    print("  clean demo OK (no temporary data)")
else:
    assert data["total"] > 0, "expected seeded circuits"
if active:
    cid = active[0]["id"]
    probe_req = urllib.request.Request(
        f"$BASE/api/v1/circuits/{cid}/probe",
        headers={"Authorization": "Bearer $TOKEN"},
        method="POST",
        data=b"",
    )
    probe = json.load(urllib.request.urlopen(probe_req))
    assert probe.get("mode") == "live", probe
    print(f"  probe {active[0]['code']} mode={probe.get('mode')} method={probe.get('probe_method')}")
PY

echo "OK — demo smoke passed ($BASE)"
