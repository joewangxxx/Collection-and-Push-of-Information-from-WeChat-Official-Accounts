from dataclasses import dataclass
from datetime import datetime

from market_info.db.models import SourceArticle
from market_info.db.session import get_session


@dataclass(frozen=True)
class ArticleQueueItem:
    id: int
    account_name: str
    title: str
    article_url: str
    published_at: datetime | None
    status: str
    attempts: int
    extraction_error: str
    processed_at: datetime | None


def list_articles(
    status: str | None = None,
    account_name: str | None = None,
    limit: int = 100,
) -> list[ArticleQueueItem]:
    with get_session() as session:
        query = session.query(SourceArticle)
        if status:
            query = query.filter(SourceArticle.processing_status == status)
        if account_name:
            query = query.filter(SourceArticle.account_name == account_name)
        rows = (
            query.order_by(SourceArticle.created_at.desc(), SourceArticle.id.desc())
            .limit(limit)
            .all()
        )
        return [_to_item(row) for row in rows]


def count_articles_by_status() -> dict[str, int]:
    with get_session() as session:
        return {
            "pending": session.query(SourceArticle)
            .filter(SourceArticle.processing_status == "pending")
            .count(),
            "failed": session.query(SourceArticle)
            .filter(SourceArticle.processing_status == "failed")
            .count(),
            "processed": session.query(SourceArticle)
            .filter(SourceArticle.processing_status == "processed")
            .count(),
        }


def _to_item(article: SourceArticle) -> ArticleQueueItem:
    return ArticleQueueItem(
        id=article.id,
        account_name=article.account_name,
        title=article.title,
        article_url=article.article_url,
        published_at=article.published_at,
        status=article.processing_status,
        attempts=article.extraction_attempts or 0,
        extraction_error=article.extraction_error or "",
        processed_at=article.processed_at,
    )
