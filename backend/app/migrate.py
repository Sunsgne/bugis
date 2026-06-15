"""Run Alembic migrations at application startup (idempotent)."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Apply pending DB migrations. Safe to call on every process start."""
    import os

    if os.environ.get("BUGIS_SKIP_MIGRATE") == "1":
        return
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError as exc:  # pragma: no cover
        logger.warning("alembic not available: %s", exc)
        return

    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    if not ini.exists():
        logger.warning("alembic.ini not found at %s", ini)
        return

    cfg = Config(str(ini))
    command.upgrade(cfg, "head")
    logger.info("database migrations applied")
