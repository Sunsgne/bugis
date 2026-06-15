#!/usr/bin/env bash
# Deploy production-grade Bugis demo stack (docker-compose.demo.yml).
#
# Stack: PostgreSQL 16 + backend + frontend + Prometheus + Grafana
#   UI:         http://<host>:3300/
#   Prometheus: http://<host>:3309/
#   Grafana:    http://<host>:3303/
#
# Required (pick one auth method):
#   DEMO_SSH_PASSWORD=...     uses sshpass
#   or default SSH key for DEMO_SSH_USER@DEMO_SSH_HOST
#
# Optional — copy deploy/demo.env.example to deploy/demo.env (recommended):
#   POSTGRES_PASSWORD, BUGIS_SECRET_KEY, GRAFANA_ADMIN_PASSWORD, SSH settings
#
# Usage:
#   cp deploy/demo.env.example deploy/demo.env   # edit secrets
#   source deploy/demo.env && ./scripts/deploy-demo.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/deploy/demo.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$ENV_FILE" && set +a
fi

HOST="${DEMO_SSH_HOST:-203.117.117.196}"
PORT="${DEMO_SSH_PORT:-2333}"
USER="${DEMO_SSH_USER:-root}"
REMOTE_DIR="${DEMO_REMOTE_DIR:-/root/bugis}"
ARCHIVE="/tmp/bugis-demo-src.tar.gz"

POSTGRES_USER="${POSTGRES_USER:-bugis}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-bugis-demo-change-me}"
POSTGRES_DB="${POSTGRES_DB:-bugis}"
BUGIS_SECRET_KEY="${BUGIS_SECRET_KEY:-demo-change-me-use-long-random-string}"
BUGIS_DRY_RUN="${BUGIS_DRY_RUN:-false}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -p "$PORT")
SCP_OPTS=(-o StrictHostKeyChecking=accept-new -P "$PORT")

run_ssh() {
  if [[ -n "${DEMO_SSH_PASSWORD:-}" ]]; then
    command -v sshpass >/dev/null || { echo "sshpass required when DEMO_SSH_PASSWORD is set"; exit 1; }
    sshpass -p "$DEMO_SSH_PASSWORD" ssh "${SSH_OPTS[@]}" "$USER@$HOST" "$@"
  else
    ssh "${SSH_OPTS[@]}" "$USER@$HOST" "$@"
  fi
}

run_scp() {
  if [[ -n "${DEMO_SSH_PASSWORD:-}" ]]; then
    sshpass -p "$DEMO_SSH_PASSWORD" scp "${SCP_OPTS[@]}" "$@"
  else
    scp "${SCP_OPTS[@]}" "$@"
  fi
}

write_stack_env() {
  local dest="$1"
  cat >"$dest" <<EOF
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
BUGIS_SECRET_KEY=${BUGIS_SECRET_KEY}
BUGIS_DRY_RUN=${BUGIS_DRY_RUN:-false}
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
EOF
}

echo "==> Packaging source from $ROOT"
tar -czf "$ARCHIVE" \
  --exclude='./.git' \
  --exclude='./node_modules' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' \
  --exclude='./backend/.pytest_cache' \
  --exclude='./deploy/demo.env' \
  --exclude='./*.db' \
  --exclude='./backend/*.db' \
  -C "$ROOT" .

STACK_ENV="$(mktemp)"
write_stack_env "$STACK_ENV"

echo "==> Uploading to $USER@$HOST:$REMOTE_DIR"
run_ssh "mkdir -p '$REMOTE_DIR'"
run_scp "$ARCHIVE" "$USER@$HOST:$REMOTE_DIR/bugis-demo-src.tar.gz"
run_scp "$STACK_ENV" "$USER@$HOST:$REMOTE_DIR/.env"
rm -f "$STACK_ENV"

echo "==> Building and restarting demo containers (PostgreSQL + observability)"
run_ssh "cd '$REMOTE_DIR' && \
  cp .env /tmp/bugis-demo.env 2>/dev/null || true && \
  find . -mindepth 1 -maxdepth 1 ! -name 'bugis-demo-src.tar.gz' -exec rm -rf {} + && \
  tar -xzf bugis-demo-src.tar.gz && \
  cp /tmp/bugis-demo.env .env && \
  rm -f bugis-demo-src.tar.gz && \
  docker compose -f docker-compose.demo.yml --env-file .env build && \
  docker compose -f docker-compose.demo.yml --env-file .env up -d && \
  docker compose -f docker-compose.demo.yml --env-file .env exec -T backend python -m scripts.ensure_demo"

echo "==> Health check (allow time for migrations + seed on first boot)"
for i in $(seq 1 20); do
  if curl -fsS "http://${HOST}:3300/health" >/dev/null 2>&1; then
    TOKEN=$(curl -sS -X POST "http://${HOST}:3300/api/v1/auth/login" \
      -d 'username=admin&password=admin123' | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
    if [[ -n "$TOKEN" ]]; then
      CODE=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
        "http://${HOST}:3300/api/v1/circuits")
      if [[ "$CODE" == "200" ]]; then
        PROM_OK=""
        if curl -fsS "http://${HOST}:3309/-/ready" >/dev/null 2>&1; then
          PROM_OK=" Prometheus OK;"
        fi
        if [[ -x "$ROOT/scripts/verify-demo.sh" ]]; then
          echo "==> Running post-deploy smoke tests"
          BUGIS_DEMO_USER=admin BUGIS_DEMO_PASS=admin123 \
            "$ROOT/scripts/verify-demo.sh" "http://${HOST}:3300" || {
            echo "WARN: smoke tests failed (stack may still be starting)"
          }
        fi
        echo "Demo is up: http://${HOST}:3300/ (circuits API OK;${PROM_OK} Grafana http://${HOST}:3303/)"
        exit 0
      fi
      echo "WARN: health OK but /circuits returned $CODE (attempt $i)"
    fi
  fi
  sleep 5
done

echo "WARN: deploy finished but health check did not pass yet; check remote logs."
echo "  ssh -p $PORT $USER@$HOST 'cd $REMOTE_DIR && docker compose -f docker-compose.demo.yml --env-file .env logs --tail=80'"
echo "First upgrade from SQLite demo? Old volume bugis_data is unused; remove with:"
echo "  ssh -p $PORT $USER@$HOST 'docker volume rm bugis_bugis_data 2>/dev/null || true'"
