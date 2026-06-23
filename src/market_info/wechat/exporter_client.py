from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx


USER_AGENT = "market-info-auto-collector/0.1"


@dataclass(frozen=True)
class WechatArticleSummary:
    title: str
    url: str
    published_at: datetime | None


class WechatExporterError(Exception):
    pass


class WechatExporterAuthError(WechatExporterError):
    pass


class WechatExporterClient:
    def __init__(self, base_url: str, auth_key: str = "", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_key = auth_key
        self.timeout = timeout

    def check_auth(self) -> bool:
        try:
            with self._client() as client:
                response = client.get("/api/public/v1/authkey")
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise WechatExporterError(f"Failed to check WeChat exporter auth: {exc}") from exc
        except ValueError:
            return False

        return payload.get("code") == 0 and bool(payload.get("data"))

    def list_articles(
        self,
        fakeid: str,
        begin: int = 0,
        size: int = 5,
    ) -> list[WechatArticleSummary]:
        if not self.auth_key:
            raise WechatExporterAuthError("WECHAT_EXPORTER_AUTH_KEY is required")
        if not fakeid:
            raise ValueError("fakeid is required")

        try:
            with self._client() as client:
                response = client.get(
                    "/api/public/v1/article",
                    params={"fakeid": fakeid, "begin": begin, "size": size},
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise WechatExporterError(f"Failed to list WeChat articles: {exc}") from exc
        except ValueError as exc:
            raise WechatExporterError("Failed to parse WeChat article list response") from exc

        base_resp = payload.get("base_resp") or {}
        if base_resp.get("ret") != 0:
            err_msg = base_resp.get("err_msg") or "WeChat exporter returned an error"
            raise WechatExporterError(err_msg)

        articles = payload.get("articles") or []
        return [summary for item in articles if (summary := self._parse_article(item))]

    def download_text(self, url: str) -> str:
        if not url:
            raise ValueError("url is required")

        try:
            with self._client() as client:
                response = client.get(
                    "/api/public/v1/download",
                    params={"url": url, "format": "text"},
                )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise WechatExporterError(f"Failed to download WeChat article text: {exc}") from exc

        return response.text.strip()

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=self.timeout,
            trust_env=False,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": USER_AGENT}
        if self.auth_key:
            headers["X-Auth-Key"] = self.auth_key
        return headers

    @staticmethod
    def _parse_article(item: dict[str, Any]) -> WechatArticleSummary | None:
        url = item.get("link") or item.get("url")
        if not url:
            return None

        return WechatArticleSummary(
            title=item.get("title") or "",
            url=url,
            published_at=_parse_unix_timestamp(item.get("update_time") or item.get("create_time")),
        )


def _parse_unix_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None

    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
