from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from market_info.jobs.weekly_job import (
    check_wechat_auth,
    process_pending_backlog,
    retry_failed_articles,
    run_weekly,
    send_report,
)
from market_info.web.templating import templates
from market_info.web.services.job_runner import job_runner


router = APIRouter(prefix="/jobs")


@router.get("")
def jobs_page(request: Request):
    return templates.TemplateResponse(
        name="jobs.html",
        request=request,
        context={
            "request": request,
            "active_nav": "jobs",
            "page_title": "运行中心",
            "jobs": job_runner.list_jobs(),
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
    job_runner.start_job("send_report", send_report, {"excel_path": Path(excel_path)})
    return RedirectResponse("/jobs", status_code=303)


@router.get("/{job_id}")
def job_detail(request: Request, job_id: str):
    job = job_runner.get_job(job_id)
    return templates.TemplateResponse(
        name="jobs.html",
        request=request,
        context={
            "request": request,
            "active_nav": "jobs",
            "page_title": "运行中心",
            "jobs": job_runner.list_jobs(),
            "selected_job": job,
        },
    )
