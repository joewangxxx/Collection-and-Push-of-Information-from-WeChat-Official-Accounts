from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from market_info.config import Settings
from market_info.db.models import PushLog
from market_info.db.session import get_session
from market_info.jobs.weekly_job import send_report


@dataclass(frozen=True)
class DeliveryLogItem:
    id: int
    run_id: str | None
    channel: str
    status: str
    recipient: str | None
    subject: str | None
    artifact_path: str | None
    message: str | None
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    artifact_path: str
    error_message: str | None = None


def list_delivery_logs(limit: int = 100) -> list[DeliveryLogItem]:
    with get_session() as session:
        rows = (
            session.query(PushLog)
            .order_by(PushLog.created_at.desc(), PushLog.id.desc())
            .limit(limit)
            .all()
        )
        return [_to_item(row) for row in rows]


def record_delivery_log(
    *,
    run_id: str | None = None,
    channel: str,
    status: str,
    recipient: str | None = None,
    subject: str | None = None,
    artifact_path: str | None = None,
    message: str | None = None,
    error_message: str | None = None,
) -> DeliveryLogItem:
    with get_session() as session:
        row = PushLog(
            run_id=run_id,
            channel=channel,
            status=status,
            recipient=recipient,
            subject=subject,
            artifact_path=artifact_path,
            message=message,
            error_message=_normalize_error(error_message) if error_message else None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_item(row)


def send_report_and_record(excel_path: Path | str) -> DeliveryResult:
    path = Path(excel_path)
    settings = Settings()
    run_id = f"send-report-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        send_report(path)
    except Exception as exc:
        error_message = _normalize_error(exc)
        record_delivery_log(
            run_id=run_id,
            channel="email",
            status="failed",
            recipient=settings.mail_to or None,
            subject=path.name,
            artifact_path=str(path),
            message="Report delivery failed",
            error_message=error_message,
        )
        raise

    record_delivery_log(
        run_id=run_id,
        channel="email",
        status="succeeded",
        recipient=settings.mail_to or None,
        subject=path.name,
        artifact_path=str(path),
        message="Report delivered",
    )
    return DeliveryResult(status="succeeded", artifact_path=str(path))


def _normalize_error(exc: Exception | str, max_length: int = 500) -> str:
    return " ".join(str(exc).split())[:max_length]


def _to_item(row: PushLog) -> DeliveryLogItem:
    return DeliveryLogItem(
        id=row.id,
        run_id=row.run_id,
        channel=row.channel,
        status=row.status,
        recipient=row.recipient,
        subject=row.subject,
        artifact_path=row.artifact_path,
        message=row.message,
        error_message=row.error_message,
        created_at=row.created_at,
    )
