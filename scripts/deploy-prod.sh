#!/usr/bin/env bash
# Deploy single-node production Bugis stack (docker-compose.prod.yml).
#
# - Only frontend :443 is published (HTTPS, self-signed cert).
# - Backend / PostgreSQL / Prometheus / Grafana are internal-only.
#
# Usage:
#   cp deploy/prod.env.example deploy/prod.env   # set SSH host/password
#   ./scripts/deploy-prod.sh                     # auto-generates missing secrets
#
# Credentials are saved to deploy/prod.env and deploy/prod/credentials.txt (gitignored).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/deploy/prod.env"
CREDS_FILE="${ROOT}/deploy/prod/credentials.txt"
CERT_DIR="${ROOT}/deploy/prod/certs"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$ENV_FILE" && set +a
fi

HOST="${PROD_SSH_HOST:?set PROD_SSH_HOST (see deploy/prod.env.example)}"
PORT="${PROD_SSH_PORT:-22}"
USER="${PROD_SSH_USER:-root}"
REMOTE_DIR="${PROD_REMOTE_DIR:-/root/bugis-prod}"
ARCHIVE="/tmp/bugis-prod-src.tar.gz"

rand_secret() {
  python3 -c "import secrets; print(secrets.token_urlsafe(24))"
}

ensure_secret() {
  local var_name="$1"
  local current="${!var_name:-}"
  if [[ -z "$current" ]]; then
    current="$(rand_secret)"
    printf -v "$var_name" '%s' "$current"
    export "$var_name"
    GENERATED_SECRETS=true
  fi
}

GENERATED_SECRETS=false
POSTGRES_USER="${POSTGRES_USER:-bugis}"
ensure_secret POSTGRES_PASSWORD
POSTGRES_DB="${POSTGRES_DB:-bugis}"
ensure_secret BUGIS_SECRET_KEY
ensure_secret GRAFANA_ADMIN_PASSWORD
BUGIS_ADMIN_USER="${BUGIS_ADMIN_USER:-admin}"
ensure_secret BUGIS_ADMIN_PASS
BUGIS_PORTAL_USER="${BUGIS_PORTAL_USER:-portal}"
ensure_secret BUGIS_PORTAL_PASS
BUGIS_FIRST_SUPERUSER_PASSWORD="${BUGIS_FIRST_SUPERUSER_PASSWORD:-$BUGIS_ADMIN_PASS}"
ensure_secret BUGIS_WEBHOOK_TOKEN

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -p "$PORT")
SCP_OPTS=(-o StrictHostKeyChecking=accept-new -P "$PORT")

run_ssh() {
  if [[ -n "${PROD_SSH_PASSWORD:-}" ]]; then
    command -v sshpass >/dev/null || { echo "sshpass required when PROD_SSH_PASSWORD is set"; exit 1; }
    sshpass -p "$PROD_SSH_PASSWORD" ssh "${SSH_OPTS[@]}" "$USER@$HOST" "$@"
  else
    ssh "${SSH_OPTS[@]}" "$USER@$HOST" "$@"
  fi
}

run_scp() {
  if [[ -n "${PROD_SSH_PASSWORD:-}" ]]; then
    sshpass -p "$PROD_SSH_PASSWORD" scp "${SCP_OPTS[@]}" "$@"
  else
    scp "${SCP_OPTS[@]}" "$@"
  fi
}

write_local_env() {
  mkdir -p "$(dirname "$ENV_FILE")"
  cat >"$ENV_FILE" <<EOF
# Generated/updated by deploy-prod.sh — do not commit
PROD_SSH_HOST=${HOST}
PROD_SSH_PORT=${PORT}
PROD_SSH_USER=${USER}
PROD_SSH_PASSWORD=${PROD_SSH_PASSWORD:-}
PROD_REMOTE_DIR=${REMOTE_DIR}

POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
BUGIS_SECRET_KEY=${BUGIS_SECRET_KEY}
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
BUGIS_ADMIN_USER=${BUGIS_ADMIN_USER}
BUGIS_ADMIN_PASS=${BUGIS_ADMIN_PASS}
BUGIS_PORTAL_USER=${BUGIS_PORTAL_USER}
BUGIS_PORTAL_PASS=${BUGIS_PORTAL_PASS}
BUGIS_FIRST_SUPERUSER_PASSWORD=${BUGIS_FIRST_SUPERUSER_PASSWORD}
BUGIS_WEBHOOK_TOKEN=${BUGIS_WEBHOOK_TOKEN}
EOF
}

write_credentials() {
  mkdir -p "$(dirname "$CREDS_FILE")"
  local deployed_at
  deployed_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  cat >"$CREDS_FILE" <<EOF
Bugis Production Deployment
===========================
Deployed: ${deployed_at}
Host:     ${HOST}
URL:      https://${HOST}/

SSH
---
  Host:     ${HOST}
  Port:     ${PORT}
  User:     ${USER}
  Password: ${PROD_SSH_PASSWORD:-<key-based auth>}

TLS (self-signed, 10 years)
---------------------------
  Cert: deploy/prod/certs/cert.pem
  Key:  deploy/prod/certs/key.pem
  Note: browsers will warn until you trust the cert or replace with a real CA cert.

PostgreSQL (internal only)
--------------------------
  User:     ${POSTGRES_USER}
  Password: ${POSTGRES_PASSWORD}
  Database: ${POSTGRES_DB}

Platform Admin
--------------
  URL:      https://${HOST}/
  Username: ${BUGIS_ADMIN_USER}
  Password: ${BUGIS_ADMIN_PASS}

Tenant Portal
-------------
  URL:      https://${HOST}/portal
  Username: ${BUGIS_PORTAL_USER}
  Password: ${BUGIS_PORTAL_PASS}

Grafana (internal only — docker network)
----------------------------------------
  Username: admin
  Password: ${GRAFANA_ADMIN_PASSWORD}

JWT / App Secret (internal)
---------------------------
  BUGIS_SECRET_KEY: ${BUGIS_SECRET_KEY}

Remote directory: ${REMOTE_DIR}
Compose file:     docker-compose.prod.yml
EOF
}

generate_tls_certs() {
  mkdir -p "$CERT_DIR"
  if [[ -f "$CERT_DIR/cert.pem" && -f "$CERT_DIR/key.pem" ]]; then
    echo "==> TLS certs already exist at $CERT_DIR (reusing)"
    return
  fi
  echo "==> Generating 10-year self-signed TLS certificate for ${HOST}"
  openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/cert.pem" \
    -subj "/CN=${HOST}" \
    -addext "subjectAltName=DNS:${HOST},IP:${HOST}" 2>/dev/null \
    || openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
      -keyout "$CERT_DIR/key.pem" \
      -out "$CERT_DIR/cert.pem" \
      -subj "/CN=${HOST}"
  chmod 600 "$CERT_DIR/key.pem"
}

write_stack_env() {
  local dest="$1"
  cat >"$dest" <<EOF
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
BUGIS_SECRET_KEY=${BUGIS_SECRET_KEY}
BUGIS_APP_ENV=production
BUGIS_DEBUG=false
BUGIS_DRY_RUN=false
BUGIS_TELEMETRY_SIMULATION=false
BUGIS_SCHEDULER_INTERVAL_SECONDS=20
BUGIS_TELEMETRY_COLLECT_BATCH_SIZE=500
BUGIS_TELEMETRY_PROBE_BATCH_SIZE=50
BUGIS_REDIS_URL=redis://redis:6379/0
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
BUGIS_RUN_SEED=true
BUGIS_RUN_DEMO=false
BUGIS_PORTAL_USER=${BUGIS_PORTAL_USER}
BUGIS_PORTAL_PASS=${BUGIS_PORTAL_PASS}
BUGIS_FIRST_SUPERUSER_PASSWORD=${BUGIS_FIRST_SUPERUSER_PASSWORD}
BUGIS_WEBHOOK_TOKEN=${BUGIS_WEBHOOK_TOKEN}
EOF
}

if [[ "$GENERATED_SECRETS" == "true" ]]; then
  echo "==> Generated random secrets (saved to deploy/prod.env)"
fi
write_local_env
generate_tls_certs

# Pre-flight: never deploy a checkout whose migrations are BEHIND the live DB.
# (A behind branch makes alembic fail with "Can't locate revision", crash-looping
#  the backend.) Compare the live DB's current revision against local migrations.
echo "==> Pre-flight: checking local migrations vs live database revision"
REMOTE_REV="$(run_ssh "cd '$REMOTE_DIR' && docker compose -f docker-compose.prod.yml --env-file .env exec -T backend alembic current 2>/dev/null | tail -1 | awk '{print \$1}'" 2>/dev/null | tr -d '\r' || true)"
if [[ -n "$REMOTE_REV" && "$REMOTE_REV" != "None" ]]; then
  if ! grep -rqE "revision = ['\"]${REMOTE_REV}['\"]" "$ROOT/backend/alembic/versions/"; then
    echo "ERROR: live DB is at migration '$REMOTE_REV' which this checkout does NOT contain."
    echo "       Your branch is BEHIND the deployed database — deploying would crash the"
    echo "       backend with alembic \"Can't locate revision\". Aborting."
    echo "       Fix: git fetch origin main && git merge origin/main   (then re-run deploy)"
    exit 1
  fi
  echo "==> Migration check OK (live DB rev '$REMOTE_REV' present in this checkout)"
else
  echo "==> Migration check skipped (no live revision detected — fresh deploy?)"
fi

echo "==> Packaging source from $ROOT"
tar -czf "$ARCHIVE" \
  --exclude='./.git' \
  --exclude='./node_modules' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' \
  --exclude='./backend/.pytest_cache' \
  --exclude='./deploy/demo.env' \
  --exclude='./deploy/prod.env' \
  --exclude='./deploy/prod/credentials.txt' \
  --exclude='./*.db' \
  --exclude='./backend/*.db' \
  -C "$ROOT" .

STACK_ENV="$(mktemp)"
write_stack_env "$STACK_ENV"

echo "==> Uploading to $USER@$HOST:$REMOTE_DIR"
run_ssh "mkdir -p '$REMOTE_DIR/deploy/prod/certs'"
run_scp "$ARCHIVE" "$USER@$HOST:$REMOTE_DIR/bugis-prod-src.tar.gz"
run_scp "$STACK_ENV" "$USER@$HOST:$REMOTE_DIR/.env"
run_scp "$CERT_DIR/cert.pem" "$USER@$HOST:$REMOTE_DIR/deploy/prod/certs/cert.pem"
run_scp "$CERT_DIR/key.pem" "$USER@$HOST:$REMOTE_DIR/deploy/prod/certs/key.pem"
rm -f "$STACK_ENV"

echo "==> Building and starting production containers"
run_ssh "cd '$REMOTE_DIR' && \
  cp .env /tmp/bugis-prod.env 2>/dev/null || true && \
  find . -mindepth 1 -maxdepth 1 ! -name 'bugis-prod-src.tar.gz' -exec rm -rf {} + && \
  tar -xzf bugis-prod-src.tar.gz && \
  cp /tmp/bugis-prod.env .env && \
  rm -f bugis-prod-src.tar.gz && \
  mkdir -p deploy/prod/certs && \
  test -f deploy/prod/certs/cert.pem && test -f deploy/prod/certs/key.pem && \
  docker compose -f docker-compose.prod.yml --env-file .env build && \
  docker compose -f docker-compose.prod.yml --env-file .env up -d && \
  docker compose -f docker-compose.prod.yml --env-file .env exec -T backend \
    python -m scripts.reset_admin_password '${BUGIS_ADMIN_USER}' '${BUGIS_ADMIN_PASS}'"

write_credentials

echo "==> Health check (HTTPS on :443, allow time for first boot)"
BASE_URL="https://${HOST}"
for i in $(seq 1 30); do
  if curl -kfsS "${BASE_URL}/health" >/dev/null 2>&1; then
    TOKEN=$(curl -kfsS -X POST "${BASE_URL}/api/v1/auth/login" \
      -d "username=${BUGIS_ADMIN_USER}&password=${BUGIS_ADMIN_PASS}" \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
    if [[ -n "$TOKEN" ]]; then
      CODE=$(curl -kfsS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
        "${BASE_URL}/api/v1/circuits")
      if [[ "$CODE" == "200" ]]; then
        echo ""
        echo "Production is up: ${BASE_URL}/"
        echo ""
        cat "$CREDS_FILE"
        exit 0
      fi
      echo "WARN: health OK but /circuits returned $CODE (attempt $i)"
    fi
  fi
  sleep 5
done

echo "WARN: deploy finished but health check did not pass yet."
echo "Credentials saved to: $CREDS_FILE"
cat "$CREDS_FILE"
echo ""
echo "Check remote logs:"
echo "  ssh -p $PORT $USER@$HOST 'cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml --env-file .env logs --tail=80'"
exit 1
