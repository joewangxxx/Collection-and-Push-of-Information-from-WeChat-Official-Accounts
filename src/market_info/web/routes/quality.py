from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from market_info.web.services.job_runner import job_runner
from market_info.web.services.quality_service import (
    build_quality_overview,
    evaluate_golden_for_web,
    export_golden_for_web,
)
from market_info.web.templating import templates


router = APIRouter(prefix="/quality")


@router.get("")
def quality_page(request: Request):
    return templates.TemplateResponse(
        name="quality.html",
        request=request,
        context={
            "request": request,
            "active_nav": "quality",
            "page_title": "质量与设置",
            "overview": build_quality_overview(),
            "jobs": job_runner.list_jobs(),
        },
    )


@router.post("/export-golden")
def start_export_golden(limit: int = Form(20), output_dir: str = Form("data/golden_articles")):
    job_runner.start_job(
        "export_golden",
        export_golden_for_web,
        {"output_dir": Path(output_dir), "limit": limit},
    )
    return RedirectResponse("/quality", status_code=303)


@router.post("/eval-golden")
def start_eval_golden(
    labels_path: str = Form("data/golden_articles/golden_labels.xlsx"),
    report_path: str = Form("data/golden_articles/evaluation_report.json"),
):
    job_runner.start_job(
        "eval_golden",
        evaluate_golden_for_web,
        {"labels_path": Path(labels_path), "report_path": Path(report_path)},
    )
    return RedirectResponse("/quality", status_code=303)
