from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, Timer
from typing import Any
from uuid import uuid4

from market_info.web.services import job_history_service


JobState = str


@dataclass
class JobStatus:
    id: str
    kind: str
    status: JobState
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: Any = None
    error_message: str | None = None
    logs: list[str] = field(default_factory=list)


class InMemoryJobRunner:
    def __init__(self, run_inline: bool = False, history_store=None) -> None:
        self.run_inline = run_inline
        self.history_store = history_store
        self._jobs: dict[str, JobStatus] = {}
        self._lock = Lock()

    def start_job(
        self,
        kind: str,
        target: Callable[..., object],
        kwargs: dict[str, object] | None = None,
    ) -> JobStatus:
        kwargs = kwargs or {}
        with self._lock:
            if self._has_running_kind(kind):
                rejected = JobStatus(
                    id=str(uuid4()),
                    kind=kind,
                    status="rejected",
                    created_at=_utc_now(),
                    error_message=f"{kind} is already running",
                )
                self._jobs[rejected.id] = rejected
                return rejected
            history_job = None
            if self.history_store is not None:
                history_job = self.history_store.create_job_run(kind, kwargs)
            job = JobStatus(
                id=history_job.id if history_job is not None else str(uuid4()),
                kind=kind,
                status="running",
                created_at=history_job.created_at if history_job is not None else _utc_now(),
                started_at=_utc_now(),
            )
            self._jobs[job.id] = job

        if self.history_store is not None:
            self.history_store.mark_job_started(job.id)
        if self.run_inline:
            self._run(job.id, target, kwargs)
        else:
            timer = Timer(0.01, self._run, args=(job.id, target, kwargs))
            timer.daemon = True
            timer.start()
        return job

    def get_job(self, job_id: str) -> JobStatus | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobStatus]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: _sort_datetime(job.created_at), reverse=True)

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.logs.append(message)
        if self.history_store is not None:
            self.history_store.append_job_log(job_id, message)

    def _run(self, job_id: str, target: Callable[..., object], kwargs: dict[str, object]) -> None:
        try:
            result = target(**kwargs)
        except Exception as exc:
            error_message = " ".join(str(exc).split())
            with self._lock:
                job = self._jobs[job_id]
                job.status = "failed"
                job.error_message = error_message
                job.finished_at = _utc_now()
            if self.history_store is not None:
                self.history_store.mark_job_failed(job_id, error_message)
            return
        with self._lock:
            job = self._jobs[job_id]
            job.status = "succeeded"
            job.result = result
            job.finished_at = _utc_now()
        if self.history_store is not None:
            self.history_store.mark_job_succeeded(job_id, result)

    def _has_running_kind(self, kind: str) -> bool:
        return any(job.kind == kind and job.status == "running" for job in self._jobs.values())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sort_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


job_runner = InMemoryJobRunner(history_store=job_history_service)
