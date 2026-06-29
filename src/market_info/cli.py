from pathlib import Path

import typer

from market_info.config import Settings
from market_info.db.session import get_session
from market_info.evaluation import evaluate_golden, export_golden_template
from market_info.jobs.weekly_job import (
    WeeklyJobError,
    check_wechat_auth,
    get_processing_status_summary,
    ingest_enabled_accounts,
    process_pending_backlog,
    retry_failed_articles,
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


def _format_ids(values: list[int]) -> str:
    return ",".join(str(value) for value in values)


def _parse_article_ids(value: str) -> list[int]:
    try:
        article_ids = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise typer.BadParameter("article-ids must be comma-separated integers") from exc
    if not article_ids:
        raise typer.BadParameter("article-ids must include at least one integer")
    return article_ids


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


@app.command("retry-failed")
def retry_failed_command(
    article_ids: str = typer.Option(..., "--article-ids"),
    include_exhausted: bool = typer.Option(False, "--include-exhausted"),
) -> None:
    try:
        parsed_ids = _parse_article_ids(article_ids)
        result = retry_failed_articles(
            parsed_ids,
            include_exhausted=include_exhausted,
            progress_callback=typer.echo,
        )
        typer.echo(f"requested_ids={_format_ids(result.requested_ids)}")
        typer.echo(f"processed_ids={_format_ids(result.processed_ids)}")
        typer.echo(f"skipped_ids={_format_ids(result.skipped_ids)}")
        typer.echo(
            f"retry batch: "
            f"new_projects={result.processing_result.new_projects} "
            f"merged_projects={result.processing_result.merged_projects} "
            f"review_projects={result.processing_result.review_projects} "
            f"status_events={result.processing_result.status_events}"
        )
        after = get_backlog_status()
        typer.echo(f"after: {_format_backlog_status(after)}")
    except typer.BadParameter as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    except WeeklyJobError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc


@app.command("export-golden")
def export_golden_command(
    output_dir: Path = typer.Option(
        Path("data/golden_articles"),
        "--output-dir",
    ),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    with get_session() as session:
        labels_path = export_golden_template(session, output_dir, limit)
    typer.echo(f"golden labels template exported: {labels_path}")


@app.command("eval-golden")
def eval_golden_command(
    labels: Path = typer.Option(..., "--labels"),
    report_path: Path | None = typer.Option(None, "--report-path"),
) -> None:
    report = evaluate_golden(labels, report_path=report_path)
    output_report_path = report_path or labels.parent / "evaluation_report.json"
    typer.echo(f"project_precision={report.extraction.project_precision:g}")
    typer.echo(f"project_recall={report.extraction.project_recall:g}")
    typer.echo(f"field_accuracy={report.extraction.field_accuracy:g}")
    typer.echo(f"status_accuracy={report.extraction.status_accuracy:g}")
    typer.echo(f"investment_accuracy={report.extraction.investment_accuracy:g}")
    typer.echo(f"hallucination_count={report.extraction.hallucination_count}")
    typer.echo(f"missed_count={report.extraction.missed_count}")
    typer.echo(f"dedupe_accuracy={report.dedupe.dedupe_accuracy:g}")
    typer.echo(f"false_merge_count={report.dedupe.false_merge_count}")
    typer.echo(f"missed_merge_count={report.dedupe.missed_merge_count}")
    typer.echo(f"status_change_accuracy={report.dedupe.status_change_accuracy:g}")
    typer.echo(f"report_path={output_report_path}")


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
