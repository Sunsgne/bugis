#!/usr/bin/env bash
# Deploy Bugis demo stack to remote server (docker-compose.demo.yml).
#
# Required (pick one auth method):
#   DEMO_SSH_PASSWORD=...     uses sshpass
#   or default SSH key for DEMO_SSH_USER@DEMO_SSH_HOST
#
# Optional:
#   DEMO_SSH_HOST=203.117.117.196
#   DEMO_SSH_PORT=2333
#   DEMO_SSH_USER=root
#   DEMO_REMOTE_DIR=/root/bugis
#
# Usage:
#   ./scripts/deploy-demo.sh
#   DEMO_SSH_PASSWORD=xxx ./scripts/deploy-demo.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${DEMO_SSH_HOST:-203.117.117.196}"
PORT="${DEMO_SSH_PORT:-2333}"
USER="${DEMO_SSH_USER:-root}"
REMOTE_DIR="${DEMO_REMOTE_DIR:-/root/bugis}"
ARCHIVE="/tmp/bugis-demo-src.tar.gz"

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

echo "==> Packaging source from $ROOT"
tar -czf "$ARCHIVE" \
  --exclude='./.git' \
  --exclude='./node_modules' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' \
  --exclude='./backend/.pytest_cache' \
  --exclude='./*.db' \
  --exclude='./backend/*.db' \
  -C "$ROOT" .

echo "==> Uploading to $USER@$HOST:$REMOTE_DIR"
run_ssh "mkdir -p '$REMOTE_DIR'"
run_scp "$ARCHIVE" "$USER@$HOST:$REMOTE_DIR/bugis-demo-src.tar.gz"

echo "==> Building and restarting demo containers"
run_ssh "cd '$REMOTE_DIR' && tar -xzf bugis-demo-src.tar.gz && rm -f bugis-demo-src.tar.gz && docker compose -f docker-compose.demo.yml build && docker compose -f docker-compose.demo.yml up -d"

echo "==> Health check"
for i in 1 2 3 4 5 6 7 8 9 10; do
  if run_ssh "curl -fsS http://127.0.0.1:3300/ >/dev/null 2>&1 || curl -fsS http://localhost:3300/ >/dev/null 2>&1"; then
    echo "Demo is up: http://${HOST}:3300/"
    exit 0
  fi
  sleep 3
done

echo "WARN: deploy finished but health check did not pass yet; check remote logs."
echo "  ssh -p $PORT $USER@$HOST 'cd $REMOTE_DIR && docker compose -f docker-compose.demo.yml logs --tail=50'"
