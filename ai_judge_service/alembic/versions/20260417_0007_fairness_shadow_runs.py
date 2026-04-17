"""add fairness shadow runs table

Revision ID: 20260417_0007
Revises: 20260416_0006
Create Date: 2026-04-17 05:30:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260417_0007"
down_revision = "20260416_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fairness_shadow_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=96), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False, server_default="fairness-benchmark-v1"),
        sa.Column("benchmark_run_id", sa.String(length=96), nullable=True),
        sa.Column("environment_mode", sa.String(length=32), nullable=False, server_default="blocked"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_data"),
        sa.Column("threshold_decision", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("needs_real_env_reconfirm", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("needs_remediation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("winner_flip_rate", sa.Float(), nullable=True),
        sa.Column("score_shift_delta", sa.Float(), nullable=True),
        sa.Column("review_required_delta", sa.Float(), nullable=True),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("reported_by", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_fairness_shadow_runs_run_id"),
    )
    op.create_index(
        "ix_fairness_shadow_runs_policy_reported",
        "fairness_shadow_runs",
        ["policy_version", "reported_at"],
        unique=False,
    )
    op.create_index(
        "ix_fairness_shadow_runs_status_reported",
        "fairness_shadow_runs",
        ["status", "reported_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fairness_shadow_runs_status_reported", table_name="fairness_shadow_runs")
    op.drop_index("ix_fairness_shadow_runs_policy_reported", table_name="fairness_shadow_runs")
    op.drop_table("fairness_shadow_runs")
