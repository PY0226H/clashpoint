"""add judge trust registry snapshots table

Revision ID: 20260425_0009
Revises: 20260424_0008
Create Date: 2026-04-25 09:30:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260425_0009"
down_revision = "20260424_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "judge_trust_registry_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.BigInteger(), nullable=False),
        sa.Column("dispatch_type", sa.String(length=16), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column(
            "registry_version",
            sa.String(length=64),
            nullable=False,
            server_default="trust-registry-v1",
        ),
        sa.Column("case_commitment", sa.JSON(), nullable=False),
        sa.Column("verdict_attestation", sa.JSON(), nullable=False),
        sa.Column("challenge_review", sa.JSON(), nullable=False),
        sa.Column("kernel_version", sa.JSON(), nullable=False),
        sa.Column("audit_anchor", sa.JSON(), nullable=False),
        sa.Column("public_verify", sa.JSON(), nullable=False),
        sa.Column("component_hashes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "case_id",
            "dispatch_type",
            "trace_id",
            "registry_version",
            name="uq_judge_trust_registry_case_dispatch_trace_version",
        ),
    )
    op.create_index(
        "ix_judge_trust_registry_case_updated",
        "judge_trust_registry_snapshots",
        ["case_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_judge_trust_registry_trace",
        "judge_trust_registry_snapshots",
        ["trace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_judge_trust_registry_trace", table_name="judge_trust_registry_snapshots")
    op.drop_index(
        "ix_judge_trust_registry_case_updated",
        table_name="judge_trust_registry_snapshots",
    )
    op.drop_table("judge_trust_registry_snapshots")
