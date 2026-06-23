import json

import httpx
import pytest

from market_info.ai.embeddings import EmbeddingClient, EmbeddingError


def test_embedding_client_parses_openai_compatible_response(respx_mock) -> None:
    route = respx_mock.post("http://ai.example/embeddings").respond(
        json={"data": [{"embedding": [0.1, 0.2, 0.3]}]}
    )
    client = EmbeddingClient(
        "http://ai.example/",
        "test-key",
        "embedding-model",
        dimensions=1536,
    )

    embedding = client.embed("项目语义文本")

    assert embedding == [0.1, 0.2, 0.3]
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-key"
    assert route.calls.last.request.headers["Content-Type"] == "application/json"
    request_payload = json.loads(route.calls.last.request.content)
    assert request_payload == {
        "model": "embedding-model",
        "input": "项目语义文本",
        "dimensions": 1536,
    }


def test_embedding_client_returns_empty_list_for_empty_text(respx_mock) -> None:
    client = EmbeddingClient("http://ai.example", "test-key", "embedding-model")

    assert client.embed("   ") == []
    assert len(respx_mock.calls) == 0


def test_embedding_client_uses_default_project_dimension(respx_mock) -> None:
    route = respx_mock.post("http://ai.example/embeddings").respond(
        json={"data": [{"embedding": [0.1, 0.2, 0.3]}]}
    )
    client = EmbeddingClient("http://ai.example", "test-key", "embedding-model")

    client.embed("project semantic text")

    request_payload = json.loads(route.calls.last.request.content)
    assert request_payload["dimensions"] == 1536


def test_embedding_client_raises_business_error_for_http_500(respx_mock) -> None:
    respx_mock.post("http://ai.example/embeddings").respond(status_code=500)
    client = EmbeddingClient("http://ai.example", "test-key", "embedding-model")

    with pytest.raises(EmbeddingError):
        client.embed("项目语义文本")


def test_embedding_client_raises_business_error_for_invalid_response(respx_mock) -> None:
    respx_mock.post("http://ai.example/embeddings").respond(json={"data": []})
    client = EmbeddingClient("http://ai.example", "test-key", "embedding-model")

    with pytest.raises(EmbeddingError):
        client.embed("项目语义文本")


def test_embedding_client_uses_trust_env_false(monkeypatch) -> None:
    seen_kwargs = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def post(self, url, **kwargs):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"data": [{"embedding": [0.1, 0.2]}]},
            )

    monkeypatch.setattr("market_info.ai.embeddings.httpx.Client", FakeClient)
    client = EmbeddingClient("http://ai.example", "test-key", "embedding-model")

    assert client.embed("项目语义文本") == [0.1, 0.2]
    assert seen_kwargs["trust_env"] is False
