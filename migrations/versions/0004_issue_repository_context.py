"""Add issue triage and repository context cache."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_issue_repository_context"
down_revision: str | None = "0003_checks_outbox_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "repository_indexes",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column(
            "repository_id",
            id_type,
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("analyzer_version", sa.String(128), nullable=False),
        sa.Column("file_tree", sa.JSON(), nullable=False),
        sa.Column("modules", sa.JSON(), nullable=False),
        sa.Column("dependency_graph", sa.JSON(), nullable=False),
        sa.Column("criticality", sa.JSON(), nullable=False),
        sa.Column("related_tests", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("source_archive", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "repository_id", "commit_sha", "analyzer_version", name="uq_repository_index_cache"
        ),
    )
    op.create_index("ix_repository_indexes_expiry", "repository_indexes", ["expires_at"])
    op.create_table(
        "issue_analyses",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column(
            "repository_id",
            id_type,
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("github_issue_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_number", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_spans", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("label_suggestions", sa.JSON(), nullable=False),
        sa.Column("similar_issues", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "repository_id", "github_issue_id", "source_hash", name="uq_issue_analysis_source"
        ),
    )
    op.create_index("ix_issue_analyses_expiry", "issue_analyses", ["expires_at"])
    op.create_table(
        "historical_evidence",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column(
            "repository_index_id",
            id_type,
            sa.ForeignKey("repository_indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(2_048), nullable=False),
        sa.Column("path", sa.String(4_096), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "repository_index_id", "kind", "source_id", "path", name="uq_history_source"
        ),
    )
    op.create_index("ix_historical_evidence_expiry", "historical_evidence", ["expires_at"])
    op.add_column(
        "audit_events",
        sa.Column(
            "issue_analysis_id",
            id_type,
            sa.ForeignKey("issue_analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_audit_issue_analysis_type",
        "audit_events",
        ["issue_analysis_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_issue_analysis_type", table_name="audit_events")
    op.drop_column("audit_events", "issue_analysis_id")
    op.drop_index("ix_historical_evidence_expiry", table_name="historical_evidence")
    op.drop_table("historical_evidence")
    op.drop_index("ix_issue_analyses_expiry", table_name="issue_analyses")
    op.drop_table("issue_analyses")
    op.drop_index("ix_repository_indexes_expiry", table_name="repository_indexes")
    op.drop_table("repository_indexes")
