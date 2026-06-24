from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import Project, ProjectEvent, ProjectRecord, SourceArticle
from market_info.dedupe.matcher import MatchDecision, ProjectMergeError, apply_match_decision


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_article(published_at: datetime | None = None) -> SourceArticle:
    return SourceArticle(
        account_id=1,
        account_name="光伏前沿",
        title="测试文章",
        article_url="https://mp.weixin.qq.com/s/test",
        normalized_url="https://mp.weixin.qq.com/s/test",
        published_at=published_at,
        content_text="正文",
        content_hash="a" * 64,
    )


def make_record(article: SourceArticle, status: str | None = "备案") -> ProjectRecord:
    return ProjectRecord(
        source_article=article,
        project_name="盐城光伏组件扩产项目",
        project_info="新增组件产线",
        province="江苏省",
        city="盐城市",
        detailed_address="盐城经开区",
        company_name="江苏示例新能源有限公司",
        investment_amount_yi=10.5,
        industry="新能源",
        field="光伏",
        market="电力",
        status=status,
        confidence=0.9,
        semantic_text="盐城光伏组件扩产项目 江苏示例新能源",
        embedding=None,
    )


def make_project(status: str | None = "备案") -> Project:
    return Project(
        canonical_project_name="盐城光伏组件扩产项目",
        canonical_company_name="江苏示例新能源有限公司",
        province="江苏省",
        city="盐城市",
        detailed_address="盐城经开区",
        investment_amount_yi=10.5,
        industry="新能源",
        field="光伏",
        market="电力",
        current_status=status,
        semantic_text="已有项目语义文本",
        embedding=None,
    )


def make_decision(
    decision: str,
    project_id: int | None,
    final_score: float = 91.5,
) -> MatchDecision:
    return MatchDecision(
        decision=decision,
        final_score=final_score,
        project_id=project_id,
        rule_score=90,
        vector_score=94,
    )


def test_new_decision_creates_project_and_links_record(session) -> None:
    published_at = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
    article = make_article(published_at=published_at)
    record = make_record(article)
    session.add(record)
    session.flush()

    project = apply_match_decision(session, record, make_decision("new", None, 12.3))

    assert project is not None
    assert project.id is not None
    assert record.project_id == project.id
    assert record.project is project
    assert project.canonical_project_name == record.project_name
    assert project.canonical_company_name == record.company_name
    assert project.current_status == record.status
    assert project.first_seen_at == published_at
    assert project.last_seen_at == published_at
    assert project.semantic_text == record.semantic_text
    assert record.dedupe_decision == "new"
    assert record.dedupe_score == 12.3
    assert session.query(ProjectEvent).count() == 0


def test_new_decision_uses_record_created_at_when_article_has_no_published_at(session) -> None:
    created_at = datetime(2026, 6, 2, 9, 30, tzinfo=timezone.utc)
    article = make_article(published_at=None)
    record = make_record(article)
    record.created_at = created_at
    session.add(record)
    session.flush()

    project = apply_match_decision(session, record, make_decision("new", None))

    assert project.first_seen_at == created_at
    assert project.last_seen_at == created_at


def test_merge_same_status_links_project_without_event(session) -> None:
    article = make_article(published_at=datetime(2026, 6, 3, 8, 0, tzinfo=timezone.utc))
    record = make_record(article, status="备案")
    project = make_project(status="备案")
    session.add_all([record, project])
    session.flush()

    result = apply_match_decision(session, record, make_decision("merge", project.id, 88.8))

    assert result is project
    assert record.project_id == project.id
    assert record.dedupe_decision == "merge"
    assert record.dedupe_score == 88.8
    assert project.current_status == "备案"
    assert project.last_seen_at == article.published_at
    assert session.query(ProjectEvent).count() == 0


def test_merge_status_change_creates_event_and_updates_current_status(session) -> None:
    published_at = datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc)
    article = make_article(published_at=published_at)
    record = make_record(article, status="开工")
    project = make_project(status="备案")
    session.add_all([record, project])
    session.flush()

    apply_match_decision(session, record, make_decision("merge", project.id))

    event = session.query(ProjectEvent).one()
    assert event.project_id == project.id
    assert event.source_article_id == record.source_article_id
    assert event.previous_status == "备案"
    assert event.event_status == "开工"
    assert event.event_date.replace(tzinfo=timezone.utc) == published_at
    assert event.change_label == "备案 -> 开工"
    assert project.current_status == "开工"


def test_merge_older_record_does_not_move_project_status_or_last_seen_backwards(session) -> None:
    older_published_at = datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc)
    newer_seen_at = datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc)
    article = make_article(published_at=older_published_at)
    record = make_record(article, status="started")
    project = make_project(status="filed")
    project.last_seen_at = newer_seen_at
    session.add_all([record, project])
    session.flush()

    apply_match_decision(session, record, make_decision("merge", project.id))

    assert record.project_id == project.id
    assert project.current_status == "filed"
    assert project.last_seen_at == newer_seen_at
    assert session.query(ProjectEvent).count() == 0


def test_merge_unknown_status_does_not_overwrite_status_or_create_event(session) -> None:
    article = make_article(published_at=datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc))
    record = make_record(article, status="未知")
    project = make_project(status="备案")
    session.add_all([record, project])
    session.flush()

    apply_match_decision(session, record, make_decision("merge", project.id))

    assert record.project_id == project.id
    assert project.current_status == "备案"
    assert session.query(ProjectEvent).count() == 0


def test_review_decision_marks_record_without_project_or_event(session) -> None:
    article = make_article()
    record = make_record(article)
    session.add(record)
    session.flush()

    result = apply_match_decision(session, record, make_decision("review", 123, 77.7))

    assert result is None
    assert record.project_id is None
    assert record.project is None
    assert record.dedupe_decision == "review"
    assert record.dedupe_score == 77.7
    assert session.query(Project).count() == 0
    assert session.query(ProjectEvent).count() == 0


def test_merge_without_project_id_raises_business_error(session) -> None:
    article = make_article()
    record = make_record(article)
    session.add(record)
    session.flush()

    with pytest.raises(ProjectMergeError, match="project_id"):
        apply_match_decision(session, record, make_decision("merge", None))


def test_merge_missing_project_raises_business_error(session) -> None:
    article = make_article()
    record = make_record(article)
    session.add(record)
    session.flush()

    with pytest.raises(ProjectMergeError, match="not found"):
        apply_match_decision(session, record, make_decision("merge", 999))


def test_apply_match_decision_does_not_commit(session) -> None:
    article = make_article()
    record = make_record(article)
    session.add(record)
    session.flush()

    def fail_commit() -> None:
        raise AssertionError("apply_match_decision must not commit")

    session.commit = fail_commit

    apply_match_decision(session, record, make_decision("review", None))
