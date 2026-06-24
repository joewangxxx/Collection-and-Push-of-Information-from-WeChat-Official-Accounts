from market_info.db.base import Base
from market_info.db.models import (
    MpAccount,
    Project,
    ProjectEvent,
    ProjectRecord,
    PushLog,
    SourceArticle,
)


def test_imports_all_database_models() -> None:
    assert MpAccount.__tablename__ == "mp_accounts"
    assert SourceArticle.__tablename__ == "source_articles"
    assert ProjectRecord.__tablename__ == "project_records"
    assert Project.__tablename__ == "projects"
    assert ProjectEvent.__tablename__ == "project_events"
    assert PushLog.__tablename__ == "push_logs"


def test_metadata_contains_business_tables() -> None:
    expected_tables = {
        "mp_accounts",
        "source_articles",
        "project_records",
        "projects",
        "project_events",
        "push_logs",
    }

    assert expected_tables <= set(Base.metadata.tables)


def test_source_articles_has_processing_status_columns() -> None:
    columns = Base.metadata.tables["source_articles"].columns

    assert "processing_status" in columns
    assert "processed_at" in columns
    assert "extraction_error" in columns
    assert "extraction_attempts" in columns
