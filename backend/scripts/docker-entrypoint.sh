#!/usr/bin/env sh
set -eu

if [ "${BUGIS_RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "==> alembic upgrade head"
  alembic upgrade head
fi

if [ "${BUGIS_RUN_SEED:-true}" = "true" ]; then
  echo "==> seed baseline catalog"
  python -m scripts.seed
fi

if [ "${BUGIS_RUN_DEMO:-true}" = "true" ]; then
  echo "==> ensure demo fixtures"
  python -m scripts.ensure_demo
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
