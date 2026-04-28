"""add fairness calibration decision log

Revision ID: 20260428_0010
Revises: 20260425_0009
Create Date: 2026-04-28 12:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260428_0010"
down_revision = "20260425_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fairness_calibration_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.String(length=96), nullable=False),
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("source_recommendation_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.JSON(), nullable=False),
        sa.Column("reason_code", sa.String(length=96), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("visibility", sa.JSON(), nullable=False),
        sa.Column("release_gate_input", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_id",
            name="uq_fairness_calibration_decisions_decision_id",
        ),
    )
    op.create_index(
        "ix_fairness_calibration_decisions_policy_created",
        "fairness_calibration_decisions",
        ["policy_version", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_fairness_calibration_decisions_source_created",
        "fairness_calibration_decisions",
        ["source_recommendation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_fairness_calibration_decisions_decision_created",
        "fairness_calibration_decisions",
        ["decision", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fairness_calibration_decisions_decision_created",
        table_name="fairness_calibration_decisions",
    )
    op.drop_index(
        "ix_fairness_calibration_decisions_source_created",
        table_name="fairness_calibration_decisions",
    )
    op.drop_index(
        "ix_fairness_calibration_decisions_policy_created",
        table_name="fairness_calibration_decisions",
    )
    op.drop_table("fairness_calibration_decisions")
