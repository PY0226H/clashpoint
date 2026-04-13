"""add dispatch receipt and audit fact tables

Revision ID: 20260413_0002
Revises: 20260413_0001
Create Date: 2026-04-13 00:20:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260413_0002"
down_revision = "20260413_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dispatch_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dispatch_type", sa.String(length=16), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("session_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("trace_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("rubric_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("judge_policy_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("topic_domain", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("retrieval_profile", sa.String(length=64), nullable=True),
        sa.Column("phase_no", sa.Integer(), nullable=True),
        sa.Column("phase_start_no", sa.Integer(), nullable=True),
        sa.Column("phase_end_no", sa.Integer(), nullable=True),
        sa.Column("message_start_id", sa.BigInteger(), nullable=True),
        sa.Column("message_end_id", sa.BigInteger(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dispatch_type",
            "job_id",
            name="uq_dispatch_receipts_dispatch_type_job_id",
        ),
    )
    op.create_index(
        "ix_dispatch_receipts_session_status",
        "dispatch_receipts",
        ["session_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_dispatch_receipts_updated_at",
        "dispatch_receipts",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "replay_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dispatch_type", sa.String(length=16), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("winner", sa.String(length=16), nullable=True),
        sa.Column("needs_draw_vote", sa.Boolean(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("report_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_replay_records_dispatch_job",
        "replay_records",
        ["dispatch_type", "job_id"],
        unique=False,
    )
    op.create_index(
        "ix_replay_records_created_at",
        "replay_records",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "audit_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("trace_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="raised"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", name="uq_audit_alerts_alert_id"),
    )
    op.create_index(
        "ix_audit_alerts_job_status",
        "audit_alerts",
        ["job_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_audit_alerts_updated_at",
        "audit_alerts",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_alerts_updated_at", table_name="audit_alerts")
    op.drop_index("ix_audit_alerts_job_status", table_name="audit_alerts")
    op.drop_table("audit_alerts")

    op.drop_index("ix_replay_records_created_at", table_name="replay_records")
    op.drop_index("ix_replay_records_dispatch_job", table_name="replay_records")
    op.drop_table("replay_records")

    op.drop_index("ix_dispatch_receipts_updated_at", table_name="dispatch_receipts")
    op.drop_index("ix_dispatch_receipts_session_status", table_name="dispatch_receipts")
    op.drop_table("dispatch_receipts")
