from dataclasses import dataclass
from pathlib import Path
import json

from market_info.config import Settings
from market_info.db.session import get_session
from market_info.evaluation.core import evaluate_golden
from market_info.evaluation.exporter import export_golden_template


DEFAULT_GOLDEN_DIR = Path("data/golden_articles")
SETTINGS_KEYS = [
    "DATABASE_URL",
    "WECHAT_EXPORTER_BASE_URL",
    "WECHAT_EXPORTER_AUTH_KEY",
    "AI_BASE_URL",
    "AI_API_KEY",
    "AI_EXTRACTION_MODEL",
    "AI_EMBEDDING_MODEL",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "MAIL_TO",
    "WECOM_WEBHOOK_URL",
    "EXPORT_DIR",
]
SECRET_KEYS = {
    "DATABASE_URL",
    "WECHAT_EXPORTER_AUTH_KEY",
    "AI_API_KEY",
    "SMTP_PASSWORD",
    "WECOM_WEBHOOK_URL",
}


@dataclass(frozen=True)
class GoldenAssetSummary:
    base_dir: Path
    labels_path: Path
    labels_exists: bool
    article_body_count: int
    report_path: Path
    report_exists: bool


@dataclass(frozen=True)
class EvaluationMetricSummary:
    project_precision: float
    project_recall: float
    field_accuracy: float
    status_accuracy: float
    investment_accuracy: float
    dedupe_accuracy: float
    false_merge_count: int
    missed_merge_count: int


@dataclass(frozen=True)
class ConfigHealthItem:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class QualityOverview:
    golden_assets: GoldenAssetSummary
    evaluation: EvaluationMetricSummary | None
    config_items: list[ConfigHealthItem]


def build_quality_overview(
    base_dir: Path | None = None,
    report_path: Path | None = None,
) -> QualityOverview:
    base = base_dir or DEFAULT_GOLDEN_DIR
    labels_path = base / "golden_labels.xlsx"
    report = report_path or base / "evaluation_report.json"
    articles_dir = base / "articles"
    body_count = len(list(articles_dir.glob("*.txt"))) if articles_dir.is_dir() else 0
    assets = GoldenAssetSummary(
        base_dir=base,
        labels_path=labels_path,
        labels_exists=labels_path.is_file(),
        article_body_count=body_count,
        report_path=report,
        report_exists=report.is_file(),
    )
    return QualityOverview(
        golden_assets=assets,
        evaluation=load_evaluation_report(report),
        config_items=get_safe_settings_snapshot(),
    )


def load_evaluation_report(report_path: Path) -> EvaluationMetricSummary | None:
    if not report_path.is_file():
        return None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    extraction = payload.get("extraction") or {}
    dedupe = payload.get("dedupe") or {}
    return EvaluationMetricSummary(
        project_precision=float(extraction.get("project_precision", 0.0)),
        project_recall=float(extraction.get("project_recall", 0.0)),
        field_accuracy=float(extraction.get("field_accuracy", 0.0)),
        status_accuracy=float(extraction.get("status_accuracy", 0.0)),
        investment_accuracy=float(extraction.get("investment_accuracy", 0.0)),
        dedupe_accuracy=float(dedupe.get("dedupe_accuracy", 0.0)),
        false_merge_count=int(dedupe.get("false_merge_count", 0)),
        missed_merge_count=int(dedupe.get("missed_merge_count", 0)),
    )


def get_safe_settings_snapshot(settings: Settings | None = None) -> list[ConfigHealthItem]:
    settings = settings or Settings()
    rows = []
    for key in SETTINGS_KEYS:
        value = _settings_value(settings, key)
        configured = bool(value)
        rows.append(
            ConfigHealthItem(
                name=key,
                status="configured" if configured else "missing",
                detail=_safe_detail(key, value),
            )
        )
    return rows


def export_golden_for_web(output_dir: Path, limit: int) -> Path:
    with get_session() as session:
        return export_golden_template(session, output_dir, limit)


def evaluate_golden_for_web(labels_path: Path, report_path: Path) -> Path:
    evaluate_golden(labels_path, report_path=report_path)
    return report_path


def _settings_value(settings: Settings, key: str) -> str:
    field_name = next(
        (
            name
            for name, field in type(settings).model_fields.items()
            if str(field.alias) == key
        ),
        "",
    )
    if not field_name:
        return ""
    value = getattr(settings, field_name)
    return "" if value is None else str(value)


def _safe_detail(key: str, value: str) -> str:
    if not value:
        return "missing"
    if key in SECRET_KEYS:
        return "configured"
    return value
