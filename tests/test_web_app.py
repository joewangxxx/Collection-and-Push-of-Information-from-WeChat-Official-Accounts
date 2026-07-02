from pathlib import Path

from fastapi.testclient import TestClient

from market_info.web.app import create_app


def test_create_app_serves_dashboard_shell() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Market Info Ops" in response.text
    assert "总览" in response.text
    assert "运行中心" in response.text
    assert "公众号账号" in response.text
    assert "推送记录" in response.text
    assert "文章队列" in response.text
    assert "周报文件" in response.text


def test_static_css_is_mounted() -> None:
    client = TestClient(create_app())

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert "--bg-canvas" in response.text


def test_busy_button_script_waits_for_form_submit() -> None:
    script = Path("src/market_info/web/static/app.js").read_text(encoding="utf-8")

    assert 'document.addEventListener("submit"' in script
    assert 'document.addEventListener("click", (event)' not in script
    assert "处理中" in script


def test_dashboard_shell_uses_design_system_classes() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "metric-grid" in response.text
    assert "glass-panel" in response.text
    assert "command-button" in response.text


def test_main_routes_render_smoke_suite() -> None:
    client = TestClient(create_app())

    for route in [
        "/jobs",
        "/accounts",
        "/delivery",
        "/articles",
        "/reports",
        "/reviews",
        "/projects",
        "/quality",
    ]:
        response = client.get(route)
        assert response.status_code == 200, route
        assert "Market Info Ops" in response.text


def test_accounts_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/accounts")

    assert response.status_code == 200
    assert "公众号账号" in response.text
    assert "同步配置" in response.text


def test_reports_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/reports")

    assert response.status_code == 200
    assert "周报文件" in response.text


def test_web_ui_text_does_not_contain_mojibake_markers() -> None:
    for path in Path("src/market_info/web").rglob("*"):
        if path.suffix not in {".py", ".html", ".js"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "\ufffd" not in text, f"{path} contains replacement characters"
        assert not any("\ue000" <= char <= "\uf8ff" for char in text), (
            f"{path} contains private-use characters"
        )


def test_rendered_pages_do_not_contain_mojibake_markers() -> None:
    client = TestClient(create_app())

    for route in [
        "/",
        "/jobs",
        "/accounts",
        "/delivery",
        "/articles",
        "/reports",
        "/reviews",
        "/projects",
        "/quality",
    ]:
        response = client.get(route)
        assert response.status_code == 200
        assert "\ufffd" not in response.text, f"{route} contains replacement characters"
        assert not any("\ue000" <= char <= "\uf8ff" for char in response.text), (
            f"{route} contains private-use characters"
        )
