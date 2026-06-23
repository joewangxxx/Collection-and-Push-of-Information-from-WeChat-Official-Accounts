from dataclasses import dataclass

from sqlalchemy.orm import Session

from market_info.db.models import MpAccount, SourceArticle
from market_info.ingest.url_normalizer import hash_content, normalize_article_url
from market_info.wechat.exporter_client import WechatExporterClient


@dataclass(frozen=True)
class IngestResult:
    inserted_articles: int = 0
    skipped_articles: int = 0
    failed_articles: int = 0


class ArticleIngestor:
    def __init__(self, client: WechatExporterClient, session: Session) -> None:
        self.client = client
        self.session = session

    def ingest_account(self, account: MpAccount, limit: int = 20) -> IngestResult:
        summaries = self.client.list_articles(account.fakeid, begin=0, size=limit)
        inserted_articles = 0
        skipped_articles = 0
        failed_articles = 0

        for summary in summaries:
            try:
                normalized_url = normalize_article_url(summary.url)
                if self._normalized_url_exists(normalized_url):
                    skipped_articles += 1
                    continue

                content_text = self.client.download_text(summary.url)
                content_hash = hash_content(content_text)
                if self._content_hash_exists_for_account(account.id, content_hash):
                    skipped_articles += 1
                    continue

                self.session.add(
                    SourceArticle(
                        account_id=account.id,
                        account_name=account.name,
                        title=summary.title,
                        article_url=summary.url,
                        normalized_url=normalized_url,
                        published_at=summary.published_at,
                        content_text=content_text,
                        content_hash=content_hash,
                    )
                )
                inserted_articles += 1
            except Exception:
                failed_articles += 1

        self.session.commit()
        return IngestResult(
            inserted_articles=inserted_articles,
            skipped_articles=skipped_articles,
            failed_articles=failed_articles,
        )

    def _normalized_url_exists(self, normalized_url: str) -> bool:
        return (
            self.session.query(SourceArticle)
            .filter_by(normalized_url=normalized_url)
            .first()
            is not None
        )

    def _content_hash_exists_for_account(self, account_id: int, content_hash: str) -> bool:
        return (
            self.session.query(SourceArticle)
            .filter_by(account_id=account_id, content_hash=content_hash)
            .first()
            is not None
        )
