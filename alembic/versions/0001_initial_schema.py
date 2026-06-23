"""Initial schema with pgvector."""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "mp_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("fakeid", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "source_articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("article_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["mp_accounts.id"]),
    )
    op.create_index(
        "ix_source_articles_normalized_url",
        "source_articles",
        ["normalized_url"],
        unique=True,
    )
    op.create_index(
        "ix_source_articles_content_hash",
        "source_articles",
        ["content_hash"],
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_project_name", sa.String(length=500), nullable=True),
        sa.Column("canonical_company_name", sa.String(length=500), nullable=True),
        sa.Column("province", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("detailed_address", sa.String(length=500), nullable=True),
        sa.Column("investment_amount_yi", sa.Numeric(14, 4), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("field", sa.String(length=255), nullable=True),
        sa.Column("market", sa.String(length=255), nullable=True),
        sa.Column("current_status", sa.String(length=100), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("semantic_text", sa.Text(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_projects_province", "projects", ["province"])
    op.create_index("ix_projects_city", "projects", ["city"])
    op.execute(
        "CREATE INDEX ix_projects_embedding_hnsw "
        "ON projects USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "project_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_article_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("project_name", sa.String(length=500), nullable=True),
        sa.Column("project_info", sa.Text(), nullable=True),
        sa.Column("province", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("detailed_address", sa.String(length=500), nullable=True),
        sa.Column("company_name", sa.String(length=500), nullable=True),
        sa.Column("investment_amount_yi", sa.Numeric(14, 4), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("field", sa.String(length=255), nullable=True),
        sa.Column("market", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("semantic_text", sa.Text(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("dedupe_decision", sa.String(length=50), nullable=True),
        sa.Column("dedupe_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_article_id"], ["source_articles.id"]),
    )

    op.create_table(
        "project_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_article_id", sa.Integer(), nullable=False),
        sa.Column("event_status", sa.String(length=100), nullable=False),
        sa.Column("previous_status", sa.String(length=100), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_label", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_article_id"], ["source_articles.id"]),
    )

    op.create_table(
        "push_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=100), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("recipient", sa.String(length=500), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("artifact_path", sa.String(length=1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("push_logs")
    op.drop_table("project_events")
    op.drop_table("project_records")
    op.execute("DROP INDEX IF EXISTS ix_projects_embedding_hnsw")
    op.drop_index("ix_projects_city", table_name="projects")
    op.drop_index("ix_projects_province", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_source_articles_content_hash", table_name="source_articles")
    op.drop_index("ix_source_articles_normalized_url", table_name="source_articles")
    op.drop_table("source_articles")
    op.drop_table("mp_accounts")
