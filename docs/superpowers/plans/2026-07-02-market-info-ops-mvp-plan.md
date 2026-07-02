# Market Info Ops MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first six tasks of the local/intranet Market Info Ops console: a white Apple liquid-glass web shell, system dashboard, job runner, article queue, and report download/send surface.

**Architecture:** Add a small FastAPI web layer under `src/market_info/web/` and keep existing CLI/job/database modules as the source of business logic. Use Jinja2 templates, HTMX-style partial responses where useful, static CSS/JS for the liquid-glass UI, and a lightweight in-memory job runner for MVP task progress. Do not introduce React/Next.js in this phase.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, Typer, SQLAlchemy, existing `market_info.jobs.weekly_job` services, pytest, FastAPI TestClient, HTML/CSS/vanilla JavaScript.

## Global Constraints

- Default web host must be `127.0.0.1`; intranet exposure is explicit via CLI options.
- Do not expose `.env`, API keys, SMTP passwords, WeChat auth keys, article full text, embeddings, or database internals in the web UI.
- First MVP scope is Task 1-6 only: web shell, design system, dashboard, job center, article queue, report center.
- Do not add the dedupe review data model in this plan; review workflow belongs to a separate follow-up plan.
- Visual style must be white Apple liquid glass: light canvas, translucent panels, restrained status colors, high readability.
- No emoji as structural icons; use Lucide-compatible inline SVG or text labels.
- Interactive elements must have visible focus states, loading states, and minimum 44px hit targets.
- Prefer server-rendered pages and small focused services over a heavy SPA.
- Reuse existing `Settings`, `get_session`, `check_wechat_auth`, `get_processing_status_summary`, `run_weekly`, `process_pending_backlog`, `retry_failed_articles`, and `send_report`.
- Use `python -m pytest ...` for test commands on Windows.
- The implementation must preserve all existing tests: `python -m pytest -q` remains green.

---

## File Structure

Create and modify the following files across Task 1-6.

```text
pyproject.toml
src/market_info/cli.py
src/market_info/web/__init__.py
src/market_info/web/app.py
src/market_info/web/templating.py
src/market_info/web/routes/__init__.py
src/market_info/web/routes/dashboard.py
src/market_info/web/routes/jobs.py
src/market_info/web/routes/articles.py
src/market_info/web/routes/reports.py
src/market_info/web/services/__init__.py
src/market_info/web/services/dashboard_service.py
src/market_info/web/services/job_runner.py
src/market_info/web/services/article_service.py
src/market_info/web/services/report_service.py
src/market_info/web/templates/base.html
src/market_info/web/templates/components.html
src/market_info/web/templates/dashboard.html
src/market_info/web/templates/jobs.html
src/market_info/web/templates/articles.html
src/market_info/web/templates/reports.html
src/market_info/web/static/styles.css
src/market_info/web/static/app.js
tests/test_web_app.py
tests/test_web_dashboard_service.py
tests/test_web_job_runner.py
tests/test_web_article_service.py
tests/test_web_report_service.py
docs/web-design-system.md
```

Responsibilities:

- `web/app.py`: FastAPI app factory, static wiring, router registration.
- `web/templating.py`: shared `Jinja2Templates` object and static/template paths, kept separate to avoid circular imports.
- `web/routes/*.py`: HTTP routes only; no direct database query logic except calling service functions.
- `web/services/*.py`: focused data and workflow adapters around existing project modules.
- `templates/base.html`: app shell with liquid-glass navigation and shared layout.
- `templates/components.html`: reusable Jinja macros for panels, metric tiles, status pills, command buttons.
- `static/styles.css`: design tokens, glass material, layout, states, responsive behavior.
- `static/app.js`: tiny progressive enhancement helpers for buttons, confirmations, and job polling.
- `tests/test_web_*.py`: service and route smoke tests that avoid requiring real WeChat, AI, SMTP, or PostgreSQL unless specifically mocked.

---

## Task 1: FastAPI Web Shell and CLI Entry

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/market_info/cli.py`
- Create: `src/market_info/web/__init__.py`
- Create: `src/market_info/web/app.py`
- Create: `src/market_info/web/templating.py`
- Create: `src/market_info/web/routes/__init__.py`
- Create: `src/market_info/web/routes/dashboard.py`
- Create: `src/market_info/web/templates/base.html`
- Create: `src/market_info/web/templates/dashboard.html`
- Create: `src/market_info/web/static/styles.css`
- Create: `src/market_info/web/static/app.js`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: existing Typer app in `market_info.cli.app`.
- Produces: `market_info.web.app.create_app() -> fastapi.FastAPI`.
- Produces: `market-info web --host 127.0.0.1 --port 8080 --reload/--no-reload`.
- Produces: `GET /` route returning HTML with title `Market Info Ops`.

- [ ] **Step 1: Write failing route and app factory tests**

Create `tests/test_web_app.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_app.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'market_info.web'
```

- [ ] **Step 3: Add web dependencies**

Modify `pyproject.toml` dependency list to include:

```toml
  "fastapi>=0.115",
  "jinja2>=3.1",
  "python-multipart>=0.0.9",
  "uvicorn[standard]>=0.30",
```

If the environment is not installed in editable mode after changing dependencies, run:

```powershell
python -m pip install -e ".[dev]"
```

Expected:

```text
Successfully installed market-info-auto-collector
```

- [ ] **Step 4: Create the web package and app factory**

Create `src/market_info/web/__init__.py`:

```python
"""Local/intranet web console for market info operations."""
```

Create `src/market_info/web/routes/__init__.py`:

```python
"""Route modules for the Market Info Ops web console."""
```

Create `src/market_info/web/templating.py`:

```python
from pathlib import Path

from fastapi.templating import Jinja2Templates


WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
```

Create `src/market_info/web/app.py`:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from market_info.web.routes import dashboard
from market_info.web.templating import STATIC_DIR


def create_app() -> FastAPI:
    app = FastAPI(title="Market Info Ops")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(dashboard.router)
    return app
```

- [ ] **Step 5: Add the dashboard route**

Create `src/market_info/web/routes/dashboard.py`:

```python
from fastapi import APIRouter, Request

from market_info.web.templating import templates


router = APIRouter()


@router.get("/")
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_nav": "dashboard",
            "page_title": "总览",
        },
    )
```

- [ ] **Step 6: Add base and dashboard templates**

Create `src/market_info/web/templates/base.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ page_title }} · Market Info Ops</title>
    <link rel="stylesheet" href="{{ url_for('static', path='styles.css') }}">
  </head>
  <body>
    <div class="app-shell">
      <aside class="sidebar glass-panel" aria-label="主导航">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">MI</span>
          <div>
            <strong>Market Info Ops</strong>
            <span>本地运营台</span>
          </div>
        </div>
        <nav class="nav-list">
          <a class="nav-link {% if active_nav == 'dashboard' %}is-active{% endif %}" href="/">总览</a>
          <a class="nav-link" href="/jobs">运行中心</a>
          <a class="nav-link" href="/articles">文章队列</a>
          <a class="nav-link" href="/reports">周报文件</a>
        </nav>
      </aside>
      <main class="main-surface">
        <header class="topbar glass-panel">
          <div>
            <p class="eyebrow">Market intelligence automation</p>
            <h1>{{ page_title }}</h1>
          </div>
          <a class="ghost-button" href="/jobs">运行任务</a>
        </header>
        <section class="content-region">
          {% block content %}{% endblock %}
        </section>
      </main>
    </div>
    <script src="{{ url_for('static', path='app.js') }}"></script>
  </body>
</html>
```

Create `src/market_info/web/templates/dashboard.html`:

```html
{% extends "base.html" %}

{% block content %}
  <section class="hero-panel glass-panel">
    <div>
      <p class="eyebrow">System overview</p>
      <h2>市场信息自动抓取运营台</h2>
      <p class="hero-copy">查看系统状态、运行周报任务、处理失败文章，并下载最近生成的 Excel 周报。</p>
    </div>
    <div class="hero-status">
      <span class="status-dot status-ok"></span>
      <span>Web console ready</span>
    </div>
  </section>
{% endblock %}
```

- [ ] **Step 7: Add the initial liquid-glass CSS and JS placeholder**

Create `src/market_info/web/static/styles.css`:

```css
:root {
  --bg-canvas: #f7f8fa;
  --surface-glass: rgba(255, 255, 255, 0.72);
  --surface-solid: #ffffff;
  --ink: #111827;
  --muted: #6b7280;
  --hairline: rgba(17, 24, 39, 0.10);
  --blue: #0a84ff;
  --green: #34c759;
  --amber: #ff9f0a;
  --red: #ff3b30;
  --purple: #af52de;
  --radius-lg: 24px;
  --radius-md: 16px;
  --shadow-glass: 0 20px 60px rgba(15, 23, 42, 0.08);
  color-scheme: light;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100dvh;
  background:
    linear-gradient(135deg, rgba(10, 132, 255, 0.08), transparent 32%),
    linear-gradient(225deg, rgba(52, 199, 89, 0.07), transparent 36%),
    var(--bg-canvas);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

a {
  color: inherit;
  text-decoration: none;
}

a:focus-visible,
button:focus-visible {
  outline: 3px solid rgba(10, 132, 255, 0.36);
  outline-offset: 3px;
}

.app-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 24px;
  min-height: 100dvh;
  padding: 24px;
}

.glass-panel {
  background: var(--surface-glass);
  border: 1px solid rgba(255, 255, 255, 0.68);
  box-shadow: var(--shadow-glass), inset 0 1px 0 rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(24px) saturate(1.35);
}

.sidebar {
  position: sticky;
  top: 24px;
  height: calc(100dvh - 48px);
  border-radius: var(--radius-lg);
  padding: 20px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(10, 132, 255, 0.18), rgba(255, 255, 255, 0.72));
  color: var(--blue);
  font-weight: 700;
}

.brand span {
  display: block;
  color: var(--muted);
  font-size: 13px;
  margin-top: 2px;
}

.nav-list {
  display: grid;
  gap: 8px;
}

.nav-link {
  min-height: 44px;
  display: flex;
  align-items: center;
  border-radius: 14px;
  padding: 0 14px;
  color: #374151;
  transition: background 180ms ease, transform 180ms ease;
}

.nav-link:hover,
.nav-link.is-active {
  background: rgba(255, 255, 255, 0.78);
  transform: translateY(-1px);
}

.main-surface {
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 20px;
  min-width: 0;
}

.topbar,
.hero-panel {
  border-radius: var(--radius-lg);
  padding: 24px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 0;
  font-size: clamp(28px, 3vw, 40px);
  line-height: 1.1;
}

.hero-panel {
  display: flex;
  justify-content: space-between;
  gap: 24px;
}

.hero-copy {
  max-width: 720px;
  color: var(--muted);
  line-height: 1.7;
}

.hero-status,
.ghost-button {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 0 16px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid var(--hairline);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.status-ok {
  background: var(--green);
}

@media (max-width: 860px) {
  .app-shell {
    grid-template-columns: 1fr;
    padding: 14px;
  }

  .sidebar {
    position: static;
    height: auto;
  }

  .nav-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .topbar,
  .hero-panel {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
}
```

Create `src/market_info/web/static/app.js`:

```javascript
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-disable-on-click]");
  if (!button) {
    return;
  }
  button.setAttribute("aria-busy", "true");
  button.setAttribute("disabled", "disabled");
});
```

- [ ] **Step 8: Add the CLI web command**

Modify `src/market_info/cli.py` imports:

```python
from pathlib import Path

import typer
```

Add this command near the other top-level commands:

```python
@app.command("web")
def web_command(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8080, "--port", min=1, max=65535),
    reload: bool = typer.Option(False, "--reload/--no-reload"),
) -> None:
    import uvicorn

    uvicorn.run(
        "market_info.web.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )
```

- [ ] **Step 9: Run task tests**

Run:

```powershell
python -m pytest tests/test_web_app.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 10: Run smoke acceptance**

Run:

```powershell
market-info web --host 127.0.0.1 --port 8080
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8080
```

Open:

```text
http://127.0.0.1:8080
```

Expected:

```text
The page renders the Market Info Ops shell with white liquid-glass navigation.
```

**Prompt for Task 1 execution:**

```text
Implement Task 1 from docs/superpowers/plans/2026-07-02-market-info-ops-mvp-plan.md. Use TDD exactly as written. Add FastAPI, Jinja2, python-multipart, and Uvicorn dependencies, create the web app factory, add the base dashboard shell, and add `market-info web`. Do not implement dashboard data, job running, articles, or reports yet. Run `python -m pytest tests/test_web_app.py -v` and then `python -m pytest -q`. Report changed files and test results.
```

---

## Task 2: Liquid Glass Design System and Reusable Template Macros

**Files:**
- Create: `src/market_info/web/templates/components.html`
- Modify: `src/market_info/web/templates/base.html`
- Modify: `src/market_info/web/templates/dashboard.html`
- Modify: `src/market_info/web/static/styles.css`
- Modify: `src/market_info/web/static/app.js`
- Create: `docs/web-design-system.md`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `create_app() -> FastAPI` from Task 1.
- Produces: Jinja macros `glass_panel`, `metric_tile`, `status_pill`, `command_button`.
- Produces: design tokens documented in `docs/web-design-system.md`.
- Produces: accessible CSS classes for `glass-panel`, `metric-grid`, `metric-tile`, `status-pill`, `command-button`, `data-table`, `side-sheet`, `toast`, and `skeleton`.

- [ ] **Step 1: Extend route tests for component classes**

Modify `tests/test_web_app.py`:

```python
def test_dashboard_shell_uses_design_system_classes() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "metric-grid" in response.text
    assert "glass-panel" in response.text
    assert "command-button" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_app.py::test_dashboard_shell_uses_design_system_classes -v
```

Expected:

```text
AssertionError: assert 'metric-grid' in response.text
```

- [ ] **Step 3: Add reusable Jinja macros**

Create `src/market_info/web/templates/components.html`:

```html
{% macro glass_panel(title, subtitle=None, class_name="") %}
  <section class="glass-panel panel {{ class_name }}">
    <header class="panel-header">
      <div>
        <h2>{{ title }}</h2>
        {% if subtitle %}
          <p>{{ subtitle }}</p>
        {% endif %}
      </div>
    </header>
    <div class="panel-body">
      {{ caller() }}
    </div>
  </section>
{% endmacro %}

{% macro metric_tile(label, value, detail="", tone="neutral") %}
  <article class="metric-tile metric-{{ tone }}">
    <span class="metric-label">{{ label }}</span>
    <strong class="metric-value">{{ value }}</strong>
    {% if detail %}
      <span class="metric-detail">{{ detail }}</span>
    {% endif %}
  </article>
{% endmacro %}

{% macro status_pill(label, tone="neutral") %}
  <span class="status-pill status-{{ tone }}">
    <span class="status-dot" aria-hidden="true"></span>
    {{ label }}
  </span>
{% endmacro %}

{% macro command_button(label, href=None, tone="primary", busy_label="处理中") %}
  {% if href %}
    <a class="command-button command-{{ tone }}" href="{{ href }}">{{ label }}</a>
  {% else %}
    <button class="command-button command-{{ tone }}" type="submit" data-disable-on-click data-busy-label="{{ busy_label }}">
      {{ label }}
    </button>
  {% endif %}
{% endmacro %}
```

- [ ] **Step 4: Use macros on the dashboard placeholder**

Modify `src/market_info/web/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  <section class="hero-panel glass-panel">
    <div>
      <p class="eyebrow">System overview</p>
      <h2>市场信息自动抓取运营台</h2>
      <p class="hero-copy">查看系统状态、运行周报任务、处理失败文章，并下载最近生成的 Excel 周报。</p>
    </div>
    <div class="hero-actions">
      {{ ui.status_pill("Web console ready", "ok") }}
      {{ ui.command_button("运行任务", "/jobs", "primary") }}
    </div>
  </section>

  <section class="metric-grid" aria-label="核心指标">
    {{ ui.metric_tile("待处理文章", "0", "pending", "neutral") }}
    {{ ui.metric_tile("可重试失败", "0", "failed_retryable", "amber") }}
    {{ ui.metric_tile("项目总数", "0", "projects", "blue") }}
    {{ ui.metric_tile("最近周报", "未生成", "exports", "neutral") }}
  </section>

  {% call ui.glass_panel("液态流程", "登录检查、抓取、AI 抽取、去重、Excel、邮件") %}
    <div class="pipeline-lens">
      <span>登录检查</span>
      <span>文章抓取</span>
      <span>AI 抽取</span>
      <span>去重入库</span>
      <span>Excel</span>
      <span>邮件</span>
    </div>
  {% endcall %}
{% endblock %}
```

- [ ] **Step 5: Extend CSS tokens and components**

Append to `src/market_info/web/static/styles.css`:

```css
.content-region {
  display: grid;
  gap: 20px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.metric-tile {
  min-height: 132px;
  border-radius: var(--radius-md);
  padding: 18px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(17, 24, 39, 0.08);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
  transition: transform 180ms ease, box-shadow 180ms ease;
}

.metric-tile:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.10);
}

.metric-label,
.metric-detail {
  display: block;
  color: var(--muted);
  font-size: 13px;
}

.metric-value {
  display: block;
  margin: 12px 0 8px;
  font-size: 34px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.metric-blue {
  border-color: rgba(10, 132, 255, 0.22);
}

.metric-amber {
  border-color: rgba(255, 159, 10, 0.28);
}

.panel {
  border-radius: var(--radius-lg);
  padding: 22px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-header h2 {
  margin-bottom: 6px;
  font-size: 20px;
}

.panel-header p {
  margin-bottom: 0;
  color: var(--muted);
}

.status-pill {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 0 12px;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, 0.74);
  color: #374151;
  font-size: 13px;
  font-weight: 650;
}

.status-pill .status-dot {
  width: 8px;
  height: 8px;
}

.status-ok .status-dot {
  background: var(--green);
}

.status-amber .status-dot {
  background: var(--amber);
}

.status-danger .status-dot {
  background: var(--red);
}

.status-neutral .status-dot {
  background: #9ca3af;
}

.command-button {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  padding: 0 18px;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  transition: transform 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
}

.command-button:active {
  transform: scale(0.98);
}

.command-primary {
  background: linear-gradient(135deg, var(--blue), #5ac8fa);
  color: #ffffff;
  box-shadow: 0 12px 24px rgba(10, 132, 255, 0.22);
}

.command-secondary {
  background: rgba(255, 255, 255, 0.78);
  color: var(--ink);
  border: 1px solid var(--hairline);
}

.pipeline-lens {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.pipeline-lens span {
  min-height: 48px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(10, 132, 255, 0.12);
  color: #374151;
  font-size: 13px;
  text-align: center;
}

.data-table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

.data-table th,
.data-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--hairline);
  text-align: left;
  vertical-align: top;
}

.data-table th {
  color: var(--muted);
  font-size: 12px;
  font-weight: 750;
}

.skeleton {
  min-height: 16px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(229, 231, 235, 0.72), rgba(255, 255, 255, 0.8), rgba(229, 231, 235, 0.72));
  background-size: 220% 100%;
  animation: shimmer 1.2s ease-in-out infinite;
}

@keyframes shimmer {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}

@media (max-width: 1120px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pipeline-lens {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .metric-grid,
  .pipeline-lens {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Improve click busy labels**

Replace `src/market_info/web/static/app.js` with:

```javascript
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-disable-on-click]");
  if (!button) {
    return;
  }
  const busyLabel = button.getAttribute("data-busy-label") || "处理中";
  button.dataset.originalLabel = button.textContent.trim();
  button.textContent = busyLabel;
  button.setAttribute("aria-busy", "true");
  button.setAttribute("disabled", "disabled");
});
```

- [ ] **Step 7: Add design system documentation**

Create `docs/web-design-system.md`:

```markdown
# Market Info Ops Web Design System

## Direction

Market Info Ops uses a white Apple liquid-glass interface for a local/intranet operations console. The UI must feel calm, precise, tactile, and data-focused.

## Tokens

- Canvas: `#F7F8FA`
- Glass surface: `rgba(255,255,255,0.72)`
- Solid surface: `#FFFFFF`
- Text: `#111827`
- Muted text: `#6B7280`
- Hairline: `rgba(17,24,39,0.10)`
- Blue action: `#0A84FF`
- Green success: `#34C759`
- Amber warning: `#FF9F0A`
- Red danger: `#FF3B30`
- Purple accent: `#AF52DE`

## Rules

- Use glass for shell, topbar, panels, sheets, and high-level tiles.
- Use solid white for dense tables when readability matters.
- Use status colors only for state, never as page decoration.
- Keep focus rings visible.
- Keep all interactive targets at least 44px tall.
- Use text labels with status color so color is not the only signal.
- Respect reduced motion.
- Do not use emoji as structural icons.
```

- [ ] **Step 8: Run task tests**

Run:

```powershell
python -m pytest tests/test_web_app.py -v
```

Expected:

```text
3 passed
```

**Prompt for Task 2 execution:**

```text
Implement Task 2 from docs/superpowers/plans/2026-07-02-market-info-ops-mvp-plan.md. Add the reusable Jinja component macros and liquid-glass CSS system. Keep the UI white, readable, accessible, and responsive. Do not add real dashboard data or new routes beyond what Task 1 created. Run `python -m pytest tests/test_web_app.py -v` and `python -m pytest -q`. Report changed files and test results.
```

---

## Task 3: Dashboard Service and Real Overview Page

**Files:**
- Create: `src/market_info/web/services/__init__.py`
- Create: `src/market_info/web/services/dashboard_service.py`
- Modify: `src/market_info/web/routes/dashboard.py`
- Modify: `src/market_info/web/templates/dashboard.html`
- Test: `tests/test_web_dashboard_service.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `Settings`, `get_session`, `check_wechat_auth`, `get_processing_status_summary`, `Project`, `ProjectEvent`, `ProjectRecord`.
- Produces: `DashboardOverview` dataclass.
- Produces: `get_dashboard_overview(settings: Settings | None = None) -> DashboardOverview`.
- Produces: `find_latest_report(export_dir: Path) -> ReportFileSummary | None`.
- Produces: dashboard route context key `overview`.

- [ ] **Step 1: Write dashboard service tests**

Create `tests/test_web_dashboard_service.py`:

```python
from pathlib import Path
from types import SimpleNamespace

from market_info.web.services.dashboard_service import find_latest_report, mask_error


def test_find_latest_report_returns_newest_xlsx(tmp_path: Path) -> None:
    older = tmp_path / "market_info_weekly_20260624_102824.xlsx"
    newer = tmp_path / "market_info_weekly_20260629_103132.xlsx"
    ignored = tmp_path / "notes.txt"
    older.write_bytes(b"older")
    newer.write_bytes(b"newer")
    ignored.write_text("ignore", encoding="utf-8")

    report = find_latest_report(tmp_path)

    assert report is not None
    assert report.name == newer.name
    assert report.path == newer
    assert report.size_bytes == len(b"newer")


def test_find_latest_report_returns_none_when_dir_missing(tmp_path: Path) -> None:
    report = find_latest_report(tmp_path / "missing")

    assert report is None


def test_mask_error_is_short_and_single_line() -> None:
    error = mask_error(RuntimeError("line one\nline two with a very long message" * 40))

    assert "\n" not in error
    assert len(error) <= 180
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_dashboard_service.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'market_info.web.services'
```

- [ ] **Step 3: Implement dashboard service dataclasses and helpers**

Create `src/market_info/web/services/__init__.py`:

```python
"""Service adapters for the Market Info Ops web console."""
```

Create `src/market_info/web/services/dashboard_service.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from market_info.config import Settings
from market_info.db.models import Project, ProjectEvent, ProjectRecord
from market_info.db.session import get_session
from market_info.jobs.weekly_job import (
    ArticleProcessingStatusSummary,
    check_wechat_auth,
    get_processing_status_summary,
)


@dataclass(frozen=True)
class ReportFileSummary:
    name: str
    path: Path
    size_bytes: int
    modified_at: float


@dataclass(frozen=True)
class ServiceHealth:
    ok: bool
    label: str
    detail: str = ""


@dataclass(frozen=True)
class DashboardOverview:
    wechat: ServiceHealth
    database: ServiceHealth
    article_status: ArticleProcessingStatusSummary
    project_total: int
    review_records: int
    status_events: int
    latest_report: ReportFileSummary | None


def mask_error(exc: Exception, max_length: int = 180) -> str:
    message = " ".join(str(exc).split())
    return message[:max_length]


def find_latest_report(export_dir: Path) -> ReportFileSummary | None:
    if not export_dir.exists() or not export_dir.is_dir():
        return None
    reports = [
        path
        for path in export_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".xlsx"
    ]
    if not reports:
        return None
    latest = max(reports, key=lambda path: path.stat().st_mtime)
    stat = latest.stat()
    return ReportFileSummary(
        name=latest.name,
        path=latest,
        size_bytes=stat.st_size,
        modified_at=stat.st_mtime,
    )


def get_dashboard_overview(settings: Settings | None = None) -> DashboardOverview:
    settings = settings or Settings()
    wechat = _check_wechat(settings)
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
            article_status = get_processing_status_summary(session)
            project_total = session.query(Project).count()
            review_records = (
                session.query(ProjectRecord)
                .filter(ProjectRecord.dedupe_decision == "review")
                .count()
            )
            status_events = session.query(ProjectEvent).count()
        database = ServiceHealth(True, "数据库正常")
    except Exception as exc:
        article_status = ArticleProcessingStatusSummary()
        project_total = 0
        review_records = 0
        status_events = 0
        database = ServiceHealth(False, "数据库异常", mask_error(exc))

    return DashboardOverview(
        wechat=wechat,
        database=database,
        article_status=article_status,
        project_total=project_total,
        review_records=review_records,
        status_events=status_events,
        latest_report=find_latest_report(Path(settings.export_dir)),
    )


def _check_wechat(settings: Settings) -> ServiceHealth:
    try:
        is_valid = check_wechat_auth(settings=settings)
    except Exception as exc:
        return ServiceHealth(False, "登录检查失败", mask_error(exc))
    if is_valid:
        return ServiceHealth(True, "登录有效")
    return ServiceHealth(False, "登录失效", "请打开 wechat-exporter 重新扫码并更新 auth key")
```

- [ ] **Step 4: Wire overview into the dashboard route**

Modify `src/market_info/web/routes/dashboard.py`:

```python
from fastapi import APIRouter, Request

from market_info.web.templating import templates
from market_info.web.services.dashboard_service import get_dashboard_overview


router = APIRouter()


@router.get("/")
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_nav": "dashboard",
            "page_title": "总览",
            "overview": get_dashboard_overview(),
        },
    )
```

- [ ] **Step 5: Render real overview data**

Modify `src/market_info/web/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  <section class="hero-panel glass-panel">
    <div>
      <p class="eyebrow">System overview</p>
      <h2>市场信息自动抓取运营台</h2>
      <p class="hero-copy">查看系统状态、运行周报任务、处理失败文章，并下载最近生成的 Excel 周报。</p>
    </div>
    <div class="hero-actions">
      {{ ui.status_pill(overview.wechat.label, "ok" if overview.wechat.ok else "danger") }}
      {{ ui.status_pill(overview.database.label, "ok" if overview.database.ok else "danger") }}
      {{ ui.command_button("运行任务", "/jobs", "primary") }}
    </div>
  </section>

  {% if overview.wechat.detail or overview.database.detail %}
    <section class="glass-panel alert-panel" aria-label="系统提示">
      {% if overview.wechat.detail %}
        <p><strong>微信登录：</strong>{{ overview.wechat.detail }}</p>
      {% endif %}
      {% if overview.database.detail %}
        <p><strong>数据库：</strong>{{ overview.database.detail }}</p>
      {% endif %}
    </section>
  {% endif %}

  <section class="metric-grid" aria-label="核心指标">
    {{ ui.metric_tile("待处理文章", overview.article_status.pending, "pending", "neutral") }}
    {{ ui.metric_tile("可重试失败", overview.article_status.failed_retryable, "failed_retryable", "amber") }}
    {{ ui.metric_tile("项目总数", overview.project_total, "projects", "blue") }}
    {{ ui.metric_tile("疑似重复", overview.review_records, "review", "amber") }}
  </section>

  {% call ui.glass_panel("液态流程", "登录检查、抓取、AI 抽取、去重、Excel、邮件") %}
    <div class="pipeline-lens">
      <span>登录检查</span>
      <span>文章抓取</span>
      <span>AI 抽取</span>
      <span>去重入库</span>
      <span>Excel</span>
      <span>邮件</span>
    </div>
  {% endcall %}

  {% call ui.glass_panel("最近周报", "Excel 文件来自 EXPORT_DIR，仅显示 .xlsx 文件") %}
    {% if overview.latest_report %}
      <div class="report-highlight">
        <strong>{{ overview.latest_report.name }}</strong>
        <span>{{ overview.latest_report.size_bytes }} bytes</span>
        <a class="command-button command-secondary" href="/reports/{{ overview.latest_report.name }}/download">下载</a>
      </div>
    {% else %}
      <p class="empty-state">还没有可下载的 Excel 周报。运行一次周报后会显示在这里。</p>
    {% endif %}
  {% endcall %}
{% endblock %}
```

- [ ] **Step 6: Add CSS for dashboard alerts and report highlight**

Append to `src/market_info/web/static/styles.css`:

```css
.alert-panel {
  border-radius: var(--radius-md);
  padding: 16px 18px;
  border-color: rgba(255, 59, 48, 0.18);
}

.alert-panel p {
  margin-bottom: 8px;
  color: #7f1d1d;
}

.alert-panel p:last-child {
  margin-bottom: 0;
}

.report-highlight {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.report-highlight span,
.empty-state {
  color: var(--muted);
}
```

- [ ] **Step 7: Run task tests**

Run:

```powershell
python -m pytest tests/test_web_dashboard_service.py tests/test_web_app.py -v
```

Expected:

```text
All selected tests pass
```

**Prompt for Task 3 execution:**

```text
Implement Task 3 from docs/superpowers/plans/2026-07-02-market-info-ops-mvp-plan.md. Add the dashboard service dataclasses and helper functions, render real overview data on `/`, and keep database/WeChat failures visible but non-crashing. Do not implement jobs, article queue, or report routes beyond the dashboard's latest report link. Run `python -m pytest tests/test_web_dashboard_service.py tests/test_web_app.py -v` and `python -m pytest -q`. Report changed files and test results.
```

---

## Task 4: Job Center and In-Memory Job Runner

**Files:**
- Create: `src/market_info/web/services/job_runner.py`
- Create: `src/market_info/web/routes/jobs.py`
- Create: `src/market_info/web/templates/jobs.html`
- Modify: `src/market_info/web/app.py`
- Modify: `src/market_info/web/templates/base.html`
- Test: `tests/test_web_job_runner.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `check_wechat_auth`, `run_weekly`, `process_pending_backlog`, `retry_failed_articles`, `send_report`.
- Produces: `JobStatus` dataclass.
- Produces: `InMemoryJobRunner.start_job(kind: str, target: Callable[..., object], kwargs: dict[str, object] | None = None) -> JobStatus`.
- Produces: `InMemoryJobRunner.get_job(job_id: str) -> JobStatus | None`.
- Produces: `InMemoryJobRunner.list_jobs() -> list[JobStatus]`.
- Produces routes `GET /jobs`, `POST /jobs/check-auth`, `POST /jobs/run-weekly`, `POST /jobs/process-pending`, `POST /jobs/retry-failed`, `POST /jobs/send-report`, `GET /jobs/{job_id}`.

- [ ] **Step 1: Write job runner tests**

Create `tests/test_web_job_runner.py`:

```python
from market_info.web.services.job_runner import InMemoryJobRunner


def test_runner_records_successful_job() -> None:
    runner = InMemoryJobRunner(run_inline=True)

    job = runner.start_job("check_auth", lambda: "ok")

    stored = runner.get_job(job.id)
    assert stored is not None
    assert stored.status == "succeeded"
    assert stored.result == "ok"
    assert stored.error_message is None


def test_runner_records_failed_job() -> None:
    runner = InMemoryJobRunner(run_inline=True)

    def fail():
        raise RuntimeError("network failed")

    job = runner.start_job("check_auth", fail)

    stored = runner.get_job(job.id)
    assert stored is not None
    assert stored.status == "failed"
    assert stored.error_message == "network failed"


def test_runner_rejects_second_running_same_kind() -> None:
    runner = InMemoryJobRunner(run_inline=False)

    first = runner.start_job("run_weekly", lambda: "ok")
    second = runner.start_job("run_weekly", lambda: "ok")

    assert first.status == "running"
    assert second.status == "rejected"
    assert "already running" in (second.error_message or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_job_runner.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'market_info.web.services.job_runner'
```

- [ ] **Step 3: Implement the job runner**

Create `src/market_info/web/services/job_runner.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock, Thread
from typing import Any
from uuid import uuid4


JobState = str


@dataclass
class JobStatus:
    id: str
    kind: str
    status: JobState
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: Any = None
    error_message: str | None = None
    logs: list[str] = field(default_factory=list)


class InMemoryJobRunner:
    def __init__(self, run_inline: bool = False) -> None:
        self.run_inline = run_inline
        self._jobs: dict[str, JobStatus] = {}
        self._lock = Lock()

    def start_job(
        self,
        kind: str,
        target: Callable[..., object],
        kwargs: dict[str, object] | None = None,
    ) -> JobStatus:
        kwargs = kwargs or {}
        with self._lock:
            if self._has_running_kind(kind):
                rejected = JobStatus(
                    id=str(uuid4()),
                    kind=kind,
                    status="rejected",
                    created_at=datetime.now(),
                    error_message=f"{kind} is already running",
                )
                self._jobs[rejected.id] = rejected
                return rejected
            job = JobStatus(
                id=str(uuid4()),
                kind=kind,
                status="running",
                created_at=datetime.now(),
                started_at=datetime.now(),
            )
            self._jobs[job.id] = job

        if self.run_inline:
            self._run(job.id, target, kwargs)
        else:
            Thread(target=self._run, args=(job.id, target, kwargs), daemon=True).start()
        return job

    def get_job(self, job_id: str) -> JobStatus | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobStatus]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.logs.append(message)

    def _run(self, job_id: str, target: Callable[..., object], kwargs: dict[str, object]) -> None:
        try:
            result = target(**kwargs)
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job.status = "failed"
                job.error_message = " ".join(str(exc).split())
                job.finished_at = datetime.now()
            return
        with self._lock:
            job = self._jobs[job_id]
            job.status = "succeeded"
            job.result = result
            job.finished_at = datetime.now()

    def _has_running_kind(self, kind: str) -> bool:
        return any(job.kind == kind and job.status == "running" for job in self._jobs.values())


job_runner = InMemoryJobRunner()
```

- [ ] **Step 4: Add job routes**

Create `src/market_info/web/routes/jobs.py`:

```python
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from market_info.jobs.weekly_job import (
    check_wechat_auth,
    process_pending_backlog,
    retry_failed_articles,
    run_weekly,
    send_report,
)
from market_info.web.templating import templates
from market_info.web.services.job_runner import job_runner


router = APIRouter(prefix="/jobs")


@router.get("")
def jobs_page(request: Request):
    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "active_nav": "jobs",
            "page_title": "运行中心",
            "jobs": job_runner.list_jobs(),
        },
    )


@router.post("/check-auth")
def start_check_auth():
    job_runner.start_job("check_auth", check_wechat_auth)
    return RedirectResponse("/jobs", status_code=303)


@router.post("/run-weekly")
def start_run_weekly(limit: int = Form(10)):
    job_runner.start_job("run_weekly", run_weekly, {"limit": limit})
    return RedirectResponse("/jobs", status_code=303)


@router.post("/process-pending")
def start_process_pending(limit: int = Form(20)):
    job_runner.start_job("process_pending", process_pending_backlog, {"limit": limit})
    return RedirectResponse("/jobs", status_code=303)


@router.post("/retry-failed")
def start_retry_failed(article_ids: str = Form(...), include_exhausted: bool = Form(False)):
    parsed_ids = [int(item.strip()) for item in article_ids.split(",") if item.strip()]
    job_runner.start_job(
        "retry_failed",
        retry_failed_articles,
        {
            "article_ids": parsed_ids,
            "include_exhausted": include_exhausted,
        },
    )
    return RedirectResponse("/jobs", status_code=303)


@router.post("/send-report")
def start_send_report(excel_path: str = Form(...)):
    job_runner.start_job("send_report", send_report, {"excel_path": Path(excel_path)})
    return RedirectResponse("/jobs", status_code=303)


@router.get("/{job_id}")
def job_detail(request: Request, job_id: str):
    job = job_runner.get_job(job_id)
    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "active_nav": "jobs",
            "page_title": "运行中心",
            "jobs": job_runner.list_jobs(),
            "selected_job": job,
        },
    )
```

- [ ] **Step 5: Register jobs router**

Modify `src/market_info/web/app.py`:

```python
from market_info.web.routes import dashboard, jobs
```

Inside `create_app()` after dashboard:

```python
    app.include_router(jobs.router)
```

- [ ] **Step 6: Update nav active state**

Modify the jobs nav link in `src/market_info/web/templates/base.html`:

```html
<a class="nav-link {% if active_nav == 'jobs' %}is-active{% endif %}" href="/jobs">运行中心</a>
```

- [ ] **Step 7: Add jobs template**

Create `src/market_info/web/templates/jobs.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  <section class="metric-grid" aria-label="任务操作">
    <form class="metric-tile" method="post" action="/jobs/check-auth">
      <span class="metric-label">微信登录</span>
      <strong class="metric-value">Auth</strong>
      {{ ui.command_button("检查登录", None, "primary", "检查中") }}
    </form>
    <form class="metric-tile" method="post" action="/jobs/run-weekly">
      <label class="metric-label" for="weekly-limit">周报 limit</label>
      <input id="weekly-limit" class="field-input" name="limit" type="number" min="1" value="10">
      {{ ui.command_button("运行周报", None, "primary", "运行中") }}
    </form>
    <form class="metric-tile" method="post" action="/jobs/process-pending">
      <label class="metric-label" for="pending-limit">处理 limit</label>
      <input id="pending-limit" class="field-input" name="limit" type="number" min="1" value="20">
      {{ ui.command_button("处理 pending", None, "secondary", "处理中") }}
    </form>
    <form class="metric-tile" method="post" action="/jobs/retry-failed">
      <label class="metric-label" for="article-ids">失败文章 ID</label>
      <input id="article-ids" class="field-input" name="article_ids" type="text" placeholder="76,104" required>
      <label class="check-row">
        <input name="include_exhausted" type="checkbox" value="true">
        包含 exhausted
      </label>
      {{ ui.command_button("重试失败", None, "secondary", "提交中") }}
    </form>
  </section>

  {% call ui.glass_panel("任务记录", "最近启动的本地任务") %}
    {% if jobs %}
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>类型</th>
              <th>状态</th>
              <th>开始时间</th>
              <th>结束时间</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            {% for job in jobs %}
              <tr>
                <td><a href="/jobs/{{ job.id }}">{{ job.kind }}</a></td>
                <td>{{ ui.status_pill(job.status, "ok" if job.status == "succeeded" else "danger" if job.status == "failed" else "amber") }}</td>
                <td>{{ job.started_at or "" }}</td>
                <td>{{ job.finished_at or "" }}</td>
                <td>{{ job.error_message or "" }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% else %}
      <p class="empty-state">还没有任务记录。先检查登录或运行一次周报。</p>
    {% endif %}
  {% endcall %}
{% endblock %}
```

- [ ] **Step 8: Add form field CSS**

Append to `src/market_info/web/static/styles.css`:

```css
.field-input {
  width: 100%;
  min-height: 44px;
  margin: 12px 0;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 0 12px;
  color: var(--ink);
  background: rgba(255, 255, 255, 0.78);
  font: inherit;
}

.field-input:focus {
  outline: 3px solid rgba(10, 132, 255, 0.25);
  border-color: rgba(10, 132, 255, 0.36);
}

.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  color: var(--muted);
  font-size: 13px;
}
```

- [ ] **Step 9: Run task tests**

Run:

```powershell
python -m pytest tests/test_web_job_runner.py tests/test_web_app.py -v
```

Expected:

```text
All selected tests pass
```

**Prompt for Task 4 execution:**

```text
Implement Task 4 from docs/superpowers/plans/2026-07-02-market-info-ops-mvp-plan.md. Add the in-memory job runner and `/jobs` routes/forms. Keep long-running work out of request handling by using the runner. Do not add SSE yet; the MVP can redirect and show task state. Run `python -m pytest tests/test_web_job_runner.py tests/test_web_app.py -v` and `python -m pytest -q`. Report changed files and test results.
```

---

## Task 5: Article Queue Page

**Files:**
- Create: `src/market_info/web/services/article_service.py`
- Create: `src/market_info/web/routes/articles.py`
- Create: `src/market_info/web/templates/articles.html`
- Modify: `src/market_info/web/app.py`
- Modify: `src/market_info/web/templates/base.html`
- Test: `tests/test_web_article_service.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `SourceArticle`, `get_session`, `retry_failed_articles`.
- Produces: `ArticleQueueItem` dataclass.
- Produces: `list_articles(status: str | None = None, account_name: str | None = None, limit: int = 100) -> list[ArticleQueueItem]`.
- Produces: `count_articles_by_status() -> dict[str, int]`.
- Produces routes `GET /articles` and `POST /articles/retry`.

- [ ] **Step 1: Write article service tests with SQLite**

Create `tests/test_web_article_service.py`:

```python
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import SourceArticle
from market_info.web.services import article_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(article_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def make_article(title: str, status: str, attempts: int = 0) -> SourceArticle:
    return SourceArticle(
        account_id=1,
        account_name="account",
        title=title,
        article_url=f"https://example.com/{title}",
        normalized_url=f"https://example.com/{title}",
        published_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        content_text="content",
        content_hash=(title + "x" * 64)[:64],
        processing_status=status,
        extraction_attempts=attempts,
    )


def test_list_articles_filters_status(sqlite_session) -> None:
    sqlite_session.add_all([
        make_article("pending", "pending"),
        make_article("processed", "processed"),
    ])
    sqlite_session.commit()

    rows = article_service.list_articles(status="pending")

    assert [row.title for row in rows] == ["pending"]
    assert rows[0].status == "pending"


def test_count_articles_by_status(sqlite_session) -> None:
    sqlite_session.add_all([
        make_article("pending", "pending"),
        make_article("failed", "failed", attempts=2),
        make_article("processed", "processed"),
    ])
    sqlite_session.commit()

    counts = article_service.count_articles_by_status()

    assert counts["pending"] == 1
    assert counts["failed"] == 1
    assert counts["processed"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_article_service.py -v
```

Expected:

```text
ImportError: cannot import name 'article_service'
```

- [ ] **Step 3: Implement article service**

Create `src/market_info/web/services/article_service.py`:

```python
from dataclasses import dataclass
from datetime import datetime

from market_info.db.models import SourceArticle
from market_info.db.session import get_session


@dataclass(frozen=True)
class ArticleQueueItem:
    id: int
    account_name: str
    title: str
    article_url: str
    published_at: datetime | None
    status: str
    attempts: int
    extraction_error: str
    processed_at: datetime | None


def list_articles(
    status: str | None = None,
    account_name: str | None = None,
    limit: int = 100,
) -> list[ArticleQueueItem]:
    with get_session() as session:
        query = session.query(SourceArticle)
        if status:
            query = query.filter(SourceArticle.processing_status == status)
        if account_name:
            query = query.filter(SourceArticle.account_name == account_name)
        rows = (
            query.order_by(SourceArticle.created_at.desc(), SourceArticle.id.desc())
            .limit(limit)
            .all()
        )
        return [_to_item(row) for row in rows]


def count_articles_by_status() -> dict[str, int]:
    with get_session() as session:
        return {
            "pending": session.query(SourceArticle).filter(SourceArticle.processing_status == "pending").count(),
            "failed": session.query(SourceArticle).filter(SourceArticle.processing_status == "failed").count(),
            "processed": session.query(SourceArticle).filter(SourceArticle.processing_status == "processed").count(),
        }


def _to_item(article: SourceArticle) -> ArticleQueueItem:
    return ArticleQueueItem(
        id=article.id,
        account_name=article.account_name,
        title=article.title,
        article_url=article.article_url,
        published_at=article.published_at,
        status=article.processing_status,
        attempts=article.extraction_attempts or 0,
        extraction_error=article.extraction_error or "",
        processed_at=article.processed_at,
    )
```

- [ ] **Step 4: Add article routes**

Create `src/market_info/web/routes/articles.py`:

```python
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from market_info.web.templating import templates
from market_info.web.services.article_service import count_articles_by_status, list_articles
from market_info.web.services.job_runner import job_runner
from market_info.jobs.weekly_job import retry_failed_articles


router = APIRouter(prefix="/articles")


@router.get("")
def articles_page(
    request: Request,
    status: str | None = None,
    account_name: str | None = None,
):
    return templates.TemplateResponse(
        "articles.html",
        {
            "request": request,
            "active_nav": "articles",
            "page_title": "文章队列",
            "articles": list_articles(status=status, account_name=account_name),
            "counts": count_articles_by_status(),
            "selected_status": status or "",
            "selected_account": account_name or "",
        },
    )


@router.post("/retry")
def retry_articles(article_ids: str = Form(...), include_exhausted: bool = Form(False)):
    parsed_ids = [int(item.strip()) for item in article_ids.split(",") if item.strip()]
    job_runner.start_job(
        "retry_failed",
        retry_failed_articles,
        {
            "article_ids": parsed_ids,
            "include_exhausted": include_exhausted,
        },
    )
    return RedirectResponse("/articles?status=failed", status_code=303)
```

- [ ] **Step 5: Register article router and nav state**

Modify `src/market_info/web/app.py`:

```python
from market_info.web.routes import articles, dashboard, jobs
```

Inside `create_app()`:

```python
    app.include_router(articles.router)
```

Modify the articles nav link in `src/market_info/web/templates/base.html`:

```html
<a class="nav-link {% if active_nav == 'articles' %}is-active{% endif %}" href="/articles">文章队列</a>
```

- [ ] **Step 6: Add article template**

Create `src/market_info/web/templates/articles.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  <section class="metric-grid" aria-label="文章状态">
    {{ ui.metric_tile("待处理", counts.pending, "pending", "neutral") }}
    {{ ui.metric_tile("失败", counts.failed, "failed", "amber") }}
    {{ ui.metric_tile("已处理", counts.processed, "processed", "blue") }}
    <form class="metric-tile" method="post" action="/articles/retry">
      <label class="metric-label" for="retry-article-ids">重试文章 ID</label>
      <input id="retry-article-ids" class="field-input" name="article_ids" type="text" placeholder="76,104" required>
      <label class="check-row">
        <input name="include_exhausted" type="checkbox" value="true">
        包含 exhausted
      </label>
      {{ ui.command_button("提交重试", None, "secondary", "提交中") }}
    </form>
  </section>

  {% call ui.glass_panel("文章列表", "按处理状态查看文章，并对失败文章发起重试") %}
    <form class="filter-row" method="get" action="/articles">
      <label>
        状态
        <select class="field-input" name="status">
          <option value="" {% if not selected_status %}selected{% endif %}>全部</option>
          <option value="pending" {% if selected_status == "pending" %}selected{% endif %}>pending</option>
          <option value="failed" {% if selected_status == "failed" %}selected{% endif %}>failed</option>
          <option value="processed" {% if selected_status == "processed" %}selected{% endif %}>processed</option>
        </select>
      </label>
      <label>
        公众号
        <input class="field-input" name="account_name" type="text" value="{{ selected_account }}">
      </label>
      {{ ui.command_button("筛选", None, "secondary", "筛选中") }}
    </form>

    {% if articles %}
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>公众号</th>
              <th>标题</th>
              <th>状态</th>
              <th>尝试</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            {% for article in articles %}
              <tr>
                <td>{{ article.id }}</td>
                <td>{{ article.account_name }}</td>
                <td><a href="{{ article.article_url }}" target="_blank" rel="noreferrer">{{ article.title }}</a></td>
                <td>{{ ui.status_pill(article.status, "danger" if article.status == "failed" else "ok" if article.status == "processed" else "amber") }}</td>
                <td>{{ article.attempts }}</td>
                <td class="error-cell">{{ article.extraction_error }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% else %}
      <p class="empty-state">没有匹配的文章。</p>
    {% endif %}
  {% endcall %}
{% endblock %}
```

- [ ] **Step 7: Add article page CSS**

Append to `src/market_info/web/static/styles.css`:

```css
.filter-row {
  display: grid;
  grid-template-columns: minmax(160px, 220px) minmax(220px, 1fr) auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 16px;
}

.filter-row label {
  color: var(--muted);
  font-size: 13px;
  font-weight: 650;
}

.error-cell {
  max-width: 360px;
  color: #7f1d1d;
  overflow-wrap: anywhere;
}

@media (max-width: 760px) {
  .filter-row {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 8: Run task tests**

Run:

```powershell
python -m pytest tests/test_web_article_service.py tests/test_web_app.py -v
```

Expected:

```text
All selected tests pass
```

**Prompt for Task 5 execution:**

```text
Implement Task 5 from docs/superpowers/plans/2026-07-02-market-info-ops-mvp-plan.md. Add article queue service, `/articles` page, status filtering, and retry submission through the existing job runner. Keep article full text out of the page. Run `python -m pytest tests/test_web_article_service.py tests/test_web_app.py -v` and `python -m pytest -q`. Report changed files and test results.
```

---

## Task 6: Report Center with Safe Excel Listing, Download, and Send

**Files:**
- Create: `src/market_info/web/services/report_service.py`
- Create: `src/market_info/web/routes/reports.py`
- Create: `src/market_info/web/templates/reports.html`
- Modify: `src/market_info/web/app.py`
- Modify: `src/market_info/web/templates/base.html`
- Test: `tests/test_web_report_service.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `Settings.export_dir`, existing `send_report`.
- Produces: `ReportListItem` dataclass.
- Produces: `list_reports(export_dir: Path | None = None) -> list[ReportListItem]`.
- Produces: `resolve_report_path(report_name: str, export_dir: Path | None = None) -> Path`.
- Produces routes `GET /reports`, `GET /reports/{report_name}/download`, `POST /reports/{report_name}/send`.

- [ ] **Step 1: Write report service tests**

Create `tests/test_web_report_service.py`:

```python
from pathlib import Path

import pytest

from market_info.web.services.report_service import list_reports, resolve_report_path


def test_list_reports_only_returns_xlsx_sorted_newest_first(tmp_path: Path) -> None:
    old = tmp_path / "market_info_weekly_20260624_102824.xlsx"
    new = tmp_path / "market_info_weekly_20260629_103132.xlsx"
    ignored = tmp_path / "notes.txt"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    ignored.write_text("ignore", encoding="utf-8")

    rows = list_reports(tmp_path)

    assert [row.name for row in rows] == [new.name, old.name]
    assert rows[0].size_bytes == len(b"new")


def test_resolve_report_path_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid report name"):
        resolve_report_path("../.env", tmp_path)


def test_resolve_report_path_requires_xlsx(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Only .xlsx reports"):
        resolve_report_path("notes.txt", tmp_path)


def test_resolve_report_path_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_report_path("missing.xlsx", tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_web_report_service.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'market_info.web.services.report_service'
```

- [ ] **Step 3: Implement report service**

Create `src/market_info/web/services/report_service.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from market_info.config import Settings


@dataclass(frozen=True)
class ReportListItem:
    name: str
    path: Path
    size_bytes: int
    modified_at: float


def list_reports(export_dir: Path | None = None) -> list[ReportListItem]:
    root = export_dir or Path(Settings().export_dir)
    if not root.exists() or not root.is_dir():
        return []
    reports = []
    for path in root.iterdir():
        if not path.is_file() or path.suffix.lower() != ".xlsx":
            continue
        stat = path.stat()
        reports.append(
            ReportListItem(
                name=path.name,
                path=path,
                size_bytes=stat.st_size,
                modified_at=stat.st_mtime,
            )
        )
    return sorted(reports, key=lambda item: item.modified_at, reverse=True)


def resolve_report_path(report_name: str, export_dir: Path | None = None) -> Path:
    if Path(report_name).name != report_name:
        raise ValueError("Invalid report name")
    if Path(report_name).suffix.lower() != ".xlsx":
        raise ValueError("Only .xlsx reports can be downloaded")
    root = (export_dir or Path(Settings().export_dir)).resolve()
    candidate = (root / report_name).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Invalid report path")
    if not candidate.is_file():
        raise FileNotFoundError(report_name)
    return candidate
```

- [ ] **Step 4: Add report routes**

Create `src/market_info/web/routes/reports.py`:

```python
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from market_info.jobs.weekly_job import send_report
from market_info.web.templating import templates
from market_info.web.services.job_runner import job_runner
from market_info.web.services.report_service import list_reports, resolve_report_path


router = APIRouter(prefix="/reports")


@router.get("")
def reports_page(request: Request):
    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "active_nav": "reports",
            "page_title": "周报文件",
            "reports": list_reports(),
        },
    )


@router.get("/{report_name}/download")
def download_report(report_name: str):
    try:
        path = resolve_report_path(report_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@router.post("/{report_name}/send")
def send_existing_report(report_name: str):
    try:
        path = resolve_report_path(report_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    job_runner.start_job("send_report", send_report, {"excel_path": path})
    return RedirectResponse("/reports", status_code=303)
```

- [ ] **Step 5: Register report router and nav state**

Modify `src/market_info/web/app.py`:

```python
from market_info.web.routes import articles, dashboard, jobs, reports
```

Inside `create_app()`:

```python
    app.include_router(reports.router)
```

Modify the reports nav link in `src/market_info/web/templates/base.html`:

```html
<a class="nav-link {% if active_nav == 'reports' %}is-active{% endif %}" href="/reports">周报文件</a>
```

- [ ] **Step 6: Add report template**

Create `src/market_info/web/templates/reports.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  {% call ui.glass_panel("周报文件", "仅展示 EXPORT_DIR 下的 .xlsx 文件") %}
    {% if reports %}
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th>大小</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {% for report in reports %}
              <tr>
                <td>{{ report.name }}</td>
                <td>{{ report.size_bytes }} bytes</td>
                <td>{{ report.modified_at }}</td>
                <td class="action-cell">
                  <a class="command-button command-secondary" href="/reports/{{ report.name }}/download">下载</a>
                  <form method="post" action="/reports/{{ report.name }}/send">
                    {{ ui.command_button("重新发送", None, "primary", "发送中") }}
                  </form>
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% else %}
      <p class="empty-state">还没有 Excel 周报。运行一次周报后会出现在这里。</p>
    {% endif %}
  {% endcall %}
{% endblock %}
```

- [ ] **Step 7: Add report action CSS**

Append to `src/market_info/web/static/styles.css`:

```css
.action-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.action-cell form {
  margin: 0;
}
```

- [ ] **Step 8: Add route smoke test for reports page**

Append to `tests/test_web_app.py`:

```python
def test_reports_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/reports")

    assert response.status_code == 200
    assert "周报文件" in response.text
```

- [ ] **Step 9: Run task tests**

Run:

```powershell
python -m pytest tests/test_web_report_service.py tests/test_web_app.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 10: Run full MVP verification**

Run:

```powershell
python -m pytest -q
```

Expected:

```text
All tests pass
```

Run:

```powershell
market-info web --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080
http://127.0.0.1:8080/jobs
http://127.0.0.1:8080/articles
http://127.0.0.1:8080/reports
```

Expected:

```text
Each page renders without a server error, uses the white liquid-glass shell, and preserves readable tables/actions.
```

**Prompt for Task 6 execution:**

```text
Implement Task 6 from docs/superpowers/plans/2026-07-02-market-info-ops-mvp-plan.md. Add the report service, `/reports` page, safe `.xlsx` listing, secure download resolution, and resend action through the existing job runner. Enforce path traversal protection exactly as described. Run `python -m pytest tests/test_web_report_service.py tests/test_web_app.py -v`, then `python -m pytest -q`, then smoke-test `market-info web --host 127.0.0.1 --port 8080`. Report changed files and test results.
```

---

## Self-Review Checklist

- Spec coverage: Task 1-6 cover the web shell, white liquid-glass visual system, dashboard, job center, article queue, and report center.
- Scope control: Dedupe review, project ledger, golden evaluation, settings page, authentication, and persisted job tables are excluded from this MVP plan and require separate plans.
- Interface consistency: `create_app`, `DashboardOverview`, `ReportFileSummary`, `InMemoryJobRunner`, `JobStatus`, `ArticleQueueItem`, `ReportListItem`, `list_articles`, `list_reports`, and `resolve_report_path` are defined before use.
- Security coverage: Report downloads are restricted to `.xlsx` files under `EXPORT_DIR`; article full text and secrets are not rendered.
- Visual coverage: The plan defines the white liquid-glass token system, reusable components, responsive behavior, focus states, and reduced-motion behavior.
- Test coverage: Each service has a focused test file; route smoke tests live in `tests/test_web_app.py`; final acceptance runs `python -m pytest -q`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-02-market-info-ops-mvp-plan.md`.

Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.

Suggested first execution prompt:

```text
Start with Task 1 from docs/superpowers/plans/2026-07-02-market-info-ops-mvp-plan.md. Use TDD, keep changes scoped to Task 1, and stop after tests pass so the result can be reviewed before Task 2.
```
