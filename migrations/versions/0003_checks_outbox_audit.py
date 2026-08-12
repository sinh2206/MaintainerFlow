"""Add safe GitHub Check publishing, audit, and transactional outbox."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_checks_outbox_audit"
down_revision: str | None = "0002_pr_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column("analyses", sa.Column("github_check_id", sa.BigInteger()))
    op.add_column(
        "analyses",
        sa.Column(
            "publish_status",
            sa.String(32),
            server_default="not_queued",
            nullable=False,
        ),
    )
    op.add_column("analyses", sa.Column("publish_error", sa.String(128)))
    op.create_table(
        "outbox_events",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(128)),
        sa.Column("github_check_id", sa.BigInteger()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending','processing','sent','dead_letter')",
            name="ck_outbox_status",
        ),
    )
    op.create_index(
        "ix_outbox_claim", "outbox_events", ["status", "available_at", "lease_expires_at"]
    )
    op.create_table(
        "audit_events",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("repository_id", id_type, sa.ForeignKey("repositories.id")),
        sa.Column("analysis_id", id_type, sa.ForeignKey("analyses.id")),
        sa.Column("actor_id", sa.BigInteger()),
        sa.Column("actor_login", sa.String(255)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_audit_analysis_type", "audit_events", ["analysis_id", "event_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_analysis_type", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_outbox_claim", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_column("analyses", "publish_error")
    op.drop_column("analyses", "publish_status")
    op.drop_column("analyses", "github_check_id")
