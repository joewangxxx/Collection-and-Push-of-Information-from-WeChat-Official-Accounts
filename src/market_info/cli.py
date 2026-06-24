from pathlib import Path

import typer

from market_info.config import Settings
from market_info.db.session import get_session
from market_info.jobs.weekly_job import (
    WeeklyJobError,
    check_wechat_auth,
    get_processing_status_summary,
    ingest_enabled_accounts,
    process_pending_backlog,
    run_weekly,
    send_report,
)


app = typer.Typer()


def get_backlog_status():
    with get_session() as session:
        return get_processing_status_summary(session)


def _format_backlog_status(summary) -> str:
    return (
        f"pending={summary.pending} "
        f"failed_retryable={summary.failed_retryable} "
        f"failed_exhausted={summary.failed_exhausted} "
        f"processed={summary.processed} "
        f"total={summary.total}"
    )


@app.command("check-auth")
def check_auth_command() -> None:
    settings = Settings()
    if check_wechat_auth(settings=settings):
        typer.echo("wechat exporter auth valid")
    else:
        typer.echo("wechat exporter auth invalid; please scan login again")


@app.command("ingest")
def ingest_command(limit: int = typer.Option(20, "--limit")) -> None:
    results = ingest_enabled_accounts(limit=limit)
    for result in results:
        typer.echo(
            f"{result.account_name}: "
            f"inserted={result.inserted_articles} "
            f"skipped={result.skipped_articles} "
            f"failed={result.failed_articles}"
        )


@app.command("send-report")
def send_report_command(excel_path: Path = typer.Option(..., "--excel-path")) -> None:
    send_report(excel_path)
    typer.echo("report email sent")


@app.command("pending-status")
def pending_status_command() -> None:
    summary = get_backlog_status()
    typer.echo(f"pending={summary.pending}")
    typer.echo(f"failed_retryable={summary.failed_retryable}")
    typer.echo(f"failed_exhausted={summary.failed_exhausted}")
    typer.echo(f"processed={summary.processed}")
    typer.echo(f"total={summary.total}")


@app.command("process-pending")
def process_pending_command(limit: int = typer.Option(20, "--limit", min=1)) -> None:
    try:
        before = get_backlog_status()
        typer.echo(f"before: {_format_backlog_status(before)}")
        result = process_pending_backlog(limit=limit, progress_callback=typer.echo)
        typer.echo(
            f"processed batch: "
            f"new_projects={result.new_projects} "
            f"merged_projects={result.merged_projects} "
            f"review_projects={result.review_projects} "
            f"status_events={result.status_events}"
        )
        after = get_backlog_status()
        typer.echo(f"after: {_format_backlog_status(after)}")
    except WeeklyJobError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc


@app.command("run-weekly")
def run_weekly_command(limit: int = typer.Option(20, "--limit")) -> None:
    try:
        summary = run_weekly(limit=limit, progress_callback=typer.echo)
    except WeeklyJobError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(f"新增文章数: {summary.new_articles}")
    typer.echo(f"新增项目数: {summary.new_projects}")
    typer.echo(f"合并/更新项目数: {summary.merged_projects}")
    typer.echo(f"疑似重复待复核数: {summary.review_projects}")
    typer.echo(f"状态变化事件数: {summary.status_events}")
    typer.echo(f"Excel 文件路径: {summary.excel_path}")
    typer.echo(f"邮件发送结果: {'sent' if summary.email_sent else 'not sent'}")
