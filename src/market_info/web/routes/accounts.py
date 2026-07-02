from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from market_info.web.services.account_service import (
    list_accounts,
    set_account_enabled,
    sync_accounts_from_config,
)
from market_info.web.services.dashboard_service import mask_error
from market_info.web.templating import templates


router = APIRouter(prefix="/accounts")


@router.get("")
def accounts_page(request: Request):
    error_message = ""
    try:
        accounts = list_accounts()
    except Exception as exc:
        accounts = []
        error_message = mask_error(exc)
    return templates.TemplateResponse(
        name="accounts.html",
        request=request,
        context={
            "request": request,
            "active_nav": "accounts",
            "page_title": "公众号账号",
            "accounts": accounts,
            "error_message": error_message,
        },
    )


@router.post("/sync")
def sync_accounts():
    sync_accounts_from_config()
    return RedirectResponse("/accounts", status_code=303)


@router.post("/{account_id}/enable")
def enable_account(account_id: int):
    if set_account_enabled(account_id, True) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return RedirectResponse("/accounts", status_code=303)


@router.post("/{account_id}/disable")
def disable_account(account_id: int):
    if set_account_enabled(account_id, False) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return RedirectResponse("/accounts", status_code=303)
