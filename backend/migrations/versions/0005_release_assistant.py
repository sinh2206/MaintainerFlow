"""Add persisted release candidate drafts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_release_assistant"
down_revision: str | None = "0004_issue_repository_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "release_drafts",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column(
            "repository_id",
            id_type,
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_ref", sa.String(255), nullable=False),
        sa.Column("to_ref", sa.String(255), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("compare_url", sa.String(2_048), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("draft_payload", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "repository_id", "from_ref", "to_ref", "input_hash", name="uq_release_draft_input"
        ),
    )
    op.create_index(
        "ix_release_drafts_range",
        "release_drafts",
        ["repository_id", "from_ref", "to_ref"],
    )
    op.add_column(
        "audit_events",
        sa.Column(
            "release_draft_id",
            id_type,
            sa.ForeignKey("release_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_audit_release_draft_type",
        "audit_events",
        ["release_draft_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_release_draft_type", table_name="audit_events")
    op.drop_column("audit_events", "release_draft_id")
    op.drop_index("ix_release_drafts_range", table_name="release_drafts")
    op.drop_table("release_drafts")
