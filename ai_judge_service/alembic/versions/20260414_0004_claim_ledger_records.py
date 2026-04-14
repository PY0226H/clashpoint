"""add claim ledger records table

Revision ID: 20260414_0004
Revises: 20260414_0003
Create Date: 2026-04-14 17:20:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260414_0004"
down_revision = "20260414_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claim_ledger_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.BigInteger(), nullable=False),
        sa.Column("dispatch_type", sa.String(length=16), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("claim_graph", sa.JSON(), nullable=False),
        sa.Column("claim_graph_summary", sa.JSON(), nullable=False),
        sa.Column("evidence_ledger", sa.JSON(), nullable=False),
        sa.Column("verdict_evidence_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "dispatch_type", name="uq_claim_ledger_case_dispatch"),
    )
    op.create_index(
        "ix_claim_ledger_case_updated",
        "claim_ledger_records",
        ["case_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_claim_ledger_case_updated", table_name="claim_ledger_records")
    op.drop_table("claim_ledger_records")
