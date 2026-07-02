from fastapi import APIRouter, Request

from market_info.web.templating import templates
from market_info.web.services.dashboard_service import get_dashboard_overview


router = APIRouter()


@router.get("/")
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        name="dashboard.html",
        request=request,
        context={
            "request": request,
            "active_nav": "dashboard",
            "page_title": "总览",
            "overview": get_dashboard_overview(),
        },
    )
