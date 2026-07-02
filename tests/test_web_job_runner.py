from datetime import datetime, timezone
from threading import Event

from market_info.web.services.job_runner import InMemoryJobRunner


def test_runner_records_successful_job() -> None:
    runner = InMemoryJobRunner(run_inline=True)

    job = runner.start_job("check_auth", lambda: "ok")

    stored = runner.get_job(job.id)
    assert stored is not None
    assert stored.status == "succeeded"
    assert stored.result == "ok"
    assert stored.error_message is None


def test_runner_records_failed_job() -> None:
    runner = InMemoryJobRunner(run_inline=True)

    def fail():
        raise RuntimeError("network failed")

    job = runner.start_job("check_auth", fail)

    stored = runner.get_job(job.id)
    assert stored is not None
    assert stored.status == "failed"
    assert stored.error_message == "network failed"


def test_runner_rejects_second_running_same_kind() -> None:
    runner = InMemoryJobRunner(run_inline=False)

    first = runner.start_job("run_weekly", lambda: "ok")
    second = runner.start_job("run_weekly", lambda: "ok")

    assert first.status == "running"
    assert second.status == "rejected"
    assert "already running" in (second.error_message or "")


class FakeHistoryStore:
    def __init__(self):
        self.created = []
        self.started = []
        self.succeeded = []
        self.failed = []
        self.logs = []

    def create_job_run(self, kind, params=None):
        from datetime import datetime
        from market_info.web.services.job_runner import JobStatus

        job = JobStatus(id="stored-1", kind=kind, status="running", created_at=datetime.now())
        self.created.append((kind, params))
        return job

    def mark_job_started(self, job_id):
        self.started.append(job_id)

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
    assert store.started == ["stored-1"]
    assert store.succeeded == [("stored-1", "ok")]


def test_runner_lists_aware_history_and_rejected_jobs() -> None:
    class AwareHistoryStore(FakeHistoryStore):
        def create_job_run(self, kind, params=None):
            from market_info.web.services.job_runner import JobStatus

            job = JobStatus(
                id="stored-aware-1",
                kind=kind,
                status="running",
                created_at=datetime.now(timezone.utc),
            )
            self.created.append((kind, params))
            return job

    blocker = Event()
    store = AwareHistoryStore()
    runner = InMemoryJobRunner(run_inline=False, history_store=store)

    try:
        first = runner.start_job("check_auth", lambda: blocker.wait(5))
        second = runner.start_job("check_auth", lambda: "ok")

        jobs = runner.list_jobs()
    finally:
        blocker.set()

    assert first.status == "running"
    assert second.status == "rejected"
    assert {job.status for job in jobs} >= {"running", "rejected"}
