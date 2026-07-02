from fastapi.testclient import TestClient

from market_info.web.app import create_app


def test_create_app_serves_dashboard_shell() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Market Info Ops" in response.text
    assert "总览" in response.text
    assert "运行中心" in response.text
    assert "文章队列" in response.text
    assert "周报文件" in response.text


def test_static_css_is_mounted() -> None:
    client = TestClient(create_app())

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert "--bg-canvas" in response.text


def test_dashboard_shell_uses_design_system_classes() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "metric-grid" in response.text
    assert "glass-panel" in response.text
    assert "command-button" in response.text


def test_reports_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/reports")

    assert response.status_code == 200
    assert "周报文件" in response.text
