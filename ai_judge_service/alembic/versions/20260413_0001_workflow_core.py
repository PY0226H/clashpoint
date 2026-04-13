"""create workflow core tables

Revision ID: 20260413_0001
Revises: None
Create Date: 2026-04-13 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260413_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "judge_jobs",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("dispatch_type", sa.String(length=16), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("rubric_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("judge_policy_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("topic_domain", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("retrieval_profile", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "ix_judge_jobs_dispatch_status",
        "judge_jobs",
        ["dispatch_type", "status"],
        unique=False,
    )
    op.create_index(
        "ix_judge_jobs_updated_at",
        "judge_jobs",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "judge_job_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["judge_jobs.job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "event_seq", name="uq_judge_job_events_job_seq"),
    )
    op.create_index("ix_judge_job_events_job_id", "judge_job_events", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_judge_job_events_job_id", table_name="judge_job_events")
    op.drop_table("judge_job_events")
    op.drop_index("ix_judge_jobs_updated_at", table_name="judge_jobs")
    op.drop_index("ix_judge_jobs_dispatch_status", table_name="judge_jobs")
    op.drop_table("judge_jobs")
