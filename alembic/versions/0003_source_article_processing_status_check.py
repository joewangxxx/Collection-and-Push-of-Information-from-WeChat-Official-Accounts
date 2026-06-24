"""Add source article processing status check constraint."""

from alembic import op


revision = "0003_processing_status_check"
down_revision = "0002_article_processing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_source_articles_processing_status",
        "source_articles",
        "processing_status in ('pending', 'processed', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_source_articles_processing_status",
        "source_articles",
        type_="check",
    )
