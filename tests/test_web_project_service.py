from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import Project, ProjectEvent, ProjectRecord, SourceArticle
from market_info.web.services import project_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(project_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def make_article() -> SourceArticle:
    return SourceArticle(
        account_id=1,
        account_name="Solar Frontline",
        title="Project started notice",
        article_url="https://mp.weixin.qq.com/s/project",
        normalized_url="https://mp.weixin.qq.com/s/project",
        published_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
        content_text="article body must not appear in project detail items",
        content_hash="b" * 64,
    )


def make_project(name: str, province: str = "Jiangsu", status: str = "started") -> Project:
    return Project(
        canonical_project_name=name,
        canonical_company_name="Jiangsu Example Energy Co.",
        province=province,
        city="Yancheng",
        industry="new energy",
        market="power",
        current_status=status,
        investment_amount_yi=10.5,
        first_seen_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
        semantic_text="must not appear in web service return objects",
    )


def test_list_projects_filters_by_query_province_and_status(sqlite_session) -> None:
    keep = make_project("Yancheng solar module expansion")
    drop = make_project("Suzhou storage station", province="Jiangsu", status="filed")
    sqlite_session.add_all([keep, drop])
    sqlite_session.commit()

    rows = project_service.list_projects(query="solar", province="Jiangsu", status="started")

    assert [row.id for row in rows] == [keep.id]
    assert rows[0].project_name == "Yancheng solar module expansion"
    assert not hasattr(rows[0], "semantic_text")


def test_get_project_detail_returns_records_and_events(sqlite_session) -> None:
    article = make_article()
    project = make_project("Yancheng solar module expansion")
    record = ProjectRecord(
        source_article=article,
        project=project,
        project_name=project.canonical_project_name,
        company_name=project.canonical_company_name,
        status="started",
        dedupe_decision="merge",
        dedupe_score=91.2,
    )
    event = ProjectEvent(
        project=project,
        source_article=article,
        previous_status="filed",
        event_status="started",
        event_date=article.published_at,
        change_label="filed -> started",
    )
    sqlite_session.add_all([record, event])
    sqlite_session.commit()

    detail = project_service.get_project_detail(project.id)

    assert detail.project.id == project.id
    assert detail.records[0].article_title == "Project started notice"
    assert detail.events[0].change_label == "filed -> started"
    assert not hasattr(detail.records[0], "content_text")


def test_get_project_detail_raises_for_missing_project(sqlite_session) -> None:
    with pytest.raises(ValueError, match="Project not found"):
        project_service.get_project_detail(999)
