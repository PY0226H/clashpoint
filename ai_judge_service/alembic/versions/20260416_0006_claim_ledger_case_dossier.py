"""add case dossier to claim ledger records

Revision ID: 20260416_0006
Revises: 20260414_0005
Create Date: 2026-04-16 22:30:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260416_0006"
down_revision = "20260414_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "claim_ledger_records",
        sa.Column("case_dossier", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column("claim_ledger_records", "case_dossier", server_default=None)


def downgrade() -> None:
    op.drop_column("claim_ledger_records", "case_dossier")
