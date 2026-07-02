from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from market_info.jobs.weekly_job import (
    check_wechat_auth,
    process_pending_backlog,
    retry_failed_articles,
    run_weekly,
)
from market_info.web.services.dashboard_service import mask_error
from market_info.web.services.delivery_service import send_report_and_record
from market_info.web.services.job_history_service import get_job_history, list_job_history
from market_info.web.services.job_runner import job_runner
from market_info.web.templating import templates


router = APIRouter(prefix="/jobs")


@router.get("")
def jobs_page(request: Request):
    error_message = ""
    try:
        jobs = list_job_history()
    except Exception as exc:
        jobs = job_runner.list_jobs()
        error_message = mask_error(exc)
    return templates.TemplateResponse(
        name="jobs.html",
        request=request,
        context={
            "request": request,
            "active_nav": "jobs",
            "page_title": "运行中心",
            "jobs": jobs,
            "running_jobs": job_runner.list_jobs(),
            "error_message": error_message,
        },
    )


@router.post("/check-auth")
def start_check_auth():
    job_runner.start_job("check_auth", check_wechat_auth)
    return RedirectResponse("/jobs", status_code=303)


@router.post("/run-weekly")
def start_run_weekly(limit: int = Form(10)):
    job_runner.start_job("run_weekly", run_weekly, {"limit": limit})
    return RedirectResponse("/jobs", status_code=303)


@router.post("/process-pending")
def start_process_pending(limit: int = Form(20)):
    job_runner.start_job("process_pending", process_pending_backlog, {"limit": limit})
    return RedirectResponse("/jobs", status_code=303)


@router.post("/retry-failed")
def start_retry_failed(article_ids: str = Form(...), include_exhausted: bool = Form(False)):
    parsed_ids = [int(item.strip()) for item in article_ids.split(",") if item.strip()]
    job_runner.start_job(
        "retry_failed",
        retry_failed_articles,
        {
            "article_ids": parsed_ids,
            "include_exhausted": include_exhausted,
        },
    )
    return RedirectResponse("/jobs", status_code=303)


@router.post("/send-report")
def start_send_report(excel_path: str = Form(...)):
    job_runner.start_job("send_report", send_report_and_record, {"excel_path": Path(excel_path)})
    return RedirectResponse("/jobs", status_code=303)


@router.get("/{job_id}")
def job_detail(request: Request, job_id: str):
    try:
        job = get_job_history(job_id)
    except Exception:
        job = None
    if job is None:
        job = job_runner.get_job(job_id)
    return templates.TemplateResponse(
        name="job_detail.html",
        request=request,
        context={
            "request": request,
            "active_nav": "jobs",
            "page_title": "任务详情",
            "job": job,
        },
    )
