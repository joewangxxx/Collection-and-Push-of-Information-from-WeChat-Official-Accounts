from fastapi import APIRouter, HTTPException, Request

from market_info.web.services.dashboard_service import mask_error
from market_info.web.services.project_service import get_project_detail, list_projects
from market_info.web.templating import templates


router = APIRouter(prefix="/projects")


@router.get("")
def projects_page(
    request: Request,
    q: str | None = None,
    province: str | None = None,
    status: str | None = None,
):
    error_message = ""
    try:
        projects = list_projects(query=q, province=province, status=status)
    except Exception as exc:
        projects = []
        error_message = mask_error(exc)
    return templates.TemplateResponse(
        name="projects.html",
        request=request,
        context={
            "request": request,
            "active_nav": "projects",
            "page_title": "项目台账",
            "projects": projects,
            "query": q or "",
            "selected_province": province or "",
            "selected_status": status or "",
            "error_message": error_message,
        },
    )


@router.get("/{project_id}")
def project_detail_page(request: Request, project_id: int):
    try:
        detail = get_project_detail(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        name="project_detail.html",
        request=request,
        context={
            "request": request,
            "active_nav": "projects",
            "page_title": "项目详情",
            "detail": detail,
        },
    )
