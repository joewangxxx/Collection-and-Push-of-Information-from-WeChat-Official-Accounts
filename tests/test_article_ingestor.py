from datetime import datetime, timezone

from market_info.db.models import MpAccount, SourceArticle
from market_info.ingest.article_ingestor import ArticleIngestor
from market_info.wechat.exporter_client import WechatArticleSummary, WechatExporterError


class FakeQuery:
    def __init__(self, session: "FakeSession") -> None:
        self.session = session
        self.filters: dict[str, object] = {}

    def filter_by(self, **kwargs: object) -> "FakeQuery":
        self.filters.update(kwargs)
        return self

    def first(self) -> SourceArticle | None:
        normalized_url = self.filters.get("normalized_url")
        if normalized_url in self.session.existing_normalized_urls:
            return SourceArticle(normalized_url=str(normalized_url), content_hash="existing")

        account_id = self.filters.get("account_id")
        content_hash = self.filters.get("content_hash")
        if (account_id, content_hash) in self.session.existing_content_hashes:
            return SourceArticle(
                account_id=int(account_id),
                normalized_url="existing",
                content_hash=str(content_hash),
            )

        return None


class FakeSession:
    def __init__(self) -> None:
        self.existing_normalized_urls: set[str] = set()
        self.existing_content_hashes: set[tuple[int, str]] = set()
        self.added: list[SourceArticle] = []
        self.commits = 0

    def query(self, model: type[SourceArticle]) -> FakeQuery:
        assert model is SourceArticle
        return FakeQuery(self)

    def add(self, article: SourceArticle) -> None:
        self.added.append(article)

    def commit(self) -> None:
        self.commits += 1


class FakeClient:
    def __init__(
        self,
        articles: list[WechatArticleSummary],
        bodies: dict[str, str],
        failing_urls: set[str] | None = None,
    ) -> None:
        self.articles = articles
        self.bodies = bodies
        self.failing_urls = failing_urls or set()
        self.downloaded_urls: list[str] = []

    def list_articles(self, fakeid: str, begin: int = 0, size: int = 5) -> list[WechatArticleSummary]:
        return self.articles[:size]

    def download_text(self, url: str) -> str:
        self.downloaded_urls.append(url)
        if url in self.failing_urls:
            raise WechatExporterError("download failed")
        return self.bodies[url]


def make_account() -> MpAccount:
    return MpAccount(id=1, name="测试公众号", fakeid="fakeid123", enabled=True)


def make_summary(url: str, title: str = "测试文章") -> WechatArticleSummary:
    return WechatArticleSummary(
        title=title,
        url=url,
        published_at=datetime(2024, 3, 10, tzinfo=timezone.utc),
    )


def test_ingest_account_inserts_new_article() -> None:
    url = "https://mp.weixin.qq.com/s?__biz=biz&mid=1&idx=1&sn=abc"
    client = FakeClient([make_summary(url)], {url: "正文内容"})
    session = FakeSession()

    result = ArticleIngestor(client, session).ingest_account(make_account(), limit=5)

    assert result.inserted_articles == 1
    assert result.skipped_articles == 0
    assert result.failed_articles == 0
    assert len(session.added) == 1
    assert session.added[0].account_name == "测试公众号"
    assert session.commits == 1


def test_ingest_account_skips_existing_normalized_url_without_download() -> None:
    url = "https://mp.weixin.qq.com/s?__biz=biz&mid=1&idx=1&sn=abc&utm_source=x"
    normalized = "https://mp.weixin.qq.com/s?__biz=biz&idx=1&mid=1&sn=abc"
    client = FakeClient([make_summary(url)], {url: "正文内容"})
    session = FakeSession()
    session.existing_normalized_urls.add(normalized)

    result = ArticleIngestor(client, session).ingest_account(make_account())

    assert result.inserted_articles == 0
    assert result.skipped_articles == 1
    assert result.failed_articles == 0
    assert client.downloaded_urls == []
    assert session.added == []


def test_ingest_account_skips_existing_content_hash_for_same_account() -> None:
    url = "https://mp.weixin.qq.com/s?__biz=biz&mid=1&idx=1&sn=abc"
    body = "重复正文"
    client = FakeClient([make_summary(url)], {url: body})
    session = FakeSession()
    from market_info.ingest.url_normalizer import hash_content

    session.existing_content_hashes.add((1, hash_content(body)))

    result = ArticleIngestor(client, session).ingest_account(make_account())

    assert result.inserted_articles == 0
    assert result.skipped_articles == 1
    assert result.failed_articles == 0
    assert session.added == []


def test_ingest_account_continues_when_one_article_download_fails() -> None:
    failed_url = "https://mp.weixin.qq.com/s?__biz=biz&mid=1&idx=1&sn=fail"
    ok_url = "https://mp.weixin.qq.com/s?__biz=biz&mid=2&idx=1&sn=ok"
    client = FakeClient(
        [make_summary(failed_url, "失败文章"), make_summary(ok_url, "成功文章")],
        {ok_url: "成功正文"},
        failing_urls={failed_url},
    )
    session = FakeSession()

    result = ArticleIngestor(client, session).ingest_account(make_account(), limit=2)

    assert result.inserted_articles == 1
    assert result.skipped_articles == 0
    assert result.failed_articles == 1
    assert len(session.added) == 1
    assert session.added[0].title == "成功文章"
