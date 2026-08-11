"""Create immutable PR snapshots, analyses, and evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_pr_analysis"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "analysis_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("repository_id", id_type, sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("pull_request_number", sa.Integer(), nullable=False),
        sa.Column("base_sha", sa.String(64), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("diff_hash", sa.String(64), nullable=False),
        sa.Column("metadata_hash", sa.String(64), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("rules_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_analysis_snapshots_pr",
        "analysis_snapshots",
        ["repository_id", "pull_request_number", "head_sha"],
    )
    op.create_table(
        "analyses",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id", sa.String(64), sa.ForeignKey("analysis_snapshots.id"), nullable=False
        ),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("risk_confidence", sa.Float(), nullable=False),
        sa.Column("evidence_coverage", sa.Float(), nullable=False),
        sa.Column("suggested_tests", sa.JSON(), nullable=False),
        sa.Column("review_focus", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("provider_metadata", sa.JSON()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("snapshot_id", name="uq_analyses_snapshot_id"),
    )
    op.create_table(
        "evidence",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("analysis_id", id_type, sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("path", sa.String(4096)),
        sa.Column("line", sa.Integer()),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_evidence_analysis_kind", "evidence", ["analysis_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_evidence_analysis_kind", table_name="evidence")
    op.drop_table("evidence")
    op.drop_table("analyses")
    op.drop_index("ix_analysis_snapshots_pr", table_name="analysis_snapshots")
    op.drop_table("analysis_snapshots")
