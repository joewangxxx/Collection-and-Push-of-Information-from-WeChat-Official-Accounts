from fastapi import FastAPI
from fastapi.testclient import TestClient

from market_info.config import Settings
from market_info.web.app import create_app
from market_info.web.security import install_access_guard, is_authorized, is_public_path


def test_public_path_detection() -> None:
    assert is_public_path("/static/styles.css") is True
    assert is_public_path("/favicon.ico") is True
    assert is_public_path("/") is False


def test_is_authorized_accepts_only_matching_bearer_token() -> None:
    assert is_authorized({"authorization": "Bearer secret"}, "secret") is True
    assert is_authorized({"authorization": "Bearer wrong"}, "secret") is False
    assert is_authorized({"authorization": "Basic secret"}, "secret") is False
    assert is_authorized({}, "secret") is False


def test_access_guard_allows_when_token_is_empty() -> None:
    app = FastAPI()
    install_access_guard(app, "")

    @app.get("/")
    def index():
        return {"ok": True}

    response = TestClient(app).get("/")

    assert response.status_code == 200


def test_create_app_requires_bearer_token_when_configured() -> None:
    app = create_app(Settings(web_access_token="secret"))
    client = TestClient(app)

    assert client.get("/").status_code == 401
    assert client.get("/", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert client.get("/static/styles.css").status_code == 200
