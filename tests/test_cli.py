from pathlib import Path

from typer.testing import CliRunner

from market_info.cli import app


runner = CliRunner()


def test_check_auth_prints_valid_when_auth_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("market_info.cli.Settings", lambda: object())
    monkeypatch.setattr("market_info.cli.check_wechat_auth", lambda settings: True)

    result = runner.invoke(app, ["check-auth"])

    assert result.exit_code == 0
    assert "wechat exporter auth valid" in result.output


def test_check_auth_prints_invalid_when_auth_fails(monkeypatch) -> None:
    monkeypatch.setattr("market_info.cli.Settings", lambda: object())
    monkeypatch.setattr("market_info.cli.check_wechat_auth", lambda settings: False)

    result = runner.invoke(app, ["check-auth"])

    assert result.exit_code == 0
    assert "wechat exporter auth invalid; please scan login again" in result.output


def test_ingest_calls_ingest_enabled_accounts_with_limit_and_prints_counts(monkeypatch) -> None:
    calls = []

    class Result:
        account_name = "test-account"
        inserted_articles = 2
        skipped_articles = 1
        failed_articles = 0

    def fake_ingest_enabled_accounts(limit: int):
        calls.append(limit)
        return [Result()]

    monkeypatch.setattr("market_info.cli.ingest_enabled_accounts", fake_ingest_enabled_accounts)

    result = runner.invoke(app, ["ingest", "--limit", "5"])

    assert result.exit_code == 0
    assert calls == [5]
    assert "test-account: inserted=2 skipped=1 failed=0" in result.output


def test_send_report_calls_send_report_and_prints_success(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("market_info.cli.send_report", lambda path: calls.append(path))

    result = runner.invoke(app, ["send-report", "--excel-path", "sample.xlsx"])

    assert result.exit_code == 0
    assert calls == [Path("sample.xlsx")]
    assert "report email sent" in result.output


def test_run_weekly_failure_returns_exit_code_1_and_prints_error(monkeypatch) -> None:
    from market_info.jobs.weekly_job import WeeklyJobError

    def fail_run_weekly(limit: int, progress_callback=None):
        raise WeeklyJobError("auth failed")

    monkeypatch.setattr("market_info.cli.run_weekly", fail_run_weekly)

    result = runner.invoke(app, ["run-weekly", "--limit", "20"])

    assert result.exit_code == 1
    assert "auth failed" in result.output


def test_run_weekly_success_prints_summary(monkeypatch, tmp_path) -> None:
    class Summary:
        new_articles = 3
        new_projects = 1
        merged_projects = 2
        review_projects = 1
        status_events = 4
        excel_path = tmp_path / "weekly.xlsx"
        email_sent = True

    monkeypatch.setattr("market_info.cli.run_weekly", lambda limit, progress_callback=None: Summary())

    result = runner.invoke(app, ["run-weekly", "--limit", "20"])

    assert result.exit_code == 0
    assert "新增文章数: 3" in result.output
    assert "新增项目数: 1" in result.output
    assert "合并/更新项目数: 2" in result.output
    assert "疑似重复待复核数: 1" in result.output
    assert "状态变化事件数: 4" in result.output
    assert f"Excel 文件路径: {tmp_path / 'weekly.xlsx'}" in result.output
    assert "邮件发送结果: sent" in result.output
