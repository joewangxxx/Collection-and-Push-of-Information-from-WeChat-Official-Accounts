from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import Project, ProjectRecord, SourceArticle
from market_info.web.services import review_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(review_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def make_article(title: str = "Solar project filing") -> SourceArticle:
    return SourceArticle(
        account_id=1,
        account_name="Solar Frontline",
        title=title,
        article_url="https://mp.weixin.qq.com/s/review",
        normalized_url="https://mp.weixin.qq.com/s/review",
        published_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
        content_text="article body must not appear in review queue items",
        content_hash="a" * 64,
    )


def make_review_record(article: SourceArticle) -> ProjectRecord:
    return ProjectRecord(
        source_article=article,
        project_name="Yancheng solar module expansion",
        project_info="New module production line",
        province="Jiangsu",
        city="Yancheng",
        company_name="Jiangsu Example Energy Co.",
        status="filed",
        dedupe_decision="review",
        dedupe_score=76.5,
        semantic_text="Yancheng solar module expansion",
    )


def test_list_review_records_returns_review_items_without_article_body(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    sqlite_session.add(record)
    sqlite_session.commit()

    rows = review_service.list_review_records()

    assert len(rows) == 1
    assert rows[0].id == record.id
    assert rows[0].project_name == "Yancheng solar module expansion"
    assert rows[0].article_title == "Solar project filing"
    assert not hasattr(rows[0], "content_text")


def test_list_project_candidates_prefers_same_province_and_name_query(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    candidate = Project(
        canonical_project_name="Yancheng solar module phase one",
        canonical_company_name="Jiangsu Example Energy Co.",
        province="Jiangsu",
        city="Yancheng",
        current_status="started",
        last_seen_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    sqlite_session.add_all([record, candidate])
    sqlite_session.commit()

    rows = review_service.list_project_candidates(record.id, query="solar")

    assert [row.id for row in rows] == [candidate.id]
    assert rows[0].score_hint == "same province"


def test_resolve_review_record_as_new_creates_project(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    sqlite_session.add(record)
    sqlite_session.commit()

    result = review_service.resolve_review_record(record.id, "new")

    sqlite_session.refresh(record)
    assert result.decision == "new"
    assert result.project_id == record.project_id
    assert record.dedupe_decision == "new"
    assert sqlite_session.query(Project).count() == 1


def test_resolve_review_record_as_merge_links_existing_project(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    project = Project(
        canonical_project_name="Yancheng solar module phase one",
        canonical_company_name="Jiangsu Example Energy Co.",
        province="Jiangsu",
        city="Yancheng",
        current_status="filed",
        last_seen_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    sqlite_session.add_all([record, project])
    sqlite_session.commit()

    result = review_service.resolve_review_record(record.id, "merge", project.id)

    sqlite_session.refresh(record)
    assert result.decision == "merge"
    assert result.project_id == project.id
    assert record.project_id == project.id
    assert record.dedupe_decision == "merge"


def test_resolve_review_record_rejects_non_review_record(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    record.dedupe_decision = "new"
    sqlite_session.add(record)
    sqlite_session.commit()

    with pytest.raises(ValueError, match="not pending review"):
        review_service.resolve_review_record(record.id, "new")
