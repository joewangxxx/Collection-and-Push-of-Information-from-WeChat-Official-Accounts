import json

import httpx
from pydantic import ValidationError

from market_info.ai.schemas import ExtractedProject


class ProjectExtractionError(Exception):
    """Raised when AI project extraction cannot produce validated JSON."""


class ProjectExtractor:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def extract(self, article_title: str, article_text: str) -> list[ExtractedProject]:
        if not article_text or not article_text.strip():
            return []

        payload = {
            "model": self.model,
            "messages": self._build_messages(article_title, article_text),
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                response_payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProjectExtractionError(
                f"AI extraction request failed with HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise ProjectExtractionError(f"AI extraction request failed: {exc}") from exc
        except ValueError as exc:
            raise ProjectExtractionError("AI extraction response was not valid JSON.") from exc

        content = self._extract_assistant_content(response_payload)
        raw_projects = self._parse_projects(content)
        try:
            return [ExtractedProject.model_validate(item) for item in raw_projects]
        except ValidationError as exc:
            raise ProjectExtractionError("AI extraction JSON did not match schema.") from exc

    def _build_messages(self, article_title: str, article_text: str) -> list[dict[str, str]]:
        status_values = "拟建、备案、环评公示、环评批复、招标、开工、建设中、投产、停缓建、未知"
        system_prompt = (
            "你是产业项目信息抽取助手。请只返回 JSON，不要返回 Markdown、解释或额外文本。"
        )
        user_prompt = f"""
请从下面的微信公众号文章正文中抽取市场项目信息，并只返回 JSON 数组。

要求：
1. 没有项目时返回 []。
2. 一篇文章包含多个项目时，数组中返回多条记录。
3. 投资额统一换算为“亿元”，字段名为 investment_amount_yi。
4. 无法判断的字段填 null，不要编造。
5. status 只能使用以下枚举：{status_values}。
6. status 无法判断时填“未知”。
7. confidence 必须是 0 到 1 之间的数字。
8. 不要输出公众号名称、文章标题、文章链接、发布日期等文章元数据。

每条记录字段：
project_name, project_info, province, city, detailed_address, company_name,
investment_amount_yi, industry, field, market, status, confidence

文章标题：
{article_title}

文章正文：
{article_text}
""".strip()

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _extract_assistant_content(self, response_payload: object) -> str:
        try:
            content = response_payload["choices"][0]["message"]["content"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProjectExtractionError("AI extraction response did not include assistant content.") from exc

        if not isinstance(content, str) or not content.strip():
            raise ProjectExtractionError("AI extraction response did not include assistant content.")
        return content

    def _parse_projects(self, content: str) -> list[object]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProjectExtractionError("AI extraction content was not valid JSON.") from exc

        if isinstance(parsed, list):
            return parsed

        if isinstance(parsed, dict) and isinstance(parsed.get("projects"), list):
            return parsed["projects"]

        raise ProjectExtractionError("AI extraction content must be a JSON array or {'projects': [...]}.")
