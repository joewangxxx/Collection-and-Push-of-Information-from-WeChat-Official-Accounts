import json
from contextlib import contextmanager
from pathlib import Path

from market_info.config import Settings
from market_info.web.services import quality_service


def test_load_evaluation_report_reads_metrics(tmp_path: Path) -> None:
    report_path = tmp_path / "evaluation_report.json"
    report_path.write_text(
        json.dumps(
            {
                "extraction": {
                    "project_precision": 0.75,
                    "project_recall": 0.6,
                    "field_accuracy": 0.8,
                    "status_accuracy": 0.9,
                    "investment_accuracy": 1.0,
                    "hallucination_count": 2,
                    "missed_count": 1,
                },
                "dedupe": {
                    "dedupe_accuracy": 0.5,
                    "false_merge_count": 1,
                    "missed_merge_count": 2,
                    "status_change_accuracy": 0.75,
                },
                "error_samples": {},
            }
        ),
        encoding="utf-8",
    )

    summary = quality_service.load_evaluation_report(report_path)

    assert summary is not None
    assert summary.project_precision == 0.75
    assert summary.dedupe_accuracy == 0.5
    assert summary.false_merge_count == 1


def test_build_quality_overview_counts_assets(tmp_path: Path) -> None:
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    (tmp_path / "golden_labels.xlsx").write_bytes(b"xlsx")
    (articles_dir / "a.txt").write_text("body", encoding="utf-8")

    overview = quality_service.build_quality_overview(base_dir=tmp_path)

    assert overview.golden_assets.labels_exists is True
    assert overview.golden_assets.article_body_count == 1
    assert overview.evaluation is None


def test_get_safe_settings_snapshot_masks_secret_values() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        WECHAT_EXPORTER_AUTH_KEY="wechat-secret",
        AI_API_KEY="ai-secret",
        SMTP_PASSWORD="smtp-secret",
        WECOM_WEBHOOK_URL="https://example.test/hook",
        MAIL_TO="ops@example.test",
    )

    rows = quality_service.get_safe_settings_snapshot(settings)
    rendered = " ".join(f"{row.name}:{row.detail}" for row in rows)

    assert "wechat-secret" not in rendered
    assert "ai-secret" not in rendered
    assert "smtp-secret" not in rendered
    assert "https://example.test/hook" not in rendered
    assert "configured" in rendered


def test_export_golden_for_web_uses_database_session(monkeypatch, tmp_path: Path) -> None:
    calls = []

    class DummySession:
        pass

    @contextmanager
    def fake_get_session():
        yield DummySession()

    def fake_export(session, output_dir, limit):
        calls.append((session, output_dir, limit))
        path = output_dir / "golden_labels.xlsx"
        output_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"xlsx")
        return path

    monkeypatch.setattr(quality_service, "get_session", fake_get_session)
    monkeypatch.setattr(quality_service, "export_golden_template", fake_export)

    path = quality_service.export_golden_for_web(tmp_path, 7)

    assert path == tmp_path / "golden_labels.xlsx"
    assert calls[0][1] == tmp_path
    assert calls[0][2] == 7
