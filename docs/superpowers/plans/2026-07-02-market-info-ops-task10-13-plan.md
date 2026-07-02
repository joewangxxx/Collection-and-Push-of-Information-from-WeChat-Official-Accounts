# Market Info Ops Task 10-13 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the local/intranet operations console with durable job history, account management, delivery audit, and deploy-ready access protection.

**Architecture:** Continue the FastAPI + Jinja server-rendered console. Add small service modules for persistence and operational actions, keep routes thin, and use existing SQLAlchemy models where available. Task 10 is the only task in this plan that adds a database migration; Task 11-13 use existing tables or configuration.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, SQLAlchemy, Alembic, Typer, pytest, FastAPI TestClient, HTML/CSS/vanilla JavaScript.

## Global Constraints

- Preserve the current white Apple liquid-glass style: light canvas, translucent surfaces, data-dense tables, restrained blue/amber/red/green status colors.
- Do not introduce React, Next.js, or a SPA.
- Do not render secrets, raw webhook URLs, SMTP passwords, auth keys, `.env` contents, article full text, semantic text, or embeddings.
- Every state-changing web action must be POST and redirect after completion.
- Use `python -m pytest ...` for all test commands.
- Keep existing commands and tests green; final acceptance requires `python -m pytest -q`.
- Any web smoke command must clean up the spawned server process.
- `docs/handover.md` is unrelated local context and must not be staged unless the user explicitly asks.

---

## File Structure

Task 10-13 create or modify these files:

```text
alembic/versions/0004_ops_job_runs.py
.env.example
docs/web-ops-runbook.md
scripts/smoke_web_console.py
src/market_info/config.py
src/market_info/db/models.py
src/market_info/web/app.py
src/market_info/web/security.py
src/market_info/web/routes/accounts.py
src/market_info/web/routes/delivery.py
src/market_info/web/routes/jobs.py
src/market_info/web/routes/reports.py
src/market_info/web/services/account_service.py
src/market_info/web/services/delivery_service.py
src/market_info/web/services/job_history_service.py
src/market_info/web/services/job_runner.py
src/market_info/web/templates/accounts.html
src/market_info/web/templates/base.html
src/market_info/web/templates/delivery.html
src/market_info/web/templates/job_detail.html
src/market_info/web/templates/jobs.html
src/market_info/web/static/styles.css
tests/test_web_account_service.py
tests/test_web_delivery_service.py
tests/test_web_job_history_service.py
tests/test_web_job_runner.py
tests/test_web_security.py
tests/test_web_app.py
tests/test_smoke_scripts.py
```

## Verification Map

**Tests:**
- Task 10: `tests/test_web_job_history_service.py`, `tests/test_web_job_runner.py`, `tests/test_web_app.py`.
- Task 11: `tests/test_web_account_service.py`, `tests/test_web_app.py`.
- Task 12: `tests/test_web_delivery_service.py`, `tests/test_web_app.py`.
- Task 13: `tests/test_web_security.py`, `tests/test_smoke_scripts.py`, `tests/test_web_app.py`.

**Acceptance Commands:**
- Task 10: `python -m pytest tests/test_web_job_history_service.py tests/test_web_job_runner.py tests/test_web_app.py -v`, `python -m pytest -q`, `alembic upgrade head`.
- Task 11: `python -m pytest tests/test_web_account_service.py tests/test_web_app.py -v`, `python -m pytest -q`.
- Task 12: `python -m pytest tests/test_web_delivery_service.py tests/test_web_app.py -v`, `python -m pytest -q`.
- Task 13: `python -m pytest tests/test_web_security.py tests/test_smoke_scripts.py tests/test_web_app.py -v`, `python -m pytest -q`, `market-info web --host 127.0.0.1 --port 8080`, `python scripts/smoke_web_console.py --base-url http://127.0.0.1:8080`.

---

## Task 10: Persistent Job History and Job Detail

**Files:**
- Modify: `src/market_info/db/models.py`
- Create: `alembic/versions/0004_ops_job_runs.py`
- Create: `src/market_info/web/services/job_history_service.py`
- Modify: `src/market_info/web/services/job_runner.py`
- Modify: `src/market_info/web/routes/jobs.py`
- Modify: `src/market_info/web/templates/jobs.html`
- Create: `src/market_info/web/templates/job_detail.html`
- Modify: `src/market_info/web/static/styles.css`
- Test: `tests/test_web_job_history_service.py`
- Test: `tests/test_web_job_runner.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Produces model `OpsJobRun` in `market_info.db.models` with columns `id`, `kind`, `status`, `params_json`, `result_json`, `error_message`, `logs_json`, `created_at`, `started_at`, `finished_at`.
- Produces `JobHistoryItem` dataclass with fields `id`, `kind`, `status`, `created_at`, `started_at`, `finished_at`, `error_message`, `logs`.
- Produces `create_job_run(kind: str, params: dict[str, object] | None = None) -> JobHistoryItem`.
- Produces `mark_job_started(job_id: str) -> None`.
- Produces `append_job_log(job_id: str, message: str) -> None`.
- Produces `mark_job_succeeded(job_id: str, result: object | None = None) -> None`.
- Produces `mark_job_failed(job_id: str, error_message: str) -> None`.
- Produces `get_job_history(job_id: str) -> JobHistoryItem | None`.
- Produces `list_job_history(limit: int = 50) -> list[JobHistoryItem]`.
- Modifies `InMemoryJobRunner(start_job(...))` so persisted history is created and updated when a `history_store` is provided.

- [ ] **Step 1: Write failing job history service tests**

Create `tests/test_web_job_history_service.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_job_history_service.py -v
```

Expected:

```text
ImportError: cannot import name 'job_history_service'
```

- [ ] **Step 3: Add model and Alembic migration**

Modify `src/market_info/db/models.py`:

```python
class OpsJobRun(Base):
    __tablename__ = "ops_job_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    params_json: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    logs_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Create `alembic/versions/0004_ops_job_runs.py` with:

```python
"""add ops job runs

Revision ID: 0004_ops_job_runs
Revises: 0003_source_article_processing_status_check
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_ops_job_runs"
down_revision = "0003_source_article_processing_status_check"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ops_job_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("logs_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ops_job_runs_kind", "ops_job_runs", ["kind"])
    op.create_index("ix_ops_job_runs_status", "ops_job_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ops_job_runs_status", table_name="ops_job_runs")
    op.drop_index("ix_ops_job_runs_kind", table_name="ops_job_runs")
    op.drop_table("ops_job_runs")
```

- [ ] **Step 4: Implement job history service**

Create `src/market_info/web/services/job_history_service.py`.

Implementation requirements:

- Serialize params/result/logs with `json.dumps(..., ensure_ascii=False, default=str)`.
- Store log list in `logs_json`.
- Use `datetime.now(timezone.utc)` for timestamps.
- Normalize errors with `" ".join(error_message.split())[:500]`.
- Return dataclasses, not ORM rows.

- [ ] **Step 5: Wire job runner to history**

Modify `src/market_info/web/services/job_runner.py`:

- Add optional `history_store` constructor parameter.
- When starting a job, call `history_store.create_job_run(kind, kwargs)` and use that id as the in-memory job id.
- On success call `mark_job_succeeded`.
- On failure call `mark_job_failed`.
- `append_log()` must update both in-memory logs and persisted logs.
- Keep `InMemoryJobRunner(run_inline=True)` tests working without a history store.

Add tests to `tests/test_web_job_runner.py`:

```python
class FakeHistoryStore:
    def __init__(self):
        self.created = []
        self.succeeded = []
        self.failed = []
        self.logs = []

    def create_job_run(self, kind, params=None):
        from market_info.web.services.job_runner import JobStatus
        from datetime import datetime
        job = JobStatus(id="stored-1", kind=kind, status="running", created_at=datetime.now())
        self.created.append((kind, params))
        return job

    def mark_job_succeeded(self, job_id, result=None):
        self.succeeded.append((job_id, result))

    def mark_job_failed(self, job_id, error_message):
        self.failed.append((job_id, error_message))

    def append_job_log(self, job_id, message):
        self.logs.append((job_id, message))


def test_runner_updates_history_store_on_success() -> None:
    store = FakeHistoryStore()
    runner = InMemoryJobRunner(run_inline=True, history_store=store)

    job = runner.start_job("check_auth", lambda: "ok")

    assert job.id == "stored-1"
    assert store.created == [("check_auth", {})]
    assert store.succeeded == [("stored-1", "ok")]
```

- [ ] **Step 6: Update jobs page and add detail template**

Modify `src/market_info/web/routes/jobs.py`:

- Use `list_job_history()` for the main jobs table.
- Keep `job_runner.list_jobs()` available as `running_jobs`.
- `GET /jobs/{job_id}` should read `get_job_history(job_id)` first, then fall back to `job_runner.get_job(job_id)`.

Create `src/market_info/web/templates/job_detail.html` with a liquid-glass detail page showing status, timestamps, error, result summary, and logs.

Modify `src/market_info/web/templates/jobs.html` so history rows link to `/jobs/{job.id}`.

- [ ] **Step 7: Run Task 10 acceptance**

Run:

```powershell
python -m pytest tests/test_web_job_history_service.py tests/test_web_job_runner.py tests/test_web_app.py -v
python -m pytest -q
alembic upgrade head
```

Expected:

```text
Selected tests pass
Full test suite passes
Alembic upgrades through 0004_ops_job_runs
```

**Prompt for Task 10 execution:**

```text
Implement Task 10 from docs/superpowers/plans/2026-07-02-market-info-ops-task10-13-plan.md. Use TDD. Add OpsJobRun model, migration 0004, job history service, runner persistence hooks, job detail page, and jobs page history integration. Preserve existing in-memory runner behavior when no history store is provided. Run the Task 10 acceptance commands and report changed files plus verification output.
```

---

## Task 11: Account Management Console

**Files:**
- Create: `src/market_info/web/services/account_service.py`
- Create: `src/market_info/web/routes/accounts.py`
- Create: `src/market_info/web/templates/accounts.html`
- Modify: `src/market_info/web/app.py`
- Modify: `src/market_info/web/templates/base.html`
- Modify: `src/market_info/web/static/styles.css`
- Test: `tests/test_web_account_service.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Produces `AccountListItem` dataclass with fields `id`, `name`, `masked_fakeid`, `enabled`, `last_fetch_at`, `article_count`, `created_at`.
- Produces `AccountSyncResult` dataclass with fields `created`, `updated`, `disabled_missing`.
- Produces `list_accounts() -> list[AccountListItem]`.
- Produces `sync_accounts_from_config(config_path: Path | None = None) -> AccountSyncResult`.
- Produces `set_account_enabled(account_id: int, enabled: bool) -> None`.
- Produces routes `GET /accounts`, `POST /accounts/sync`, `POST /accounts/{account_id}/enable`, `POST /accounts/{account_id}/disable`.

- [ ] **Step 1: Write failing account service tests**

Create `tests/test_web_account_service.py`:

```python
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import MpAccount, SourceArticle
from market_info.web.services import account_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(account_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def test_list_accounts_masks_fakeid_and_counts_articles(sqlite_session) -> None:
    account = MpAccount(name="光伏前沿", fakeid="MzA123456789", enabled=True)
    sqlite_session.add(account)
    sqlite_session.flush()
    sqlite_session.add(
        SourceArticle(
            account_id=account.id,
            account_name=account.name,
            title="测试文章",
            article_url="https://mp.weixin.qq.com/s/a",
            normalized_url="https://mp.weixin.qq.com/s/a",
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            content_text="body",
            content_hash="c" * 64,
        )
    )
    sqlite_session.commit()

    rows = account_service.list_accounts()

    assert rows[0].name == "光伏前沿"
    assert rows[0].masked_fakeid == "MzA1...6789"
    assert rows[0].article_count == 1


def test_sync_accounts_from_config_creates_and_updates(monkeypatch, sqlite_session, tmp_path: Path) -> None:
    config_path = tmp_path / "accounts.yml"
    config_path.write_text(
        "accounts:\n"
        "  - name: 光伏前沿\n"
        "    fakeid: MzA123456789\n"
        "    enabled: true\n",
        encoding="utf-8",
    )

    result = account_service.sync_accounts_from_config(config_path)

    assert result.created == 1
    assert result.updated == 0
    assert sqlite_session.query(MpAccount).one().name == "光伏前沿"


def test_set_account_enabled_updates_existing_account(sqlite_session) -> None:
    account = MpAccount(name="光伏前沿", fakeid="fakeid", enabled=True)
    sqlite_session.add(account)
    sqlite_session.commit()

    account_service.set_account_enabled(account.id, False)

    sqlite_session.refresh(account)
    assert account.enabled is False


def test_set_account_enabled_rejects_missing_account(sqlite_session) -> None:
    with pytest.raises(ValueError, match="Account not found"):
        account_service.set_account_enabled(999, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_account_service.py -v
```

Expected:

```text
ImportError: cannot import name 'account_service'
```

- [ ] **Step 3: Implement account service**

Create `src/market_info/web/services/account_service.py`.

Implementation requirements:

- `_mask_fakeid("MzA123456789") == "MzA1...6789"`.
- For fakeids shorter than 8 chars, return `"****"`.
- `sync_accounts_from_config()` uses `Settings().accounts_config_path` when no path is provided.
- Matching is by `fakeid`.
- Existing rows update `name` and `enabled`.
- Rows absent from config are left unchanged; `disabled_missing` remains `0` in this plan to avoid surprise disabling.

- [ ] **Step 4: Add accounts route and template**

Create `src/market_info/web/routes/accounts.py` with routes named in the interface.

Create `src/market_info/web/templates/accounts.html`:

- Page title: `公众号账号`
- Shows sync button.
- Shows table columns `名称`, `fakeid`, `启用`, `文章数`, `最近抓取`, `操作`.
- Enable/disable actions must be POST forms.
- Do not render raw `fakeid`.

Register router in `src/market_info/web/app.py` and nav in `base.html`.

- [ ] **Step 5: Add route smoke test**

Append to `tests/test_web_app.py`:

```python
def test_accounts_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/accounts")

    assert response.status_code == 200
    assert "公众号账号" in response.text
```

- [ ] **Step 6: Run Task 11 acceptance**

Run:

```powershell
python -m pytest tests/test_web_account_service.py tests/test_web_app.py -v
python -m pytest -q
```

Expected:

```text
Selected tests pass
Full test suite passes
```

**Prompt for Task 11 execution:**

```text
Implement Task 11 from docs/superpowers/plans/2026-07-02-market-info-ops-task10-13-plan.md. Use TDD. Add account service, /accounts routes, template, nav entry, and styling. Sync accounts from config/accounts.yml through existing load_accounts_config. Never show raw fakeid; use masked_fakeid. Run the Task 11 acceptance commands and report changed files plus verification output.
```

---

## Task 12: Delivery Audit and Report Send Logging

**Files:**
- Create: `src/market_info/web/services/delivery_service.py`
- Create: `src/market_info/web/routes/delivery.py`
- Create: `src/market_info/web/templates/delivery.html`
- Modify: `src/market_info/web/routes/reports.py`
- Modify: `src/market_info/web/routes/jobs.py`
- Modify: `src/market_info/web/app.py`
- Modify: `src/market_info/web/templates/base.html`
- Modify: `src/market_info/web/static/styles.css`
- Test: `tests/test_web_delivery_service.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes existing `PushLog` model.
- Consumes existing `market_info.jobs.weekly_job.send_report(excel_path: Path) -> None`.
- Produces `DeliveryLogItem` dataclass with fields `id`, `run_id`, `channel`, `status`, `recipient`, `subject`, `artifact_path`, `message`, `error_message`, `created_at`.
- Produces `DeliveryResult` dataclass with fields `status`, `artifact_path`, `error_message`.
- Produces `list_delivery_logs(limit: int = 100) -> list[DeliveryLogItem]`.
- Produces `record_delivery_log(channel: str, status: str, artifact_path: str | None = None, recipient: str | None = None, subject: str | None = None, message: str | None = None, error_message: str | None = None, run_id: str | None = None) -> DeliveryLogItem`.
- Produces `send_report_and_record(excel_path: Path) -> DeliveryResult`.
- Produces route `GET /delivery`.

- [ ] **Step 1: Write failing delivery service tests**

Create `tests/test_web_delivery_service.py`:

```python
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import PushLog
from market_info.web.services import delivery_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(delivery_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def test_record_and_list_delivery_logs(sqlite_session) -> None:
    created = delivery_service.record_delivery_log(
        channel="email",
        status="sent",
        artifact_path="exports/weekly.xlsx",
        recipient="ops@example.test",
        subject="weekly",
    )

    rows = delivery_service.list_delivery_logs()

    assert [row.id for row in rows] == [created.id]
    assert rows[0].status == "sent"
    assert rows[0].artifact_path == "exports/weekly.xlsx"


def test_send_report_and_record_writes_success(monkeypatch, sqlite_session, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(delivery_service, "send_report", lambda path: calls.append(path))
    excel_path = tmp_path / "weekly.xlsx"
    excel_path.write_bytes(b"xlsx")

    result = delivery_service.send_report_and_record(excel_path)

    assert calls == [excel_path]
    assert result.status == "sent"
    assert sqlite_session.query(PushLog).one().status == "sent"


def test_send_report_and_record_writes_failure_and_reraises(monkeypatch, sqlite_session, tmp_path: Path) -> None:
    def fail(path):
        raise RuntimeError("smtp failed\nsecret should not be here")

    monkeypatch.setattr(delivery_service, "send_report", fail)
    excel_path = tmp_path / "weekly.xlsx"
    excel_path.write_bytes(b"xlsx")

    with pytest.raises(RuntimeError, match="smtp failed"):
        delivery_service.send_report_and_record(excel_path)

    log = sqlite_session.query(PushLog).one()
    assert log.status == "failed"
    assert log.error_message == "smtp failed secret should not be here"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_delivery_service.py -v
```

Expected:

```text
ImportError: cannot import name 'delivery_service'
```

- [ ] **Step 3: Implement delivery service**

Create `src/market_info/web/services/delivery_service.py`.

Implementation requirements:

- `record_delivery_log()` inserts a `PushLog` row and commits.
- `list_delivery_logs()` orders by `PushLog.created_at.desc()` then `PushLog.id.desc()`.
- `send_report_and_record()` calls existing `send_report(excel_path)`.
- On success, record `channel="email"`, `status="sent"`, `artifact_path=str(excel_path)`.
- On failure, record `status="failed"` and normalized `error_message`, then re-raise the original exception.
- Do not render or store SMTP password, auth keys, or webhook URL.

- [ ] **Step 4: Add delivery page and wire report sends**

Create `src/market_info/web/routes/delivery.py` with `GET /delivery`.

Create `src/market_info/web/templates/delivery.html` showing delivery logs with columns `时间`, `渠道`, `状态`, `收件人`, `主题`, `文件`, `错误`.

Modify `src/market_info/web/routes/reports.py`:

- Replace direct `send_report` job target with `send_report_and_record`.

Modify `src/market_info/web/routes/jobs.py`:

- For the send-report POST route, use `send_report_and_record`.

Register delivery router and nav label `推送记录`.

- [ ] **Step 5: Add route smoke test**

Append to `tests/test_web_app.py`:

```python
def test_delivery_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/delivery")

    assert response.status_code == 200
    assert "推送记录" in response.text
```

- [ ] **Step 6: Run Task 12 acceptance**

Run:

```powershell
python -m pytest tests/test_web_delivery_service.py tests/test_web_app.py -v
python -m pytest -q
```

Expected:

```text
Selected tests pass
Full test suite passes
```

**Prompt for Task 12 execution:**

```text
Implement Task 12 from docs/superpowers/plans/2026-07-02-market-info-ops-task10-13-plan.md. Use TDD. Add delivery audit service/page, use PushLog, and route report resend actions through send_report_and_record so web sends are logged. Never log or render secrets. Run the Task 12 acceptance commands and report changed files plus verification output.
```

---

## Task 13: Optional Access Guard and Deployment Smoke

**Files:**
- Modify: `src/market_info/config.py`
- Modify: `.env.example`
- Create: `src/market_info/web/security.py`
- Modify: `src/market_info/web/app.py`
- Create: `scripts/smoke_web_console.py`
- Create: `docs/web-ops-runbook.md`
- Test: `tests/test_web_security.py`
- Test: `tests/test_smoke_scripts.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Adds setting `web_access_token: str = Field(default="", alias="WEB_ACCESS_TOKEN")`.
- Produces `is_public_path(path: str) -> bool`.
- Produces `is_authorized(headers: Mapping[str, str], token: str) -> bool`.
- Produces `install_access_guard(app: FastAPI, token: str) -> None`.
- `create_app(settings: Settings | None = None) -> FastAPI` installs the guard when `settings.web_access_token` is non-empty.
- Produces CLI script `python scripts/smoke_web_console.py --base-url http://127.0.0.1:8080 [--token TOKEN]`.

- [ ] **Step 1: Write failing security tests**

Create `tests/test_web_security.py`:

```python
from fastapi.testclient import TestClient

from market_info.config import Settings
from market_info.web.app import create_app
from market_info.web.security import is_authorized, is_public_path


def test_is_public_path_allows_static_assets() -> None:
    assert is_public_path("/static/styles.css") is True
    assert is_public_path("/") is False


def test_is_authorized_accepts_bearer_token() -> None:
    assert is_authorized({"authorization": "Bearer secret"}, "secret") is True
    assert is_authorized({"authorization": "Bearer wrong"}, "secret") is False
    assert is_authorized({}, "secret") is False


def test_app_allows_requests_when_token_not_configured() -> None:
    settings = Settings(WEB_ACCESS_TOKEN="")
    client = TestClient(create_app(settings=settings))

    response = client.get("/")

    assert response.status_code == 200


def test_app_requires_token_when_configured() -> None:
    settings = Settings(WEB_ACCESS_TOKEN="secret")
    client = TestClient(create_app(settings=settings))

    denied = client.get("/")
    allowed = client.get("/", headers={"Authorization": "Bearer secret"})

    assert denied.status_code == 401
    assert allowed.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_web_security.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'market_info.web.security'
```

- [ ] **Step 3: Implement access guard**

Modify `src/market_info/config.py`:

```python
web_access_token: str = Field(default="", alias="WEB_ACCESS_TOKEN")
```

Create `src/market_info/web/security.py`:

- `is_public_path()` returns true for `/static/` paths and `/favicon.ico`.
- `is_authorized()` accepts `Authorization: Bearer <token>` only.
- `install_access_guard()` adds FastAPI middleware that returns `JSONResponse({"detail": "Unauthorized"}, status_code=401)` when token is configured and request is not authorized.
- Use `hmac.compare_digest()` for token comparison.

Modify `src/market_info/web/app.py`:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Market Info Ops")
    ...
    install_access_guard(app, settings.web_access_token)
    return app
```

- [ ] **Step 4: Add deployment smoke script**

Create `scripts/smoke_web_console.py`:

```python
from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    routes = ["/", "/jobs", "/articles", "/reports", "/reviews", "/projects", "/quality"]
    with httpx.Client(timeout=10.0, headers=headers) as client:
        for route in routes:
            response = client.get(args.base_url.rstrip("/") + route)
            if response.status_code != 200 or "Market Info Ops" not in response.text:
                print(f"FAIL {route}: status={response.status_code}", file=sys.stderr)
                return 1
            print(f"OK {route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Append to `tests/test_smoke_scripts.py`:

```python
def test_smoke_web_console_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/smoke_web_console.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--base-url" in result.stdout
```

- [ ] **Step 5: Update docs and env example**

Modify `.env.example`:

```dotenv
WEB_ACCESS_TOKEN=
```

Create `docs/web-ops-runbook.md` with:

```markdown
# Market Info Ops Web Runbook

## Start Locally

`market-info web --host 127.0.0.1 --port 8080`

## Optional Access Token

Set `WEB_ACCESS_TOKEN` to require `Authorization: Bearer <token>` for web pages.

## Smoke Test

`python scripts/smoke_web_console.py --base-url http://127.0.0.1:8080`

With token:

`python scripts/smoke_web_console.py --base-url http://127.0.0.1:8080 --token <token>`

## Verification

`python -m pytest -q`
```

- [ ] **Step 6: Run Task 13 acceptance**

Run:

```powershell
python -m pytest tests/test_web_security.py tests/test_smoke_scripts.py tests/test_web_app.py -v
python -m pytest -q
market-info web --host 127.0.0.1 --port 8080
python scripts/smoke_web_console.py --base-url http://127.0.0.1:8080
```

Expected:

```text
Security tests pass
Full test suite passes
Smoke script prints OK for each route
```

**Prompt for Task 13 execution:**

```text
Implement Task 13 from docs/superpowers/plans/2026-07-02-market-info-ops-task10-13-plan.md. Use TDD. Add optional WEB_ACCESS_TOKEN protection, smoke_web_console.py, .env.example entry, and web ops runbook. Access guard must be disabled when token is empty and must accept only Authorization: Bearer <token> when configured. Run the Task 13 acceptance commands and report changed files plus verification output.
```

---

## Final Acceptance for Task 10-13

Run:

```powershell
python -m pytest tests/test_web_job_history_service.py tests/test_web_account_service.py tests/test_web_delivery_service.py tests/test_web_security.py tests/test_web_app.py -v
python -m pytest -q
alembic upgrade head
market-info web --host 127.0.0.1 --port 8080
python scripts/smoke_web_console.py --base-url http://127.0.0.1:8080
```

Open:

```text
http://127.0.0.1:8080/jobs
http://127.0.0.1:8080/accounts
http://127.0.0.1:8080/delivery
```

Expected:

```text
Job history persists, accounts can be viewed/synced/toggled, web report sends create PushLog audit rows, optional token protection works, and smoke script verifies all key pages.
```

## Self-Review Checklist

- Task 10 covers durable job history and logs.
- Task 11 covers account visibility and enable/disable operations.
- Task 12 covers delivery audit using existing `PushLog`.
- Task 13 covers optional access protection, smoke script, and runbook.
- No plan step asks implementers to render secrets, article body text, semantic text, or embeddings.
- Each task has exact files, interfaces, tests, acceptance commands, and execution prompt.
- Placeholder scan must return no matches for banned planning placeholders.
