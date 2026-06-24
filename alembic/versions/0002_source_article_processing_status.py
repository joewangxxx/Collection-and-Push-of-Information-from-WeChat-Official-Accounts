"""Add source article AI processing status."""

from alembic import op
import sqlalchemy as sa


revision = "0002_article_processing"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_articles",
        sa.Column(
            "processing_status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "source_articles",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_articles",
        sa.Column("extraction_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "source_articles",
        sa.Column(
            "extraction_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_source_articles_processing_status",
        "source_articles",
        ["processing_status"],
    )
    op.execute(
        """
        UPDATE source_articles
        SET processing_status = 'processed',
            processed_at = now(),
            extraction_error = NULL
        WHERE id IN (
            SELECT DISTINCT source_article_id
            FROM project_records
            WHERE source_article_id IS NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_source_articles_processing_status", table_name="source_articles")
    op.drop_column("source_articles", "extraction_attempts")
    op.drop_column("source_articles", "extraction_error")
    op.drop_column("source_articles", "processed_at")
    op.drop_column("source_articles", "processing_status")
