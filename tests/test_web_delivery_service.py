from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import PushLog
from market_info.web.services import delivery_service


@pytest.fixture()
def sqlite_session(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "delivery.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    @contextmanager
    def get_test_session():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(delivery_service, "get_session", get_test_session)
    return SessionLocal


def test_record_and_list_delivery_logs(sqlite_session) -> None:
    delivery_service.record_delivery_log(
        run_id="run-1",
        channel="email",
        status="succeeded",
        recipient="ops@example.com",
        subject="weekly.xlsx",
        artifact_path="exports/weekly.xlsx",
        message="sent",
    )

    logs = delivery_service.list_delivery_logs()

    assert len(logs) == 1
    assert logs[0].run_id == "run-1"
    assert logs[0].channel == "email"
    assert logs[0].status == "succeeded"
    assert logs[0].artifact_path == "exports/weekly.xlsx"


def test_send_report_and_record_success(sqlite_session, monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "weekly.xlsx"
    report_path.write_bytes(b"xlsx")
    calls = []
    monkeypatch.setattr(delivery_service, "send_report", lambda path: calls.append(path))

    result = delivery_service.send_report_and_record(report_path)

    assert result.status == "succeeded"
    assert result.artifact_path == str(report_path)
    assert calls == [report_path]
    [row] = sqlite_session().query(PushLog).all()
    assert row.status == "succeeded"
    assert row.artifact_path == str(report_path)


def test_send_report_and_record_failure_is_recorded_and_reraised(
    sqlite_session,
    monkeypatch,
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "weekly.xlsx"
    report_path.write_bytes(b"xlsx")

    def fail_send(path: Path) -> None:
        raise RuntimeError("smtp \n failed with api_key=secret")

    monkeypatch.setattr(delivery_service, "send_report", fail_send)

    with pytest.raises(RuntimeError, match="smtp"):
        delivery_service.send_report_and_record(report_path)

    [row] = sqlite_session().query(PushLog).all()
    assert row.status == "failed"
    assert row.artifact_path == str(report_path)
    assert row.error_message == "smtp failed with api_key=secret"
