import httpx

from market_info.ai.schemas import ExtractedProject


class EmbeddingError(Exception):
    """Raised when an embedding response cannot be parsed or requested."""


def build_project_semantic_text(project: ExtractedProject) -> str:
    location_parts = [
        project.province,
        project.city,
        project.detailed_address,
    ]
    location = " ".join(part for part in location_parts if part)

    fields = [
        ("项目名称", project.project_name),
        ("企业名称", project.company_name),
        ("地点", location or None),
        (
            "投资额",
            f"{project.investment_amount_yi:g}亿元"
            if project.investment_amount_yi is not None
            else None,
        ),
        ("产业", project.industry),
        ("领域", project.field),
        ("市场", project.market),
        ("状态", project.status),
        ("项目信息", project.project_info),
    ]

    return "\n".join(f"{label}：{value}" for label, value in fields if value)


class EmbeddingClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int | None = 1536,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            return []

        payload = {
            "model": self.model,
            "input": text,
        }
        if self.dimensions:
            payload["dimensions"] = self.dimensions
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                response = client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                response_payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(
                f"Embedding request failed with HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise EmbeddingError(f"Embedding request failed: {exc}") from exc
        except ValueError as exc:
            raise EmbeddingError("Embedding response was not valid JSON.") from exc

        return self._parse_embedding(response_payload)

    def _parse_embedding(self, response_payload: object) -> list[float]:
        try:
            embedding = response_payload["data"][0]["embedding"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingError("Embedding response did not include data[0].embedding.") from exc

        if not isinstance(embedding, list) or not embedding:
            raise EmbeddingError("Embedding response did not include a non-empty vector.")

        try:
            return [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("Embedding vector must contain only numbers.") from exc
