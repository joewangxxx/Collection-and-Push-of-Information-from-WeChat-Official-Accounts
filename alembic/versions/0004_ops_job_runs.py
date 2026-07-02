"""Add ops job runs."""

from alembic import op
import sqlalchemy as sa


revision = "0004_ops_job_runs"
down_revision = "0003_processing_status_check"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ops_job_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("logs_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ops_job_runs_kind", "ops_job_runs", ["kind"])
    op.create_index("ix_ops_job_runs_status", "ops_job_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ops_job_runs_status", table_name="ops_job_runs")
    op.drop_index("ix_ops_job_runs_kind", table_name="ops_job_runs")
    op.drop_table("ops_job_runs")
