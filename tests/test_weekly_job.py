from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_info.ai.embeddings import EmbeddingError
from market_info.ai.extractor import ProjectExtractionError
from market_info.ai.schemas import ExtractedProject
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
        lambda session, settings, max_articles=None: calls.append(("process", max_articles))
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

    assert calls == [
        "ingest",
        ("process", 20),
        "commit",
        "excel",
        ("email", excel_path, summary.to_email_summary()),
    ]
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
        lambda session, settings, max_articles=None: weekly_job.ProcessingResult(
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


def test_process_pending_articles_skips_article_when_extraction_fails(monkeypatch) -> None:
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

    class FakeSession:
        def query(self, model):
            return SimpleNamespace(count=lambda: 0)

    articles = [
        SimpleNamespace(title="bad", content_text="text"),
        SimpleNamespace(title="good", content_text="text"),
    ]
    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())
    monkeypatch.setattr(
        weekly_job,
        "_pending_articles",
        lambda session, max_articles=None: articles,
    )

    result = weekly_job.process_pending_articles(FakeSession(), make_settings())

    assert calls == ["bad", "good"]
    assert result.new_projects == 0
    assert result.merged_projects == 0
    assert result.review_projects == 0


def test_process_pending_articles_passes_max_articles_to_pending_query(monkeypatch) -> None:
    from market_info.jobs import weekly_job

    seen = []

    class FakeSession:
        def query(self, model):
            return SimpleNamespace(count=lambda: 0)

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


def test_process_pending_articles_skips_project_when_embedding_fails(monkeypatch) -> None:
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

    class FakeSession:
        def __init__(self) -> None:
            self.added = []

        def query(self, model):
            return SimpleNamespace(count=lambda: 0)

        def add(self, record) -> None:
            self.added.append(record)

        def flush(self) -> None:
            raise AssertionError("flush should not be called when embedding fails")

    session = FakeSession()
    articles = [SimpleNamespace(title="article", content_text="text")]
    monkeypatch.setattr(weekly_job, "ProjectExtractor", FakeExtractor)
    monkeypatch.setattr(weekly_job, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(weekly_job, "VectorSearch", lambda session: SimpleNamespace())
    monkeypatch.setattr(
        weekly_job,
        "_pending_articles",
        lambda session, max_articles=None: articles,
    )

    result = weekly_job.process_pending_articles(session, make_settings())

    assert session.added == []
    assert result.new_projects == 0
