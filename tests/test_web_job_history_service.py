from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.web.services import job_history_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(job_history_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def test_create_and_list_job_history(sqlite_session) -> None:
    created = job_history_service.create_job_run("run_weekly", {"limit": 10})
    job_history_service.mark_job_started(created.id)
    job_history_service.append_job_log(created.id, "started weekly run")
    job_history_service.mark_job_succeeded(created.id, {"new_projects": 2})

    rows = job_history_service.list_job_history()
    loaded = job_history_service.get_job_history(created.id)

    assert [row.id for row in rows] == [created.id]
    assert loaded is not None
    assert loaded.kind == "run_weekly"
    assert loaded.status == "succeeded"
    assert loaded.logs == ["started weekly run"]
    assert loaded.finished_at is not None


def test_mark_job_failed_records_single_line_error(sqlite_session) -> None:
    created = job_history_service.create_job_run("check_auth")

    job_history_service.mark_job_failed(created.id, "line one\nline two")

    loaded = job_history_service.get_job_history(created.id)
    assert loaded is not None
    assert loaded.status == "failed"
    assert loaded.error_message == "line one line two"


def test_missing_job_history_returns_none(sqlite_session) -> None:
    assert job_history_service.get_job_history("missing") is None
