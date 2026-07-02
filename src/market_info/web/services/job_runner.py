from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock, Timer
from typing import Any
from uuid import uuid4


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
    def __init__(self, run_inline: bool = False) -> None:
        self.run_inline = run_inline
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
                    created_at=datetime.now(),
                    error_message=f"{kind} is already running",
                )
                self._jobs[rejected.id] = rejected
                return rejected
            job = JobStatus(
                id=str(uuid4()),
                kind=kind,
                status="running",
                created_at=datetime.now(),
                started_at=datetime.now(),
            )
            self._jobs[job.id] = job

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
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.logs.append(message)

    def _run(self, job_id: str, target: Callable[..., object], kwargs: dict[str, object]) -> None:
        try:
            result = target(**kwargs)
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job.status = "failed"
                job.error_message = " ".join(str(exc).split())
                job.finished_at = datetime.now()
            return
        with self._lock:
            job = self._jobs[job_id]
            job.status = "succeeded"
            job.result = result
            job.finished_at = datetime.now()

    def _has_running_kind(self, kind: str) -> bool:
        return any(job.kind == kind and job.status == "running" for job in self._jobs.values())


job_runner = InMemoryJobRunner()
