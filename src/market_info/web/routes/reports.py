from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from market_info.web.services.delivery_service import send_report_and_record
from market_info.web.templating import templates
from market_info.web.services.job_runner import job_runner
from market_info.web.services.report_service import list_reports, resolve_report_path


router = APIRouter(prefix="/reports")


@router.get("")
def reports_page(request: Request):
    return templates.TemplateResponse(
        name="reports.html",
        request=request,
        context={
            "request": request,
            "active_nav": "reports",
            "page_title": "周报文件",
            "reports": list_reports(),
        },
    )


@router.get("/{report_name}/download")
def download_report(report_name: str):
    try:
        path = resolve_report_path(report_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@router.post("/{report_name}/send")
def send_existing_report(report_name: str):
    try:
        path = resolve_report_path(report_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    job_runner.start_job("send_report", send_report_and_record, {"excel_path": path})
    return RedirectResponse("/reports", status_code=303)
