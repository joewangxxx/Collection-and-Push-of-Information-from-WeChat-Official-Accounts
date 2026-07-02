from dataclasses import dataclass
from datetime import datetime, timezone
import json
from uuid import uuid4

from market_info.db.models import OpsJobRun
from market_info.db.session import get_session


@dataclass(frozen=True)
class JobHistoryItem:
    id: str
    kind: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    logs: list[str]


def create_job_run(kind: str, params: dict[str, object] | None = None) -> JobHistoryItem:
    now = datetime.now(timezone.utc)
    row = OpsJobRun(
        id=str(uuid4()),
        kind=kind,
        status="created",
        params_json=_dumps(params or {}),
        logs_json=_dumps([]),
        created_at=now,
    )
    with get_session() as session:
        session.add(row)
        session.commit()
        return _to_item(row)


def mark_job_started(job_id: str) -> None:
    with get_session() as session:
        row = session.get(OpsJobRun, job_id)
        if row is None:
            return
        row.status = "running"
        row.started_at = datetime.now(timezone.utc)
        session.commit()


def append_job_log(job_id: str, message: str) -> None:
    with get_session() as session:
        row = session.get(OpsJobRun, job_id)
        if row is None:
            return
        logs = _loads_list(row.logs_json)
        logs.append(message)
        row.logs_json = _dumps(logs)
        session.commit()


def mark_job_succeeded(job_id: str, result: object | None = None) -> None:
    with get_session() as session:
        row = session.get(OpsJobRun, job_id)
        if row is None:
            return
        row.status = "succeeded"
        row.result_json = _dumps(result)
        row.finished_at = datetime.now(timezone.utc)
        session.commit()


def mark_job_failed(job_id: str, error_message: str) -> None:
    with get_session() as session:
        row = session.get(OpsJobRun, job_id)
        if row is None:
            return
        row.status = "failed"
        row.error_message = _normalize_error(error_message)
        row.finished_at = datetime.now(timezone.utc)
        session.commit()


def get_job_history(job_id: str) -> JobHistoryItem | None:
    with get_session() as session:
        row = session.get(OpsJobRun, job_id)
        return _to_item(row) if row is not None else None


def list_job_history(limit: int = 50) -> list[JobHistoryItem]:
    with get_session() as session:
        rows = (
            session.query(OpsJobRun)
            .order_by(OpsJobRun.created_at.desc(), OpsJobRun.id.desc())
            .limit(limit)
            .all()
        )
        return [_to_item(row) for row in rows]


def _to_item(row: OpsJobRun) -> JobHistoryItem:
    return JobHistoryItem(
        id=row.id,
        kind=row.kind,
        status=row.status,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        error_message=row.error_message,
        logs=_loads_list(row.logs_json),
    )


def _dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads_list(value: str | None) -> list[str]:
    if not value:
        return []
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _normalize_error(error_message: str) -> str:
    return " ".join(error_message.split())[:500]
