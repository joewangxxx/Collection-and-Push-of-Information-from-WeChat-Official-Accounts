from datetime import datetime

import pytest

from market_info.wechat.exporter_client import (
    WechatExporterAuthError,
    WechatExporterClient,
    WechatExporterError,
)


def test_check_auth_success(respx_mock) -> None:
    respx_mock.get("http://localhost:3000/api/public/v1/authkey").respond(
        json={"code": 0, "data": "abc"},
    )
    client = WechatExporterClient("http://localhost:3000", "test-auth-key")

    assert client.check_auth() is True


def test_check_auth_failure(respx_mock) -> None:
    respx_mock.get("http://localhost:3000/api/public/v1/authkey").respond(
        json={"code": -1, "msg": "AuthKey not found"},
    )
    client = WechatExporterClient("http://localhost:3000", "test-auth-key")

    assert client.check_auth() is False


def test_list_articles_success(respx_mock) -> None:
    respx_mock.get("http://localhost:3000/api/public/v1/article").respond(
        json={
            "base_resp": {"ret": 0, "err_msg": "ok"},
            "articles": [
                {
                    "title": "测试文章",
                    "link": "https://mp.weixin.qq.com/s/test",
                    "update_time": 1710000000,
                },
            ],
        },
    )
    client = WechatExporterClient("http://localhost:3000/", "test-auth-key")

    articles = client.list_articles("fakeid123", begin=0, size=5)

    assert len(articles) == 1
    assert articles[0].title == "测试文章"
    assert articles[0].url == "https://mp.weixin.qq.com/s/test"
    assert isinstance(articles[0].published_at, datetime)


def test_list_articles_raises_exporter_error_for_api_error(respx_mock) -> None:
    respx_mock.get("http://localhost:3000/api/public/v1/article").respond(
        json={"base_resp": {"ret": -1, "err_msg": "认证信息无效"}},
    )
    client = WechatExporterClient("http://localhost:3000", "test-auth-key")

    with pytest.raises(WechatExporterError, match="认证信息无效"):
        client.list_articles("fakeid123")


def test_list_articles_requires_auth_key() -> None:
    client = WechatExporterClient("http://localhost:3000", auth_key="")

    with pytest.raises(WechatExporterAuthError):
        client.list_articles("fakeid123")


def test_download_text_success(respx_mock) -> None:
    respx_mock.get("http://localhost:3000/api/public/v1/download").respond(
        text="  这是一篇公众号文章正文  ",
    )
    client = WechatExporterClient("http://localhost:3000", "test-auth-key")

    assert client.download_text("https://mp.weixin.qq.com/s/test") == "这是一篇公众号文章正文"


def test_download_text_rejects_empty_url() -> None:
    client = WechatExporterClient("http://localhost:3000", "test-auth-key")

    with pytest.raises(ValueError):
        client.download_text("")


def test_http_client_ignores_environment_proxy(monkeypatch) -> None:
    captured_kwargs = {}

    class DummyClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr("market_info.wechat.exporter_client.httpx.Client", DummyClient)
    client = WechatExporterClient("http://localhost:3000", "test-auth-key")

    client._client()

    assert captured_kwargs["trust_env"] is False
