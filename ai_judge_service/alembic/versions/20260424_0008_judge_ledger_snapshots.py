"""add judge ledger snapshots table

Revision ID: 20260424_0008
Revises: 20260417_0007
Create Date: 2026-04-24 17:10:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260424_0008"
down_revision = "20260417_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "judge_ledger_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.BigInteger(), nullable=False),
        sa.Column("dispatch_type", sa.String(length=16), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("scope_id", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("rubric_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "judge_policy_version",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
        sa.Column("topic_domain", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("retrieval_profile", sa.String(length=64), nullable=True),
        sa.Column("case_dossier", sa.JSON(), nullable=False),
        sa.Column("claim_graph", sa.JSON(), nullable=False),
        sa.Column("evidence_ledger", sa.JSON(), nullable=False),
        sa.Column("verdict_ledger", sa.JSON(), nullable=False),
        sa.Column("fairness_report", sa.JSON(), nullable=False),
        sa.Column("opinion_pack", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "case_id",
            "dispatch_type",
            "judge_policy_version",
            "rubric_version",
            name="uq_judge_ledger_snapshots_case_dispatch_policy_rubric",
        ),
    )
    op.create_index(
        "ix_judge_ledger_snapshots_case_updated",
        "judge_ledger_snapshots",
        ["case_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_judge_ledger_snapshots_trace",
        "judge_ledger_snapshots",
        ["trace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_judge_ledger_snapshots_trace", table_name="judge_ledger_snapshots")
    op.drop_index(
        "ix_judge_ledger_snapshots_case_updated",
        table_name="judge_ledger_snapshots",
    )
    op.drop_table("judge_ledger_snapshots")
