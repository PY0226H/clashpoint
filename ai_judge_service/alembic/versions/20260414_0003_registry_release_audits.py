"""add judge registry release and audit tables

Revision ID: 20260414_0003
Revises: 20260413_0002
Create Date: 2026-04-14 00:30:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260414_0003"
down_revision = "20260413_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "judge_registry_releases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("registry_type", sa.String(length=16), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="published"),
        sa.Column("created_by", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by", sa.String(length=64), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "registry_type",
            "version",
            name="uq_judge_registry_release_type_version",
        ),
    )
    op.create_index(
        "ix_judge_registry_release_type_active",
        "judge_registry_releases",
        ["registry_type", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_judge_registry_release_type_updated",
        "judge_registry_releases",
        ["registry_type", "updated_at"],
        unique=False,
    )

    op.create_table(
        "judge_registry_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("registry_type", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=True),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_judge_registry_audits_type_created",
        "judge_registry_audits",
        ["registry_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_judge_registry_audits_type_created", table_name="judge_registry_audits")
    op.drop_table("judge_registry_audits")

    op.drop_index("ix_judge_registry_release_type_updated", table_name="judge_registry_releases")
    op.drop_index("ix_judge_registry_release_type_active", table_name="judge_registry_releases")
    op.drop_table("judge_registry_releases")
