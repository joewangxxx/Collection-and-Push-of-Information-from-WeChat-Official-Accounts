from fastapi import APIRouter, Request

from market_info.web.services.dashboard_service import mask_error
from market_info.web.services.delivery_service import list_delivery_logs
from market_info.web.templating import templates


router = APIRouter(prefix="/delivery")


@router.get("")
def delivery_page(request: Request):
    error_message = ""
    try:
        logs = list_delivery_logs()
    except Exception as exc:
        logs = []
        error_message = mask_error(exc)
    return templates.TemplateResponse(
        name="delivery.html",
        request=request,
        context={
            "request": request,
            "active_nav": "delivery",
            "page_title": "推送记录",
            "logs": logs,
            "error_message": error_message,
        },
    )
