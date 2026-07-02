from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import SourceArticle
from market_info.web.services import article_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(article_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def make_article(title: str, status: str, attempts: int = 0) -> SourceArticle:
    return SourceArticle(
        account_id=1,
        account_name="account",
        title=title,
        article_url=f"https://example.com/{title}",
        normalized_url=f"https://example.com/{title}",
        published_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        content_text="content",
        content_hash=(title + "x" * 64)[:64],
        processing_status=status,
        extraction_attempts=attempts,
    )


def test_list_articles_filters_status(sqlite_session) -> None:
    sqlite_session.add_all(
        [
            make_article("pending", "pending"),
            make_article("processed", "processed"),
        ]
    )
    sqlite_session.commit()

    rows = article_service.list_articles(status="pending")

    assert [row.title for row in rows] == ["pending"]
    assert rows[0].status == "pending"


def test_count_articles_by_status(sqlite_session) -> None:
    sqlite_session.add_all(
        [
            make_article("pending", "pending"),
            make_article("failed", "failed", attempts=2),
            make_article("processed", "processed"),
        ]
    )
    sqlite_session.commit()

    counts = article_service.count_articles_by_status()

    assert counts["pending"] == 1
    assert counts["failed"] == 1
    assert counts["processed"] == 1
