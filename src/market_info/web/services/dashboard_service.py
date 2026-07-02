from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from market_info.config import Settings
from market_info.db.models import Project, ProjectEvent, ProjectRecord
from market_info.db.session import get_session
from market_info.jobs.weekly_job import (
    ArticleProcessingStatusSummary,
    check_wechat_auth,
    get_processing_status_summary,
)
from market_info.wechat.exporter_client import WechatExporterClient


@dataclass(frozen=True)
class ReportFileSummary:
    name: str
    path: Path
    size_bytes: int
    modified_at: float


@dataclass(frozen=True)
class ServiceHealth:
    ok: bool
    label: str
    detail: str = ""


@dataclass(frozen=True)
class DashboardOverview:
    wechat: ServiceHealth
    database: ServiceHealth
    article_status: ArticleProcessingStatusSummary
    project_total: int
    review_records: int
    status_events: int
    latest_report: ReportFileSummary | None


def mask_error(exc: Exception, max_length: int = 180) -> str:
    message = " ".join(str(exc).split())
    return message[:max_length]


def find_latest_report(export_dir: Path) -> ReportFileSummary | None:
    if not export_dir.exists() or not export_dir.is_dir():
        return None
    reports = [
        path
        for path in export_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".xlsx"
    ]
    if not reports:
        return None
    latest = max(reports, key=lambda path: (path.stat().st_mtime, path.name))
    stat = latest.stat()
    return ReportFileSummary(
        name=latest.name,
        path=latest,
        size_bytes=stat.st_size,
        modified_at=stat.st_mtime,
    )


def get_dashboard_overview(settings: Settings | None = None) -> DashboardOverview:
    settings = settings or Settings()
    wechat = _check_wechat(settings)
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
            article_status = get_processing_status_summary(session)
            project_total = session.query(Project).count()
            review_records = (
                session.query(ProjectRecord)
                .filter(ProjectRecord.dedupe_decision == "review")
                .count()
            )
            status_events = session.query(ProjectEvent).count()
        database = ServiceHealth(True, "数据库连接正常")
    except Exception as exc:
        article_status = ArticleProcessingStatusSummary()
        project_total = 0
        review_records = 0
        status_events = 0
        database = ServiceHealth(False, "数据库连接失败", mask_error(exc))

    return DashboardOverview(
        wechat=wechat,
        database=database,
        article_status=article_status,
        project_total=project_total,
        review_records=review_records,
        status_events=status_events,
        latest_report=find_latest_report(Path(settings.export_dir)),
    )


def _check_wechat(settings: Settings) -> ServiceHealth:
    try:
        client = WechatExporterClient(
            settings.wechat_exporter_base_url,
            settings.wechat_exporter_auth_key,
            timeout=1.0,
        )
        is_valid = check_wechat_auth(settings=settings, client=client)
    except Exception as exc:
        return ServiceHealth(False, "微信导出服务检查失败", mask_error(exc))
    if is_valid:
        return ServiceHealth(True, "微信授权正常")
    return ServiceHealth(
        False,
        "微信授权异常",
        "请检查 wechat-exporter 服务地址和 auth key",
    )
