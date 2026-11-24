"""
Create alignment jobs and alignment results tables.

Revision ID: 0001_alignment_tables
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# Revision identifiers.
revision: str = "0001_alignment_tables"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the GeneWeaver alignment tables."""

    op.create_table(
        "alignment_jobs",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("guide_sequence", sa.String(length=256), nullable=False),
        sa.Column(
            "pam_type",
            sa.String(length=32),
            server_default=sa.text("'NGG'"),
            nullable=False,
        ),
        sa.Column("reference_genome", sa.String(length=128), nullable=False),
        sa.Column(
            "reference_dataset_version",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "reference_dataset_checksum",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column("algorithm_name", sa.String(length=128), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column(
            "compute_backend",
            sa.String(length=32),
            server_default=sa.text("'cpu'"),
            nullable=False,
        ),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "progress",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN " "('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_alignment_jobs_status",
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_alignment_jobs_progress",
        ),
    )

    op.create_index(
        "ix_alignment_jobs_status_created_at",
        "alignment_jobs",
        ["status", "created_at"],
    )

    op.create_index(
        "ix_alignment_jobs_reference_genome",
        "alignment_jobs",
        ["reference_genome"],
    )

    op.create_table(
        "alignment_results",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chromosome", sa.String(length=64), nullable=False),
        sa.Column("start_position", sa.Integer(), nullable=False),
        sa.Column("end_position", sa.Integer(), nullable=False),
        sa.Column("strand", sa.String(length=1), nullable=False),
        sa.Column("target_sequence", sa.String(length=256), nullable=False),
        sa.Column("pam_sequence", sa.String(length=32), nullable=False),
        sa.Column("mismatch_count", sa.Integer(), nullable=False),
        sa.Column("mismatch_positions", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("score_components", sa.JSON(), nullable=True),
        sa.Column("result_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["alignment_jobs.id"],
            name="fk_alignment_results_job_id_alignment_jobs",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "start_position >= 0",
            name="ck_alignment_results_start_position",
        ),
        sa.CheckConstraint(
            "end_position > start_position",
            name="ck_alignment_results_coordinate_range",
        ),
        sa.CheckConstraint(
            "strand IN ('+', '-')",
            name="ck_alignment_results_strand",
        ),
        sa.CheckConstraint(
            "mismatch_count >= 0",
            name="ck_alignment_results_mismatch_count",
        ),
    )

    op.create_index(
        "ix_alignment_results_job_id",
        "alignment_results",
        ["job_id"],
    )

    op.create_index(
        "ix_alignment_results_chromosome_position",
        "alignment_results",
        ["chromosome", "start_position"],
    )

    op.create_index(
        "ix_alignment_results_mismatch_count",
        "alignment_results",
        ["mismatch_count"],
    )


def downgrade() -> None:
    """Remove the alignment tables and their indexes."""

    op.drop_index(
        "ix_alignment_results_mismatch_count",
        table_name="alignment_results",
    )

    op.drop_index(
        "ix_alignment_results_chromosome_position",
        table_name="alignment_results",
    )

    op.drop_index(
        "ix_alignment_results_job_id",
        table_name="alignment_results",
    )

    op.drop_table("alignment_results")

    op.drop_index(
        "ix_alignment_jobs_reference_genome",
        table_name="alignment_jobs",
    )

    op.drop_index(
        "ix_alignment_jobs_status_created_at",
        table_name="alignment_jobs",
    )

    op.drop_table("alignment_jobs")
