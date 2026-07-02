from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from market_info.jobs.weekly_job import retry_failed_articles
from market_info.web.templating import templates
from market_info.web.services.article_service import count_articles_by_status, list_articles
from market_info.web.services.dashboard_service import mask_error
from market_info.web.services.job_runner import job_runner


router = APIRouter(prefix="/articles")


@router.get("")
def articles_page(
    request: Request,
    status: str | None = None,
    account_name: str | None = None,
):
    error_message = ""
    try:
        articles = list_articles(status=status, account_name=account_name)
        counts = count_articles_by_status()
    except Exception as exc:
        articles = []
        counts = {"pending": 0, "failed": 0, "processed": 0}
        error_message = mask_error(exc)
    return templates.TemplateResponse(
        name="articles.html",
        request=request,
        context={
            "request": request,
            "active_nav": "articles",
            "page_title": "文章队列",
            "articles": articles,
            "counts": counts,
            "selected_status": status or "",
            "selected_account": account_name or "",
            "error_message": error_message,
        },
    )


@router.post("/retry")
def retry_articles(article_ids: str = Form(...), include_exhausted: bool = Form(False)):
    parsed_ids = [int(item.strip()) for item in article_ids.split(",") if item.strip()]
    job_runner.start_job(
        "retry_failed",
        retry_failed_articles,
        {
            "article_ids": parsed_ids,
            "include_exhausted": include_exhausted,
        },
    )
    return RedirectResponse("/articles?status=failed", status_code=303)
