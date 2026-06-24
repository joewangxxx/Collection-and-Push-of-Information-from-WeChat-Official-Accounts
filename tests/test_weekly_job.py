from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.ai.embeddings import EmbeddingError
from market_info.ai.extractor import ProjectExtractionError
from market_info.ai.schemas import ALLOWED_STATUSES, ExtractedProject
from market_info.db.base import Base
from market_info.db.models import ProjectRecord, SourceArticle
from market_info.dedupe.matcher import MatchDecision
from market_info.ingest.article_ingestor import IngestResult
from market_info.notify.email_sender import EmailSendError


def make_settings() -> SimpleNamespace:
    return SimpleNamespace(
        wechat_exporter_base_url="http://wechat.example",
        wechat_exporter_auth_key="auth-key",
        accounts_config_path="config/accounts.yml",
        ai_base_url="http://ai.example",
        ai_api_key="ai-key",
        ai_extraction_model="extract-model",
        ai_embedding_model="embed-model",
        embedding_dim=1536,
        ai_concurrency=3,
        export_dir="exports",
    )


class FakeWechatClient:
    def __init__(self, auth_valid: bool = True) -> None:
        self.auth_valid = auth_valid

    def check_auth(self) -> bool:
        return self.auth_valid


@contextmanager
def fake_session_scope(session: object | None = None):
    yield session or SimpleNamespace(commit=lambda: None)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_source_article(
    title: str = "article",
    processing_status: str = "pending",
    extraction_attempts: int = 0,
) -> SourceArticle:
    return SourceArticle(
        account_id=1,
        account_name="account",
        title=title,
        article_url=f"https://mp.weixin.qq.com/s/{title}",
        normalized_url=f"https://mp.weixin.qq.com/s/{title}",
        published_at=datetime(2026, 6, 24, tzinfo=timezone.utc),
        content_text="article content",
        content_hash=("a" * 63) + str(len(title) % 10),
        processing_status=processing_status,
        extraction_attempts=extraction_attempts,
    )


def test_run_weekly_stops_when_auth_fails_and_does_not_send_email(monkeypatch) -> None:
    from market_info.jobs import weekly_job

    email_calls = []
    monkeypatch.setattr(weekly_job, "Settings", make_settings)
    monkeypatch.setattr(
        weekly_job,
        "WechatExporterClient",
        lambda base_url, auth_key: FakeWechatClient(auth_valid=False),
    )
    monkeypatch.setattr(weekly_job, "send_report_email", lambda *args, **kwargs: email_calls.append(args))

    with pytest.raises(weekly_job.WeeklyJobError, match="wechat exporter auth invalid"):
        weekly_job.run_weekly(limit=20)

    assert email_calls == []


def test_ingest_enabled_accounts_only_ingests_articles(monkeypatch) -> None:
    from market_info.jobs import weekly_job

    calls = []
    enabled_account = SimpleNamespace(name="enabled-account", fakeid="fakeid-1", enabled=True)
    disabled_account = SimpleNamespace(name="disabled-account", fakeid="fakeid-2", enabled=False)

    class FakeArticleIngestor:
        def __init__(self, client, session) -> None:
            calls.append("create-ingestor")

        def ingest_account(self, account, limit: int) -> IngestResult:
            calls.append(("ingest", account.name, limit))
            return IngestResult(inserted_articles=2, skipped_articles=1, failed_articles=0)

    monkeypatch.setattr(weekly_job, "Settings", make_settings)
    monkeypatch.setattr(weekly_job, "load_accounts_config", lambda path: [enabled_account, disabled_account])
    monkeypatch.setattr(weekly_job, "get_session", lambda: fake_session_scope())
    monkeypatch.setattr(weekly_job, "_sync_account", lambda session, account_config: account_config)
    monkeypatch.setattr(weekly_job, "ArticleIngestor", FakeArticleIngestor)
    monkeypatch.setattr(weekly_job, "ProjectExtractor", lambda *args, **kwargs: calls.append("ai"))
    monkeypatch.setattr(weekly_job, "generate_weekly_excel", lambda *args, **kwargs: calls.append("excel"))
    monkeypatch.setattr(weekly_job, "send_report_email", lambda *args, **kwargs: calls.append("email"))

    results = weekly_job.ingest_enabled_accounts(limit=5, client=FakeWechatClient())

    assert len(results) == 1
    assert results[0].account_name == "enabled-account"
    assert results[0].inserted_articles == 2
    assert calls == ["create-ingestor", ("ingest", "enabled-account", 5)]


def test_send_report_calls_email_sender(monkeypatch, tmp_path) -> None:
    from market_info.jobs import weekly_job

    report_path = tmp_path / "sample.xlsx"
    report_path.write_bytes(b"xlsx")
    calls = []
    monkeypatch.setattr(weekly_job, "send_report_email", lambda path, summary: calls.append((path, summary)))

    weekly_job.send_report(report_path)

    assert calls
    assert calls[0][0] == report_path
    assert calls[0][1]["new_projects"] == 0
    assert calls[0][1]["generated_at"]


def test_run_weekly_success_calls_steps_in_order(monkeypatch, tmp_path) -> None:
    from market_info.jobs import weekly_job

    calls = []
    fake_session = SimpleNamespace(commit=lambda: calls.append("commit"))
    excel_path = tmp_path / "weekly.xlsx"

    monkeypatch.setattr(weekly_job, "Settings", make_settings)
    monkeypatch.setattr(
        weekly_job,
        "WechatExporterClient",
        lambda base_url, auth_key: FakeWechatClient(auth_valid=True),
    )
    monkeypatch.setattr(
        weekly_job,
        "ingest_enabled_accounts",
        lambda limit, settings=None, client=None: (
            calls.append("ingest")
            or [
                weekly_job.IngestAccountResult(
                    account_name="account",
                    inserted_articles=3,
                    skipped_articles=1,
                    failed_articles=0,
                )
            ]
        ),
    )
    monkeypatch.setattr(weekly_job, "get_session", lambda: fake_session_scope(fake_session))
    monkeypatch.setattr(
        weekly_job,
        "process_pending_articles",
        lambda session, settings, max_articles=None, progress_callback=None: calls.append(
            ("process", max_articles, progress_callback)
        )
        or weekly_job.ProcessingResult(
            new_projects=1,
            merged_projects=2,
            review_projects=1,
            status_events=1,
            project_total=4,
        ),
    )
    monkeypatch.setattr(
        weekly_job,
        "generate_weekly_excel",
        lambda session, output_dir, run_id=None: calls.append("excel") or excel_path,
    )
    monkeypatch.setattr(
        weekly_job,
        "send_report_email",
        lambda path, summary: calls.append(("email", path, summary)),
    )

    summary = weekly_job.run_weekly(limit=20)

    assert calls[:4] == [
        "ingest",
        ("process", 20, None),
        "commit",
        "excel",
    ]
    email_call = calls[4]
    assert email_call[0] == "email"
    assert email_call[1] == excel_path
    assert email_call[2]["new_projects"] == summary.new_projects
    assert email_call[2]["merged_projects"] == summary.merged_projects
    assert email_call[2]["review_projects"] == summary.review_projects
    assert email_call[2]["project_total"] == summary.project_total
    assert email_call[2]["status_events"] == summary.status_events
    assert email_call[2]["generated_at"]
    assert summary.new_articles == 3
    assert summary.new_projects == 1
    assert summary.merged_projects == 2
    assert summary.review_projects == 1
    assert summary.status_events == 1
    assert summary.excel_path == excel_path
    assert summary.email_sent is True


def test_run_weekly_raises_clear_error_when_email_fails(monkeypatch, tmp_path) -> None:
    from market_info.jobs import weekly_job

    fake_session = SimpleNamespace(commit=lambda: None)
    monkeypatch.setattr(weekly_job, "Settings", make_settings)
    monkeypatch.setattr(
        weekly_job,
        "WechatExporterClient",
        lambda base_url, auth_key: FakeWechatClient(auth_valid=True),
    )
    monkeypatch.setattr(weekly_job, "ingest_enabled_accounts", lambda *args, **kwargs: [])
    monkeypatch.setattr(weekly_job, "get_session", lambda: fake_session_scope(fake_session))
    monkeypatch.setattr(
        weekly_job,
        "process_pending_articles",
        lambda session, settings, max_articles=None, progress_callback=None: weekly_job.ProcessingResult(
            new_projects=0,
            merged_projects=0,
            review_projects=0,
            status_events=0,
            project_total=0,
        ),
    )
    monkeypatch.setattr(weekly_job, "generate_weekly_excel", lambda *args, **kwargs: tmp_path / "weekly.xlsx")
    monkeypatch.setattr(
        weekly_job,
        "send_report_email",
        lambda *args, **kwargs: (_ for _ in ()).throw(EmailSendError("smtp failed")),
    )

    with pytest.raises(weekly_job.WeeklyJobError, match="email sending failed"):
        weekly_job.run_weekly(limit=20)


def test_process_pending_articles_skips_article_when_extraction_fails(
    monkeypatch,
    db_session,
) -> None:
    from market_info.jobs import weekly_job

    calls = []

    class FakeExtractor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract(self, title: str, text: str):
            calls.append(title)
            if title == "bad":
                raise ProjectExtractionError("timeout")
            return []

    bad_article = make_source_article("bad")
    good_article = make_source_article("good")
    db_session.add_all([bad_article, good_article])
    db_session.flush()
    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())

    result = weekly_job.process_pending_articles(db_session, make_settings())

    assert calls == ["bad", "good"]
    assert result.new_projects == 0
    assert result.merged_projects == 0
    assert result.review_projects == 0
    db_session.refresh(bad_article)
    db_session.refresh(good_article)
    assert bad_article.processing_status == "failed"
    assert good_article.processing_status == "processed"


def test_process_pending_articles_passes_max_articles_to_pending_query(monkeypatch) -> None:
    from market_info.jobs import weekly_job

    seen = []

    class FakeSession:
        def query(self, model):
            return SimpleNamespace(count=lambda: 0)

        def flush(self) -> None:
            pass

    monkeypatch.setattr(weekly_job, "ProjectExtractor", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(weekly_job, "EmbeddingClient", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())
    monkeypatch.setattr(
        weekly_job,
        "_pending_articles",
        lambda session, max_articles=None: seen.append(max_articles) or [],
    )

    weekly_job.process_pending_articles(FakeSession(), make_settings(), max_articles=7)

    assert seen == [7]


def test_process_pending_articles_marks_article_failed_when_embedding_fails(
    monkeypatch,
    db_session,
) -> None:
    from market_info.jobs import weekly_job

    extracted_project = ExtractedProject(
        project_name="project",
        status="备案",
        confidence=0.9,
    )

    class FakeExtractor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract(self, title: str, text: str):
            return [extracted_project]

    class FakeEmbeddingClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def embed(self, text: str):
            raise EmbeddingError("embedding timeout")

    article = make_source_article("article")
    db_session.add(article)
    db_session.flush()
    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())

    result = weekly_job.process_pending_articles(db_session, make_settings())

    db_session.refresh(article)
    assert db_session.query(ProjectRecord).filter_by(source_article_id=article.id).count() == 0
    assert article.processing_status == "failed"
    assert article.extraction_attempts == 1
    assert "embedding timeout" in article.extraction_error
    assert result.new_projects == 0


def test_pending_articles_uses_processing_status_and_retry_limit(db_session) -> None:
    from market_info.jobs import weekly_job

    pending = make_source_article("pending", processing_status="pending")
    processed = make_source_article("processed", processing_status="processed")
    retryable_failed = make_source_article(
        "retryable",
        processing_status="failed",
        extraction_attempts=2,
    )
    exhausted_failed = make_source_article(
        "exhausted",
        processing_status="failed",
        extraction_attempts=3,
    )
    db_session.add_all([pending, processed, retryable_failed, exhausted_failed])
    db_session.flush()

    articles = weekly_job._pending_articles(db_session)

    assert {article.title for article in articles} == {"pending", "retryable"}


def test_pending_articles_with_limit_drains_oldest_first(db_session) -> None:
    from market_info.jobs import weekly_job

    oldest = make_source_article("oldest", processing_status="pending")
    middle = make_source_article("middle", processing_status="pending")
    newest = make_source_article("newest", processing_status="pending")
    oldest.created_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    middle.created_at = datetime(2026, 6, 2, tzinfo=timezone.utc)
    newest.created_at = datetime(2026, 6, 3, tzinfo=timezone.utc)
    db_session.add_all([newest, oldest, middle])
    db_session.flush()

    articles = weekly_job._pending_articles(db_session, max_articles=2)

    assert [article.title for article in articles] == ["oldest", "middle"]


def test_process_pending_articles_rejects_invalid_ai_concurrency(db_session) -> None:
    from market_info.jobs import weekly_job

    settings = make_settings()
    settings.ai_concurrency = 0

    with pytest.raises(weekly_job.WeeklyJobError, match="AI_CONCURRENCY"):
        weekly_job.process_pending_articles(db_session, settings)


def test_process_pending_articles_marks_no_project_article_processed(
    monkeypatch,
    db_session,
) -> None:
    from market_info.jobs import weekly_job

    article = make_source_article("no-project")
    db_session.add(article)
    db_session.flush()

    class FakeExtractor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract(self, title: str, text: str):
            return []

    progress = []
    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())

    weekly_job.process_pending_articles(
        db_session,
        make_settings(),
        progress_callback=progress.append,
    )

    db_session.refresh(article)
    assert article.processing_status == "processed"
    assert article.extraction_attempts == 1
    assert article.processed_at is not None
    assert article.extraction_error is None
    assert weekly_job._pending_articles(db_session) == []
    assert any("projects=0 status=processed" in item for item in progress)


def test_process_pending_articles_creates_record_and_marks_article_processed(
    monkeypatch,
    db_session,
) -> None:
    from market_info.jobs import weekly_job

    article = make_source_article("with-project")
    db_session.add(article)
    db_session.flush()
    extracted_project = ExtractedProject(
        project_name="project",
        company_name="company",
        province="province",
        status="备案",
        confidence=0.9,
    )

    class FakeExtractor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract(self, title: str, text: str):
            return [extracted_project]

    class FakeEmbeddingClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def embed(self, text: str):
            return None

    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(
        weekly_job,
        "VectorSearch",
        lambda session: SimpleNamespace(find_candidates=lambda embedding, province: []),
    )
    monkeypatch.setattr(
        weekly_job,
        "choose_best_match",
        lambda candidates, rule_scores: MatchDecision(
            decision="new",
            final_score=0,
            project_id=None,
            rule_score=0,
            vector_score=0,
        ),
    )

    result = weekly_job.process_pending_articles(db_session, make_settings())

    db_session.refresh(article)
    assert article.processing_status == "processed"
    assert db_session.query(ProjectRecord).filter_by(source_article_id=article.id).count() == 1
    assert result.new_projects == 1


def test_process_pending_articles_marks_extraction_failure_failed(
    monkeypatch,
    db_session,
) -> None:
    from market_info.jobs import weekly_job

    article = make_source_article("bad")
    db_session.add(article)
    db_session.flush()

    class FakeExtractor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract(self, title: str, text: str):
            raise ProjectExtractionError("timeout while extracting")

    progress = []
    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())

    weekly_job.process_pending_articles(
        db_session,
        make_settings(),
        progress_callback=progress.append,
    )

    db_session.refresh(article)
    assert article.processing_status == "failed"
    assert article.extraction_attempts == 1
    assert article.processed_at is not None
    assert "timeout while extracting" in article.extraction_error
    assert any("status=failed" in item for item in progress)


def test_process_pending_articles_uses_limited_ai_concurrency(
    monkeypatch,
    db_session,
) -> None:
    from market_info.jobs import weekly_job

    for index in range(5):
        db_session.add(make_source_article(f"article-{index}"))
    db_session.flush()

    active = 0
    max_active = 0
    lock = threading.Lock()

    class FakeExtractor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract(self, title: str, text: str):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return []

    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())

    settings = make_settings()
    settings.ai_concurrency = 2
    progress = []

    weekly_job.process_pending_articles(
        db_session,
        settings,
        max_articles=5,
        progress_callback=progress.append,
    )

    assert max_active == 2
    assert all(article.processing_status == "processed" for article in db_session.query(SourceArticle))
    assert "AI processing articles: total=5 concurrency=2" in progress


def test_worker_receives_article_snapshot_not_orm_object(
    monkeypatch,
) -> None:
    from market_info.jobs import weekly_job

    seen = []

    class FakeExtractor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract(self, title: str, text: str):
            seen.append((title, text))
            return []

    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", lambda *args, **kwargs: SimpleNamespace())

    outcome = weekly_job._process_article_ai(
        weekly_job.ArticleProcessingInput(
            article_id=123,
            title="title",
            content_text="content",
        ),
        make_settings(),
    )

    assert outcome.article_id == 123
    assert outcome.success is True
    assert outcome.projects == []
    assert seen == [("title", "content")]


def test_process_pending_articles_replays_database_writes_in_article_order(
    monkeypatch,
    db_session,
) -> None:
    from market_info.jobs import weekly_job

    first_article = make_source_article("first")
    second_article = make_source_article("second")
    db_session.add_all([first_article, second_article])
    db_session.flush()

    first_project = ExtractedProject(
        project_name="first project",
        status="澶囨",
        confidence=0.9,
    )
    second_project = ExtractedProject(
        project_name="second project",
        status="澶囨",
        confidence=0.9,
    )

    def fake_process_article_ai(article_input, settings):
        if article_input.title == "first":
            time.sleep(0.05)
            project = first_project
        else:
            project = second_project
        return weekly_job.ArticleProcessingOutcome(
            article_id=article_input.article_id,
            success=True,
            projects=[
                weekly_job.ProjectExtractionOutput(
                    extracted_project=project,
                    semantic_text=project.project_name,
                    embedding=[0.1] * 1536,
                )
            ],
        )

    write_order = []
    monkeypatch.setattr(weekly_job, "_process_article_ai", fake_process_article_ai)
    monkeypatch.setattr(
        weekly_job,
        "VectorSearch",
        lambda session: SimpleNamespace(find_candidates=lambda embedding, province: []),
    )

    def fake_choose_best_match(candidates, rule_scores):
        record = db_session.query(ProjectRecord).order_by(ProjectRecord.id.desc()).first()
        write_order.append(record.project_name)
        return MatchDecision(
            decision="new",
            final_score=0,
            project_id=None,
            rule_score=0,
            vector_score=0,
        )

    monkeypatch.setattr(weekly_job, "choose_best_match", fake_choose_best_match)

    result = weekly_job.process_pending_articles(db_session, make_settings())

    assert result.new_projects == 2
    assert write_order == ["first project", "second project"]


def test_process_pending_articles_marks_worker_crash_failed(
    monkeypatch,
    db_session,
) -> None:
    from market_info.jobs import weekly_job

    article = make_source_article("crash")
    db_session.add(article)
    db_session.flush()

    def fake_process_article_ai(article_input, settings):
        raise RuntimeError("worker crashed")

    monkeypatch.setattr(weekly_job, "_process_article_ai", fake_process_article_ai)
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())

    weekly_job.process_pending_articles(db_session, make_settings())

    db_session.refresh(article)
    assert article.processing_status == "failed"
    assert article.extraction_attempts == 1
    assert "worker crashed" in article.extraction_error
