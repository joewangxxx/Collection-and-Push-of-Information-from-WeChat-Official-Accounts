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
