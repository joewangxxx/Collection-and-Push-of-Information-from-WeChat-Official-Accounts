from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from market_info.web.services.dashboard_service import mask_error
from market_info.web.services.review_service import (
    get_review_record,
    list_project_candidates,
    list_review_records,
    resolve_review_record,
)
from market_info.web.templating import templates


router = APIRouter(prefix="/reviews")


@router.get("")
def reviews_page(request: Request):
    error_message = ""
    try:
        records = list_review_records()
    except Exception as exc:
        records = []
        error_message = mask_error(exc)
    return templates.TemplateResponse(
        name="reviews.html",
        request=request,
        context={
            "request": request,
            "active_nav": "reviews",
            "page_title": "复核工作台",
            "records": records,
            "error_message": error_message,
        },
    )


@router.get("/{record_id}")
def review_detail_page(request: Request, record_id: int, q: str | None = None):
    try:
        record = get_review_record(record_id)
        candidates = list_project_candidates(record_id, query=q)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        name="review_detail.html",
        request=request,
        context={
            "request": request,
            "active_nav": "reviews",
            "page_title": "复核详情",
            "record": record,
            "candidates": candidates,
            "query": q or "",
        },
    )


@router.post("/{record_id}/new")
def resolve_as_new(record_id: int):
    try:
        resolve_review_record(record_id, "new")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/reviews", status_code=303)


@router.post("/{record_id}/merge")
def resolve_as_merge(record_id: int, project_id: int = Form(...)):
    try:
        resolve_review_record(record_id, "merge", project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/reviews", status_code=303)
