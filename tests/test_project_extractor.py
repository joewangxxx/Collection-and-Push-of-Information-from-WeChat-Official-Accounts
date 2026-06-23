import json

import httpx
import pytest

from market_info.ai.extractor import ProjectExtractionError, ProjectExtractor


def test_empty_article_text_returns_empty_list_without_http(respx_mock) -> None:
    client = ProjectExtractor("http://ai.example", "test-key", "test-model")

    assert client.extract("测试标题", "   ") == []
    assert len(respx_mock.calls) == 0


def test_extract_parses_json_array_response(respx_mock) -> None:
    respx_mock.post("http://ai.example/chat/completions").respond(
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                {
                                    "project_name": "光伏电池项目",
                                    "company_name": "测试新能源有限公司",
                                    "investment_amount_yi": 10.5,
                                    "status": "备案",
                                    "confidence": 0.9,
                                }
                            ],
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
    )
    client = ProjectExtractor("http://ai.example/", "test-key", "test-model")

    projects = client.extract("测试标题", "这里有一个光伏项目。")

    assert len(projects) == 1
    assert projects[0].project_name == "光伏电池项目"
    assert projects[0].status == "备案"


def test_extract_parses_projects_object_response(respx_mock) -> None:
    respx_mock.post("http://ai.example/chat/completions").respond(
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "projects": [
                                    {
                                        "project_name": "组件扩产项目",
                                        "status": "投产",
                                        "confidence": 0.8,
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }
    )
    client = ProjectExtractor("http://ai.example", "test-key", "test-model")

    projects = client.extract("测试标题", "组件扩产项目已投产。")

    assert len(projects) == 1
    assert projects[0].project_name == "组件扩产项目"
    assert projects[0].status == "投产"


def test_extract_raises_for_invalid_json(respx_mock) -> None:
    respx_mock.post("http://ai.example/chat/completions").respond(
        json={"choices": [{"message": {"content": "not json"}}]}
    )
    client = ProjectExtractor("http://ai.example", "test-key", "test-model")

    with pytest.raises(ProjectExtractionError):
        client.extract("测试标题", "正文")


def test_extract_raises_for_http_500(respx_mock) -> None:
    respx_mock.post("http://ai.example/chat/completions").respond(status_code=500)
    client = ProjectExtractor("http://ai.example", "test-key", "test-model")

    with pytest.raises(ProjectExtractionError):
        client.extract("测试标题", "正文")


def test_http_client_uses_trust_env_false(monkeypatch) -> None:
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
                json={"choices": [{"message": {"content": "[]"}}]},
            )

    monkeypatch.setattr("market_info.ai.extractor.httpx.Client", FakeClient)
    client = ProjectExtractor("http://ai.example", "test-key", "test-model")

    assert client.extract("测试标题", "正文") == []
    assert seen_kwargs["trust_env"] is False
