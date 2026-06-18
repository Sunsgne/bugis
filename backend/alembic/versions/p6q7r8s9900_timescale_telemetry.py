"""TimescaleDB hypertable + 5m continuous aggregate for telemetry_samples.

Revision ID: p6q7r8s9900
Revises: o5p6q7r8800
Create Date: 2026-06-18

Designed for ~10k active circuits: raw samples retained 14d, 5-minute rollups 400d.
"""

from __future__ import annotations

from alembic import op

revision = "p6q7r8s9900"
down_revision = "o5p6q7r8800_telemetry_idx"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def _timescale_available() -> bool:
    if not _is_postgres():
        return False
    bind = op.get_bind()
    row = bind.execute(
        __import__("sqlalchemy").text(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb' LIMIT 1"
        )
    ).fetchone()
    return row is not None


def upgrade() -> None:
    if not _is_postgres() or not _timescale_available():
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.execute(
        """
        SELECT create_hypertable(
          'telemetry_samples', 'created_at',
          if_not_exists => TRUE,
          migrate_data => TRUE
        );
        """
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_samples_5m
        WITH (timescaledb.continuous) AS
        SELECT
          time_bucket('5 minutes', created_at) AS bucket,
          circuit_id,
          source,
          MAX(rx_mbps) AS max_rx_mbps,
          MAX(tx_mbps) AS max_tx_mbps,
          AVG(rx_mbps) AS avg_rx_mbps,
          AVG(tx_mbps) AS avg_tx_mbps,
          MAX(latency_ms) AS max_latency_ms,
          AVG(latency_ms) AS avg_latency_ms,
          COUNT(*) AS sample_count
        FROM telemetry_samples
        GROUP BY bucket, circuit_id, source
        WITH NO DATA;
        """
    )

    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
          'telemetry_samples_5m',
          start_offset => INTERVAL '3 hours',
          end_offset => INTERVAL '5 minutes',
          schedule_interval => INTERVAL '5 minutes',
          if_not_exists => TRUE
        );
        """
    )

    op.execute(
        """
        SELECT add_retention_policy(
          'telemetry_samples',
          INTERVAL '14 days',
          if_not_exists => TRUE
        );
        """
    )

    op.execute(
        """
        SELECT add_retention_policy(
          'telemetry_samples_5m',
          INTERVAL '400 days',
          if_not_exists => TRUE
        );
        """
    )


def downgrade() -> None:
    if not _is_postgres() or not _timescale_available():
        return

    op.execute(
        "SELECT remove_retention_policy('telemetry_samples_5m', if_exists => true)"
    )
    op.execute(
        "SELECT remove_retention_policy('telemetry_samples', if_exists => true)"
    )
    op.execute(
        """
        SELECT remove_continuous_aggregate_policy('telemetry_samples_5m', if_exists => true)
        """
    )
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_samples_5m CASCADE")
