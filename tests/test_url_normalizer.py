import pytest

from market_info.ingest.url_normalizer import hash_content, normalize_article_url


def test_normalize_article_url_keeps_identity_params_sorted() -> None:
    url = (
        "https://mp.weixin.qq.com/s?sn=abc&utm_source=x&idx=1&mid=2"
        "&__biz=biz&from=timeline#rd"
    )

    normalized = normalize_article_url(url)

    assert normalized == "https://mp.weixin.qq.com/s?__biz=biz&idx=1&mid=2&sn=abc"


def test_normalize_article_url_lowercases_scheme_and_host() -> None:
    url = "HTTPS://MP.WEIXIN.QQ.COM/s?MID=ignored&mid=2&sn=abc"

    normalized = normalize_article_url(url)

    assert normalized == "https://mp.weixin.qq.com/s?mid=2&sn=abc"


def test_normalize_article_url_rejects_empty_url() -> None:
    with pytest.raises(ValueError):
        normalize_article_url("")


def test_hash_content_ignores_surrounding_whitespace() -> None:
    assert hash_content("  正文内容  ") == hash_content("正文内容")
