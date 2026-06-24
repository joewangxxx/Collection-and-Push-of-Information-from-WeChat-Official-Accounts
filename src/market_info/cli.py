from pathlib import Path

import typer

from market_info.config import Settings
from market_info.jobs.weekly_job import (
    WeeklyJobError,
    check_wechat_auth,
    ingest_enabled_accounts,
    run_weekly,
    send_report,
)


app = typer.Typer()


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


@app.command("run-weekly")
def run_weekly_command(limit: int = typer.Option(20, "--limit")) -> None:
    try:
        summary = run_weekly(limit=limit)
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
