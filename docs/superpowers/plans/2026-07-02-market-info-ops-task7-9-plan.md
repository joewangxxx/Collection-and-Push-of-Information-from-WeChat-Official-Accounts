# Market Info Ops Task 7-9 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the local/intranet Market Info Ops console from passive monitoring into a practical operations workbench: manual dedupe review, project ledger browsing, and quality/configuration visibility.

**Architecture:** Continue the server-rendered FastAPI + Jinja architecture introduced in Task 1-6. Keep route modules thin, put database/query/write behavior in focused `src/market_info/web/services/*.py` services, reuse the existing `apply_match_decision`, `export_golden_template`, `evaluate_golden`, `Settings`, and `job_runner` APIs, and avoid new database tables in this phase.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, SQLAlchemy, existing dedupe/evaluation modules, pytest, FastAPI TestClient, HTML/CSS/vanilla JavaScript.

## Global Constraints

- Preserve the white Apple liquid-glass visual language: light canvas, translucent panels, restrained status colors, clear focus states, no decorative clutter.
- Do not expose `.env`, API keys, SMTP passwords, WeChat auth keys, webhook URLs, article full text, embeddings, or raw database internals in the web UI.
- Do not add migrations in Task 7-9; use existing `Project`, `ProjectRecord`, `ProjectEvent`, and `SourceArticle` fields.
- Use server-rendered pages and small services; do not introduce React, Next.js, or a SPA.
- Every write action must happen through a POST route and must redirect after success.
- Manual review actions may only resolve records whose `ProjectRecord.dedupe_decision == "review"`.
- All new routes must render inside the existing `base.html` shell and preserve mobile responsiveness at 375px, 768px, 1024px, and 1440px.
- Use `python -m pytest ...` for Windows-friendly test commands.
- Full acceptance requires `python -m pytest -q` to remain green.

---

## File Structure

Task 7-9 create or modify the following files.

```text
src/market_info/web/app.py
src/market_info/web/routes/reviews.py
src/market_info/web/routes/projects.py
src/market_info/web/routes/quality.py
src/market_info/web/services/review_service.py
src/market_info/web/services/project_service.py
src/market_info/web/services/quality_service.py
src/market_info/web/templates/base.html
src/market_info/web/templates/reviews.html
src/market_info/web/templates/review_detail.html
src/market_info/web/templates/projects.html
src/market_info/web/templates/project_detail.html
src/market_info/web/templates/quality.html
src/market_info/web/static/styles.css
tests/test_web_review_service.py
tests/test_web_project_service.py
tests/test_web_quality_service.py
tests/test_web_app.py
docs/superpowers/plans/2026-07-02-market-info-ops-task7-9-plan.md
```

Responsibilities:

- `review_service.py`: load review records, find merge candidates, and apply manual `new` or `merge` decisions.
- `project_service.py`: list searchable project ledger rows and provide project detail timelines.
- `quality_service.py`: summarize golden evaluation reports, start safe golden export/eval jobs, and expose masked configuration health.
- `routes/reviews.py`: review list/detail pages and POST actions for `new` and `merge`.
- `routes/projects.py`: project ledger and project detail pages.
- `routes/quality.py`: quality/config page and POST actions for golden dataset export/evaluation.
- `templates/*.html`: liquid-glass pages using existing `components.html` macros.
- `styles.css`: data-dense review/detail/timeline styles that reuse existing tokens.
- `tests/test_web_*.py`: service tests with in-memory SQLite and route smoke tests with `TestClient`.

---

## Task 7: Manual Dedupe Review Workbench

**Files:**
- Create: `src/market_info/web/services/review_service.py`
- Create: `src/market_info/web/routes/reviews.py`
- Create: `src/market_info/web/templates/reviews.html`
- Create: `src/market_info/web/templates/review_detail.html`
- Modify: `src/market_info/web/app.py`
- Modify: `src/market_info/web/templates/base.html`
- Modify: `src/market_info/web/static/styles.css`
- Test: `tests/test_web_review_service.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `market_info.dedupe.matcher.apply_match_decision(session, record, decision)`.
- Consumes: `market_info.dedupe.matcher.MatchDecision`.
- Produces: `ReviewQueueItem` dataclass with fields `id`, `project_name`, `company_name`, `province`, `city`, `status`, `dedupe_score`, `article_title`, `article_url`, `account_name`, `published_at`, `created_at`.
- Produces: `ReviewCandidateItem` dataclass with fields `id`, `project_name`, `company_name`, `province`, `city`, `status`, `last_seen_at`, `score_hint`.
- Produces: `ReviewResolutionResult` dataclass with fields `record_id`, `decision`, `project_id`.
- Produces: `list_review_records(limit: int = 100) -> list[ReviewQueueItem]`.
- Produces: `get_review_record(record_id: int) -> ReviewQueueItem`.
- Produces: `list_project_candidates(record_id: int, query: str | None = None, limit: int = 8) -> list[ReviewCandidateItem]`.
- Produces: `resolve_review_record(record_id: int, decision: Literal["new", "merge"], project_id: int | None = None) -> ReviewResolutionResult`.
- Produces routes `GET /reviews`, `GET /reviews/{record_id}`, `POST /reviews/{record_id}/new`, `POST /reviews/{record_id}/merge`.

- [ ] **Step 1: Write failing review service tests**

Create `tests/test_web_review_service.py`:

```python
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import Project, ProjectRecord, SourceArticle
from market_info.web.services import review_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(review_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def make_article(title: str = "光伏项目备案") -> SourceArticle:
    return SourceArticle(
        account_id=1,
        account_name="光伏前沿",
        title=title,
        article_url="https://mp.weixin.qq.com/s/review",
        normalized_url="https://mp.weixin.qq.com/s/review",
        published_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
        content_text="正文不应出现在复核列表里",
        content_hash="a" * 64,
    )


def make_review_record(article: SourceArticle) -> ProjectRecord:
    return ProjectRecord(
        source_article=article,
        project_name="盐城光伏组件扩产项目",
        project_info="新增组件产线",
        province="江苏省",
        city="盐城市",
        company_name="江苏示例新能源有限公司",
        status="备案",
        dedupe_decision="review",
        dedupe_score=76.5,
        semantic_text="盐城 光伏 组件 扩产",
    )


def test_list_review_records_returns_review_items_without_article_body(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    sqlite_session.add(record)
    sqlite_session.commit()

    rows = review_service.list_review_records()

    assert len(rows) == 1
    assert rows[0].id == record.id
    assert rows[0].project_name == "盐城光伏组件扩产项目"
    assert rows[0].article_title == "光伏项目备案"
    assert not hasattr(rows[0], "content_text")


def test_list_project_candidates_prefers_same_province_and_name_query(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    candidate = Project(
        canonical_project_name="盐城光伏组件一期项目",
        canonical_company_name="江苏示例新能源有限公司",
        province="江苏省",
        city="盐城市",
        current_status="开工",
        last_seen_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    sqlite_session.add_all([record, candidate])
    sqlite_session.commit()

    rows = review_service.list_project_candidates(record.id, query="光伏")

    assert [row.id for row in rows] == [candidate.id]
    assert rows[0].score_hint == "same province"


def test_resolve_review_record_as_new_creates_project(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    sqlite_session.add(record)
    sqlite_session.commit()

    result = review_service.resolve_review_record(record.id, "new")

    sqlite_session.refresh(record)
    assert result.decision == "new"
    assert result.project_id == record.project_id
    assert record.dedupe_decision == "new"
    assert sqlite_session.query(Project).count() == 1


def test_resolve_review_record_as_merge_links_existing_project(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    project = Project(
        canonical_project_name="盐城光伏组件一期项目",
        canonical_company_name="江苏示例新能源有限公司",
        province="江苏省",
        city="盐城市",
        current_status="备案",
        last_seen_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    sqlite_session.add_all([record, project])
    sqlite_session.commit()

    result = review_service.resolve_review_record(record.id, "merge", project.id)

    sqlite_session.refresh(record)
    assert result.decision == "merge"
    assert result.project_id == project.id
    assert record.project_id == project.id
    assert record.dedupe_decision == "merge"


def test_resolve_review_record_rejects_non_review_record(sqlite_session) -> None:
    article = make_article()
    record = make_review_record(article)
    record.dedupe_decision = "new"
    sqlite_session.add(record)
    sqlite_session.commit()

    with pytest.raises(ValueError, match="not pending review"):
        review_service.resolve_review_record(record.id, "new")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_web_review_service.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'market_info.web.services.review_service'
```

- [ ] **Step 3: Implement review service**

Create `src/market_info/web/services/review_service.py` with these dataclasses and function signatures:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import or_

from market_info.db.models import Project, ProjectRecord, SourceArticle
from market_info.db.session import get_session
from market_info.dedupe.matcher import MatchDecision, apply_match_decision


ReviewDecision = Literal["new", "merge"]


@dataclass(frozen=True)
class ReviewQueueItem:
    id: int
    project_name: str
    company_name: str
    province: str
    city: str
    status: str
    dedupe_score: float | None
    article_title: str
    article_url: str
    account_name: str
    published_at: datetime | None
    created_at: datetime | None


@dataclass(frozen=True)
class ReviewCandidateItem:
    id: int
    project_name: str
    company_name: str
    province: str
    city: str
    status: str
    last_seen_at: datetime | None
    score_hint: str


@dataclass(frozen=True)
class ReviewResolutionResult:
    record_id: int
    decision: ReviewDecision
    project_id: int | None
```

Implementation rules:

- `list_review_records()` queries `ProjectRecord` joined to `SourceArticle`, filters `dedupe_decision == "review"`, orders by `ProjectRecord.created_at.desc()` then `ProjectRecord.id.desc()`, and maps to `ReviewQueueItem`.
- `get_review_record()` returns one review record by id or raises `ValueError("Review record not found")`.
- `list_project_candidates()` loads the review record, queries `Project`, filters by `query` against `canonical_project_name` and `canonical_company_name` when provided, otherwise prefers same `province`, orders by `last_seen_at.desc()` then `id.desc()`, and limits results.
- Candidate `score_hint` is `"same province"` when `project.province == record.province`, otherwise `"search match"`.
- `resolve_review_record()` loads the record, rejects records that are not pending review with `ValueError("Record is not pending review")`, rejects `merge` without `project_id` with `ValueError("Merge decision requires project_id")`, calls `apply_match_decision()` with `MatchDecision(decision=decision, final_score=record.dedupe_score or 100.0, project_id=project_id, rule_score=0.0, vector_score=0.0)`, commits, and returns `ReviewResolutionResult`.

- [ ] **Step 4: Add review routes**

Create `src/market_info/web/routes/reviews.py`:

```python
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from market_info.web.services.review_service import (
    get_review_record,
    list_project_candidates,
    list_review_records,
    resolve_review_record,
)
from market_info.web.templating import templates


router = APIRouter(prefix="/reviews")


@router.get("")
def reviews_page(request: Request):
    return templates.TemplateResponse(
        name="reviews.html",
        request=request,
        context={
            "request": request,
            "active_nav": "reviews",
            "page_title": "复核工作台",
            "records": list_review_records(),
        },
    )


@router.get("/{record_id}")
def review_detail_page(request: Request, record_id: int, q: str | None = None):
    try:
        record = get_review_record(record_id)
        candidates = list_project_candidates(record_id, query=q)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        name="review_detail.html",
        request=request,
        context={
            "request": request,
            "active_nav": "reviews",
            "page_title": "复核详情",
            "record": record,
            "candidates": candidates,
            "query": q or "",
        },
    )


@router.post("/{record_id}/new")
def resolve_as_new(record_id: int):
    try:
        resolve_review_record(record_id, "new")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/reviews", status_code=303)


@router.post("/{record_id}/merge")
def resolve_as_merge(record_id: int, project_id: int = Form(...)):
    try:
        resolve_review_record(record_id, "merge", project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/reviews", status_code=303)
```

- [ ] **Step 5: Register route and navigation**

Modify `src/market_info/web/app.py`:

```python
from market_info.web.routes import articles, dashboard, jobs, reports, reviews
```

Inside `create_app()` after articles:

```python
    app.include_router(reviews.router)
```

Modify `src/market_info/web/templates/base.html` navigation:

```html
<a class="nav-link {% if active_nav == 'reviews' %}is-active{% endif %}" href="/reviews">复核工作台</a>
```

- [ ] **Step 6: Add review templates**

Create `src/market_info/web/templates/reviews.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  {% call ui.glass_panel("复核队列", "处理 dedupe_decision=review 的疑似重复项目") %}
    {% if records %}
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>项目</th>
              <th>企业</th>
              <th>地区</th>
              <th>状态</th>
              <th>分数</th>
              <th>来源文章</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {% for record in records %}
              <tr>
                <td>{{ record.id }}</td>
                <td>{{ record.project_name }}</td>
                <td>{{ record.company_name }}</td>
                <td>{{ record.province }} {{ record.city }}</td>
                <td>{{ record.status }}</td>
                <td>{{ record.dedupe_score or "" }}</td>
                <td><a href="{{ record.article_url }}" target="_blank" rel="noreferrer">{{ record.article_title }}</a></td>
                <td><a class="command-button command-secondary" href="/reviews/{{ record.id }}">处理</a></td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% else %}
      <p class="empty-state">当前没有待复核记录。</p>
    {% endif %}
  {% endcall %}
{% endblock %}
```

Create `src/market_info/web/templates/review_detail.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  <section class="detail-grid">
    {% call ui.glass_panel("待复核记录", "确认该抽取记录应该新建项目，还是并入已有项目") %}
      <dl class="detail-list">
        <dt>项目</dt><dd>{{ record.project_name }}</dd>
        <dt>企业</dt><dd>{{ record.company_name }}</dd>
        <dt>地区</dt><dd>{{ record.province }} {{ record.city }}</dd>
        <dt>状态</dt><dd>{{ record.status }}</dd>
        <dt>分数</dt><dd>{{ record.dedupe_score or "" }}</dd>
        <dt>来源</dt><dd><a href="{{ record.article_url }}" target="_blank" rel="noreferrer">{{ record.article_title }}</a></dd>
      </dl>
      <form method="post" action="/reviews/{{ record.id }}/new">
        {{ ui.command_button("作为新项目入库", None, "primary", "处理中") }}
      </form>
    {% endcall %}

    {% call ui.glass_panel("候选项目", "选择一个已有项目进行合并") %}
      <form class="filter-row" method="get" action="/reviews/{{ record.id }}">
        <label>
          搜索项目或企业
          <input class="field-input" name="q" type="text" value="{{ query }}">
        </label>
        {{ ui.command_button("搜索", None, "secondary", "搜索中") }}
      </form>
      {% if candidates %}
        <div class="candidate-list">
          {% for candidate in candidates %}
            <form class="candidate-row" method="post" action="/reviews/{{ record.id }}/merge">
              <input type="hidden" name="project_id" value="{{ candidate.id }}">
              <div>
                <strong>{{ candidate.project_name }}</strong>
                <span>{{ candidate.company_name }} · {{ candidate.province }} {{ candidate.city }} · {{ candidate.status }}</span>
              </div>
              {{ ui.status_pill(candidate.score_hint, "amber") }}
              {{ ui.command_button("合并到此项目", None, "secondary", "处理中") }}
            </form>
          {% endfor %}
        </div>
      {% else %}
        <p class="empty-state">没有找到候选项目，可以作为新项目入库。</p>
      {% endif %}
    {% endcall %}
  </section>
{% endblock %}
```

- [ ] **Step 7: Add review CSS**

Append to `src/market_info/web/static/styles.css`:

```css
.detail-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.1fr);
  gap: 20px;
  align-items: start;
}

.detail-list {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px 16px;
  margin: 0 0 20px;
}

.detail-list dt {
  color: var(--muted);
  font-weight: 700;
}

.detail-list dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.candidate-list {
  display: grid;
  gap: 12px;
}

.candidate-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.72);
}

.candidate-row span {
  display: block;
  margin-top: 4px;
  color: var(--muted);
  font-size: 13px;
}

@media (max-width: 980px) {
  .detail-grid,
  .candidate-row {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 8: Add route smoke tests**

Append to `tests/test_web_app.py`:

```python
def test_reviews_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/reviews")

    assert response.status_code == 200
    assert "复核工作台" in response.text
```

- [ ] **Step 9: Run Task 7 tests**

Run:

```powershell
python -m pytest tests/test_web_review_service.py tests/test_web_app.py -v
python -m pytest -q
```

Expected:

```text
All selected tests pass
Full test suite passes
```

- [ ] **Step 10: Manual acceptance for Task 7**

Run:

```powershell
market-info web --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/reviews
```

Expected:

```text
The review page renders in the liquid-glass shell, shows pending review records without article body text, and detail actions submit via POST.
```

**Prompt for Task 7 execution:**

```text
Implement Task 7 from docs/superpowers/plans/2026-07-02-market-info-ops-task7-9-plan.md. Use TDD exactly as written. Add the manual dedupe review workbench with service functions, routes, templates, nav entry, and CSS. Reuse apply_match_decision and do not add database migrations. Keep article full text and embeddings out of the UI. Run `python -m pytest tests/test_web_review_service.py tests/test_web_app.py -v`, then `python -m pytest -q`, then smoke-test `/reviews`. Report changed files and verification output.
```

---

## Task 8: Project Ledger and Timeline Pages

**Files:**
- Create: `src/market_info/web/services/project_service.py`
- Create: `src/market_info/web/routes/projects.py`
- Create: `src/market_info/web/templates/projects.html`
- Create: `src/market_info/web/templates/project_detail.html`
- Modify: `src/market_info/web/app.py`
- Modify: `src/market_info/web/templates/base.html`
- Modify: `src/market_info/web/static/styles.css`
- Test: `tests/test_web_project_service.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Produces: `ProjectListItem` dataclass with fields `id`, `project_name`, `company_name`, `province`, `city`, `industry`, `market`, `status`, `investment_amount_yi`, `first_seen_at`, `last_seen_at`.
- Produces: `ProjectRecordSummary` dataclass with fields `id`, `article_title`, `article_url`, `account_name`, `published_at`, `decision`, `score`, `status`, `created_at`.
- Produces: `ProjectEventSummary` dataclass with fields `id`, `event_status`, `previous_status`, `change_label`, `event_date`, `article_title`, `article_url`.
- Produces: `ProjectDetail` dataclass with fields `project`, `records`, `events`.
- Produces: `list_projects(query: str | None = None, province: str | None = None, status: str | None = None, limit: int = 100) -> list[ProjectListItem]`.
- Produces: `get_project_detail(project_id: int) -> ProjectDetail`.
- Produces routes `GET /projects`, `GET /projects/{project_id}`.

- [ ] **Step 1: Write failing project service tests**

Create `tests/test_web_project_service.py`:

```python
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import Project, ProjectEvent, ProjectRecord, SourceArticle
from market_info.web.services import project_service


@pytest.fixture()
def sqlite_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    @contextmanager
    def fake_get_session():
        yield session

    monkeypatch.setattr(project_service, "get_session", fake_get_session)
    try:
        yield session
    finally:
        session.close()


def make_article() -> SourceArticle:
    return SourceArticle(
        account_id=1,
        account_name="光伏前沿",
        title="项目开工公告",
        article_url="https://mp.weixin.qq.com/s/project",
        normalized_url="https://mp.weixin.qq.com/s/project",
        published_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
        content_text="正文不应出现在项目详情里",
        content_hash="b" * 64,
    )


def make_project(name: str, province: str = "江苏省", status: str = "开工") -> Project:
    return Project(
        canonical_project_name=name,
        canonical_company_name="江苏示例新能源有限公司",
        province=province,
        city="盐城市",
        industry="新能源",
        market="电力",
        current_status=status,
        investment_amount_yi=10.5,
        first_seen_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
        semantic_text="不应出现在页面服务返回对象里",
    )


def test_list_projects_filters_by_query_province_and_status(sqlite_session) -> None:
    keep = make_project("盐城光伏组件扩产项目")
    drop = make_project("苏州储能电站项目", province="江苏省", status="备案")
    sqlite_session.add_all([keep, drop])
    sqlite_session.commit()

    rows = project_service.list_projects(query="光伏", province="江苏省", status="开工")

    assert [row.id for row in rows] == [keep.id]
    assert rows[0].project_name == "盐城光伏组件扩产项目"
    assert not hasattr(rows[0], "semantic_text")


def test_get_project_detail_returns_records_and_events(sqlite_session) -> None:
    article = make_article()
    project = make_project("盐城光伏组件扩产项目")
    record = ProjectRecord(
        source_article=article,
        project=project,
        project_name=project.canonical_project_name,
        company_name=project.canonical_company_name,
        status="开工",
        dedupe_decision="merge",
        dedupe_score=91.2,
    )
    event = ProjectEvent(
        project=project,
        source_article=article,
        previous_status="备案",
        event_status="开工",
        event_date=article.published_at,
        change_label="备案 -> 开工",
    )
    sqlite_session.add_all([record, event])
    sqlite_session.commit()

    detail = project_service.get_project_detail(project.id)

    assert detail.project.id == project.id
    assert detail.records[0].article_title == "项目开工公告"
    assert detail.events[0].change_label == "备案 -> 开工"
    assert not hasattr(detail.records[0], "content_text")


def test_get_project_detail_raises_for_missing_project(sqlite_session) -> None:
    with pytest.raises(ValueError, match="Project not found"):
        project_service.get_project_detail(999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_web_project_service.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'market_info.web.services.project_service'
```

- [ ] **Step 3: Implement project service**

Create `src/market_info/web/services/project_service.py` with dataclasses named in the interface section.

Implementation rules:

- `list_projects()` queries `Project`, filters `query` against `canonical_project_name` and `canonical_company_name`, filters exact `province` and `current_status` when provided, orders by `last_seen_at.desc().nullslast()` then `id.desc()`, and maps to `ProjectListItem`.
- `get_project_detail()` loads a project or raises `ValueError("Project not found")`.
- `get_project_detail()` queries records by `project_id`, joins `SourceArticle`, orders by `SourceArticle.published_at.desc()` then `ProjectRecord.id.desc()`.
- `get_project_detail()` queries events by `project_id`, joins `SourceArticle`, orders by `ProjectEvent.event_date.desc()` then `ProjectEvent.id.desc()`.
- Do not include `Project.semantic_text`, `Project.embedding`, `ProjectRecord.semantic_text`, `ProjectRecord.embedding`, or `SourceArticle.content_text` in returned dataclasses.

- [ ] **Step 4: Add project routes**

Create `src/market_info/web/routes/projects.py`:

```python
from fastapi import APIRouter, HTTPException, Request

from market_info.web.services.project_service import get_project_detail, list_projects
from market_info.web.templating import templates


router = APIRouter(prefix="/projects")


@router.get("")
def projects_page(
    request: Request,
    q: str | None = None,
    province: str | None = None,
    status: str | None = None,
):
    return templates.TemplateResponse(
        name="projects.html",
        request=request,
        context={
            "request": request,
            "active_nav": "projects",
            "page_title": "项目台账",
            "projects": list_projects(query=q, province=province, status=status),
            "query": q or "",
            "selected_province": province or "",
            "selected_status": status or "",
        },
    )


@router.get("/{project_id}")
def project_detail_page(request: Request, project_id: int):
    try:
        detail = get_project_detail(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        name="project_detail.html",
        request=request,
        context={
            "request": request,
            "active_nav": "projects",
            "page_title": "项目详情",
            "detail": detail,
        },
    )
```

- [ ] **Step 5: Register route and navigation**

Modify `src/market_info/web/app.py`:

```python
from market_info.web.routes import articles, dashboard, jobs, projects, reports, reviews
```

Inside `create_app()` after reviews:

```python
    app.include_router(projects.router)
```

Modify `src/market_info/web/templates/base.html` navigation:

```html
<a class="nav-link {% if active_nav == 'projects' %}is-active{% endif %}" href="/projects">项目台账</a>
```

- [ ] **Step 6: Add project templates**

Create `src/market_info/web/templates/projects.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  {% call ui.glass_panel("项目台账", "按项目名、企业、地区和状态检索沉淀项目") %}
    <form class="filter-row project-filter" method="get" action="/projects">
      <label>
        项目或企业
        <input class="field-input" name="q" type="text" value="{{ query }}">
      </label>
      <label>
        省份
        <input class="field-input" name="province" type="text" value="{{ selected_province }}">
      </label>
      <label>
        状态
        <input class="field-input" name="status" type="text" value="{{ selected_status }}">
      </label>
      {{ ui.command_button("筛选", None, "secondary", "筛选中") }}
    </form>

    {% if projects %}
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>项目</th>
              <th>企业</th>
              <th>地区</th>
              <th>行业</th>
              <th>市场</th>
              <th>状态</th>
              <th>投资额</th>
              <th>最近发现</th>
            </tr>
          </thead>
          <tbody>
            {% for project in projects %}
              <tr>
                <td>{{ project.id }}</td>
                <td><a href="/projects/{{ project.id }}">{{ project.project_name }}</a></td>
                <td>{{ project.company_name }}</td>
                <td>{{ project.province }} {{ project.city }}</td>
                <td>{{ project.industry }}</td>
                <td>{{ project.market }}</td>
                <td>{{ ui.status_pill(project.status or "未知", "neutral") }}</td>
                <td>{{ project.investment_amount_yi or "" }}</td>
                <td>{{ project.last_seen_at or "" }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% else %}
      <p class="empty-state">没有匹配的项目。</p>
    {% endif %}
  {% endcall %}
{% endblock %}
```

Create `src/market_info/web/templates/project_detail.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  <section class="hero-panel glass-panel">
    <div>
      <p class="eyebrow">Project ledger</p>
      <h2>{{ detail.project.project_name }}</h2>
      <p class="hero-copy">{{ detail.project.company_name }} · {{ detail.project.province }} {{ detail.project.city }} · {{ detail.project.status or "未知" }}</p>
    </div>
    <div class="hero-actions">
      {{ ui.status_pill(detail.project.status or "未知", "neutral") }}
      <a class="command-button command-secondary" href="/projects">返回台账</a>
    </div>
  </section>

  <section class="detail-grid">
    {% call ui.glass_panel("状态时间线", "由项目事件表生成") %}
      {% if detail.events %}
        <ol class="timeline-list">
          {% for event in detail.events %}
            <li>
              <strong>{{ event.change_label or event.event_status }}</strong>
              <span>{{ event.event_date or "" }}</span>
              <a href="{{ event.article_url }}" target="_blank" rel="noreferrer">{{ event.article_title }}</a>
            </li>
          {% endfor %}
        </ol>
      {% else %}
        <p class="empty-state">还没有状态变化事件。</p>
      {% endif %}
    {% endcall %}

    {% call ui.glass_panel("来源记录", "构成该项目的抽取记录") %}
      {% if detail.records %}
        <div class="data-table-wrap compact-table">
          <table class="data-table">
            <thead>
              <tr>
                <th>文章</th>
                <th>决策</th>
                <th>分数</th>
                <th>状态</th>
                <th>发布时间</th>
              </tr>
            </thead>
            <tbody>
              {% for record in detail.records %}
                <tr>
                  <td><a href="{{ record.article_url }}" target="_blank" rel="noreferrer">{{ record.article_title }}</a></td>
                  <td>{{ record.decision }}</td>
                  <td>{{ record.score or "" }}</td>
                  <td>{{ record.status or "" }}</td>
                  <td>{{ record.published_at or "" }}</td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      {% else %}
        <p class="empty-state">没有来源记录。</p>
      {% endif %}
    {% endcall %}
  </section>
{% endblock %}
```

- [ ] **Step 7: Add project CSS**

Append to `src/market_info/web/static/styles.css`:

```css
.project-filter {
  grid-template-columns: minmax(200px, 1fr) minmax(140px, 180px) minmax(140px, 180px) auto;
}

.timeline-list {
  display: grid;
  gap: 14px;
  margin: 0;
  padding-left: 22px;
}

.timeline-list li {
  padding-left: 8px;
}

.timeline-list strong,
.timeline-list span,
.timeline-list a {
  display: block;
}

.timeline-list span {
  margin: 4px 0;
  color: var(--muted);
  font-size: 13px;
}

.compact-table .data-table {
  min-width: 620px;
}

@media (max-width: 760px) {
  .project-filter {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 8: Add route smoke tests**

Append to `tests/test_web_app.py`:

```python
def test_projects_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/projects")

    assert response.status_code == 200
    assert "项目台账" in response.text
```

- [ ] **Step 9: Run Task 8 tests**

Run:

```powershell
python -m pytest tests/test_web_project_service.py tests/test_web_app.py -v
python -m pytest -q
```

Expected:

```text
All selected tests pass
Full test suite passes
```

- [ ] **Step 10: Manual acceptance for Task 8**

Run:

```powershell
market-info web --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/projects
```

Expected:

```text
The project ledger page renders, filter controls fit on desktop and mobile, project links open detail pages, and detail pages show timeline plus source records without article body text or embeddings.
```

**Prompt for Task 8 execution:**

```text
Implement Task 8 from docs/superpowers/plans/2026-07-02-market-info-ops-task7-9-plan.md. Use TDD exactly as written. Add project ledger and project detail/timeline services, routes, templates, nav entry, and CSS. Do not expose semantic_text, embeddings, or article full text. Run `python -m pytest tests/test_web_project_service.py tests/test_web_app.py -v`, then `python -m pytest -q`, then smoke-test `/projects`. Report changed files and verification output.
```

---

## Task 9: Quality Evaluation and Safe Settings Center

**Files:**
- Create: `src/market_info/web/services/quality_service.py`
- Create: `src/market_info/web/routes/quality.py`
- Create: `src/market_info/web/templates/quality.html`
- Modify: `src/market_info/web/app.py`
- Modify: `src/market_info/web/templates/base.html`
- Modify: `src/market_info/web/static/styles.css`
- Test: `tests/test_web_quality_service.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `market_info.evaluation.exporter.export_golden_template(session, output_dir, limit)`.
- Consumes: `market_info.evaluation.core.evaluate_golden(labels_path, report_path=report_path)`.
- Consumes: `market_info.config.Settings`.
- Produces: `GoldenAssetSummary` dataclass with fields `base_dir`, `labels_path`, `labels_exists`, `article_body_count`, `report_path`, `report_exists`.
- Produces: `EvaluationMetricSummary` dataclass with fields `project_precision`, `project_recall`, `field_accuracy`, `status_accuracy`, `investment_accuracy`, `dedupe_accuracy`, `false_merge_count`, `missed_merge_count`.
- Produces: `ConfigHealthItem` dataclass with fields `name`, `status`, `detail`.
- Produces: `QualityOverview` dataclass with fields `golden_assets`, `evaluation`, `config_items`.
- Produces: `build_quality_overview(base_dir: Path | None = None, report_path: Path | None = None) -> QualityOverview`.
- Produces: `load_evaluation_report(report_path: Path) -> EvaluationMetricSummary | None`.
- Produces: `get_safe_settings_snapshot(settings: Settings | None = None) -> list[ConfigHealthItem]`.
- Produces: `export_golden_for_web(output_dir: Path, limit: int) -> Path`.
- Produces: `evaluate_golden_for_web(labels_path: Path, report_path: Path) -> Path`.
- Produces routes `GET /quality`, `POST /quality/export-golden`, `POST /quality/eval-golden`.

- [ ] **Step 1: Write failing quality service tests**

Create `tests/test_web_quality_service.py`:

```python
import json
from contextlib import contextmanager
from pathlib import Path

from pydantic import SecretStr

from market_info.config import Settings
from market_info.web.services import quality_service


def test_load_evaluation_report_reads_metrics(tmp_path: Path) -> None:
    report_path = tmp_path / "evaluation_report.json"
    report_path.write_text(
        json.dumps(
            {
                "extraction": {
                    "project_precision": 0.75,
                    "project_recall": 0.6,
                    "field_accuracy": 0.8,
                    "status_accuracy": 0.9,
                    "investment_accuracy": 1.0,
                    "hallucination_count": 2,
                    "missed_count": 1,
                },
                "dedupe": {
                    "dedupe_accuracy": 0.5,
                    "false_merge_count": 1,
                    "missed_merge_count": 2,
                    "status_change_accuracy": 0.75,
                },
                "error_samples": {},
            }
        ),
        encoding="utf-8",
    )

    summary = quality_service.load_evaluation_report(report_path)

    assert summary is not None
    assert summary.project_precision == 0.75
    assert summary.dedupe_accuracy == 0.5
    assert summary.false_merge_count == 1


def test_build_quality_overview_counts_assets(tmp_path: Path) -> None:
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    (tmp_path / "golden_labels.xlsx").write_bytes(b"xlsx")
    (articles_dir / "a.txt").write_text("body", encoding="utf-8")

    overview = quality_service.build_quality_overview(base_dir=tmp_path)

    assert overview.golden_assets.labels_exists is True
    assert overview.golden_assets.article_body_count == 1
    assert overview.evaluation is None


def test_get_safe_settings_snapshot_masks_secret_values(monkeypatch) -> None:
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        WECHAT_EXPORTER_AUTH_KEY="wechat-secret",
        AI_API_KEY="ai-secret",
        SMTP_PASSWORD="smtp-secret",
        WECOM_WEBHOOK_URL="https://example.test/hook",
        MAIL_TO="ops@example.test",
    )

    rows = quality_service.get_safe_settings_snapshot(settings)
    rendered = " ".join(f"{row.name}:{row.detail}" for row in rows)

    assert "wechat-secret" not in rendered
    assert "ai-secret" not in rendered
    assert "smtp-secret" not in rendered
    assert "https://example.test/hook" not in rendered
    assert "configured" in rendered


def test_export_golden_for_web_uses_database_session(monkeypatch, tmp_path: Path) -> None:
    calls = []

    class DummySession:
        pass

    @contextmanager
    def fake_get_session():
        yield DummySession()

    def fake_export(session, output_dir, limit):
        calls.append((session, output_dir, limit))
        path = output_dir / "golden_labels.xlsx"
        output_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"xlsx")
        return path

    monkeypatch.setattr(quality_service, "get_session", fake_get_session)
    monkeypatch.setattr(quality_service, "export_golden_template", fake_export)

    path = quality_service.export_golden_for_web(tmp_path, 7)

    assert path == tmp_path / "golden_labels.xlsx"
    assert calls[0][1] == tmp_path
    assert calls[0][2] == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_web_quality_service.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'market_info.web.services.quality_service'
```

- [ ] **Step 3: Implement quality service**

Create `src/market_info/web/services/quality_service.py` with dataclasses named in the interface section.

Implementation rules:

- Default base directory is `Path("data/golden_articles")`.
- Default report path is `base_dir / "evaluation_report.json"`.
- `load_evaluation_report()` returns `None` when the JSON file does not exist.
- `load_evaluation_report()` reads only aggregate metrics and ignores `error_samples` detail for the MVP.
- `get_safe_settings_snapshot()` returns rows for `DATABASE_URL`, `WECHAT_EXPORTER_BASE_URL`, `WECHAT_EXPORTER_AUTH_KEY`, `AI_BASE_URL`, `AI_API_KEY`, `AI_EXTRACTION_MODEL`, `AI_EMBEDDING_MODEL`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_TO`, `WECOM_WEBHOOK_URL`, `EXPORT_DIR`.
- Secret-like values use detail `"configured"` when present and `"missing"` when empty; never include raw secret strings.
- Non-secret URL/path/user values may show host/path-level detail, but `DATABASE_URL` must show only `"configured"` or `"missing"`.
- `export_golden_for_web()` opens `get_session()`, calls `export_golden_template(session, output_dir, limit)`, and returns the generated path.
- `evaluate_golden_for_web()` calls `evaluate_golden(labels_path, report_path=report_path)` and returns `report_path`.

- [ ] **Step 4: Add quality routes**

Create `src/market_info/web/routes/quality.py`:

```python
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from market_info.web.services.job_runner import job_runner
from market_info.web.services.quality_service import (
    build_quality_overview,
    evaluate_golden_for_web,
    export_golden_for_web,
)
from market_info.web.templating import templates


router = APIRouter(prefix="/quality")


@router.get("")
def quality_page(request: Request):
    return templates.TemplateResponse(
        name="quality.html",
        request=request,
        context={
            "request": request,
            "active_nav": "quality",
            "page_title": "质量与设置",
            "overview": build_quality_overview(),
            "jobs": job_runner.list_jobs(),
        },
    )


@router.post("/export-golden")
def start_export_golden(limit: int = Form(20), output_dir: str = Form("data/golden_articles")):
    job_runner.start_job(
        "export_golden",
        export_golden_for_web,
        {"output_dir": Path(output_dir), "limit": limit},
    )
    return RedirectResponse("/quality", status_code=303)


@router.post("/eval-golden")
def start_eval_golden(
    labels_path: str = Form("data/golden_articles/golden_labels.xlsx"),
    report_path: str = Form("data/golden_articles/evaluation_report.json"),
):
    job_runner.start_job(
        "eval_golden",
        evaluate_golden_for_web,
        {"labels_path": Path(labels_path), "report_path": Path(report_path)},
    )
    return RedirectResponse("/quality", status_code=303)
```

- [ ] **Step 5: Register route and navigation**

Modify `src/market_info/web/app.py`:

```python
from market_info.web.routes import articles, dashboard, jobs, projects, quality, reports, reviews
```

Inside `create_app()` after projects:

```python
    app.include_router(quality.router)
```

Modify `src/market_info/web/templates/base.html` navigation:

```html
<a class="nav-link {% if active_nav == 'quality' %}is-active{% endif %}" href="/quality">质量与设置</a>
```

- [ ] **Step 6: Add quality template**

Create `src/market_info/web/templates/quality.html`:

```html
{% extends "base.html" %}
{% import "components.html" as ui %}

{% block content %}
  <section class="metric-grid" aria-label="质量指标">
    {% if overview.evaluation %}
      {{ ui.metric_tile("项目精确率", "%.0f%%"|format(overview.evaluation.project_precision * 100), "precision", "blue") }}
      {{ ui.metric_tile("项目召回率", "%.0f%%"|format(overview.evaluation.project_recall * 100), "recall", "blue") }}
      {{ ui.metric_tile("字段准确率", "%.0f%%"|format(overview.evaluation.field_accuracy * 100), "field accuracy", "neutral") }}
      {{ ui.metric_tile("去重准确率", "%.0f%%"|format(overview.evaluation.dedupe_accuracy * 100), "dedupe", "amber") }}
    {% else %}
      {{ ui.metric_tile("项目精确率", "-", "未生成评估报告", "neutral") }}
      {{ ui.metric_tile("项目召回率", "-", "未生成评估报告", "neutral") }}
      {{ ui.metric_tile("字段准确率", "-", "未生成评估报告", "neutral") }}
      {{ ui.metric_tile("去重准确率", "-", "未生成评估报告", "neutral") }}
    {% endif %}
  </section>

  <section class="detail-grid">
    {% call ui.glass_panel("黄金测试集", "导出待标注样本，或运行已有 golden_labels.xlsx 的评估") %}
      <dl class="detail-list">
        <dt>标签文件</dt><dd>{{ overview.golden_assets.labels_path }}</dd>
        <dt>标签状态</dt><dd>{{ "已存在" if overview.golden_assets.labels_exists else "未生成" }}</dd>
        <dt>正文样本</dt><dd>{{ overview.golden_assets.article_body_count }}</dd>
        <dt>评估报告</dt><dd>{{ "已存在" if overview.golden_assets.report_exists else "未生成" }}</dd>
      </dl>
      <form class="quality-action" method="post" action="/quality/export-golden">
        <label>
          导出数量
          <input class="field-input" name="limit" type="number" min="1" value="20">
        </label>
        <input type="hidden" name="output_dir" value="{{ overview.golden_assets.base_dir }}">
        {{ ui.command_button("导出黄金测试集", None, "secondary", "导出中") }}
      </form>
      <form class="quality-action" method="post" action="/quality/eval-golden">
        <input type="hidden" name="labels_path" value="{{ overview.golden_assets.labels_path }}">
        <input type="hidden" name="report_path" value="{{ overview.golden_assets.report_path }}">
        {{ ui.command_button("运行质量评估", None, "primary", "评估中") }}
      </form>
    {% endcall %}

    {% call ui.glass_panel("安全配置快照", "只显示是否配置，不显示密钥和密码") %}
      <div class="settings-grid">
        {% for item in overview.config_items %}
          <article class="setting-row">
            <strong>{{ item.name }}</strong>
            {{ ui.status_pill(item.status, "ok" if item.status == "configured" else "amber") }}
            <span>{{ item.detail }}</span>
          </article>
        {% endfor %}
      </div>
    {% endcall %}
  </section>
{% endblock %}
```

- [ ] **Step 7: Add quality CSS**

Append to `src/market_info/web/static/styles.css`:

```css
.quality-action {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.quality-action label {
  color: var(--muted);
  font-size: 13px;
  font-weight: 650;
}

.settings-grid {
  display: grid;
  gap: 10px;
}

.setting-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) auto minmax(120px, 0.8fr);
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
}

.setting-row span {
  color: var(--muted);
  overflow-wrap: anywhere;
}

@media (max-width: 760px) {
  .setting-row {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 8: Add route smoke tests**

Append to `tests/test_web_app.py`:

```python
def test_quality_page_renders() -> None:
    client = TestClient(create_app())

    response = client.get("/quality")

    assert response.status_code == 200
    assert "质量与设置" in response.text
    assert "安全配置快照" in response.text
```

- [ ] **Step 9: Run Task 9 tests**

Run:

```powershell
python -m pytest tests/test_web_quality_service.py tests/test_web_app.py -v
python -m pytest -q
```

Expected:

```text
All selected tests pass
Full test suite passes
```

- [ ] **Step 10: Manual acceptance for Task 9**

Run:

```powershell
market-info web --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/quality
```

Expected:

```text
The quality page renders in the liquid-glass shell, shows aggregate evaluation metrics when a report exists, starts golden export/eval jobs through POST, and never displays secret values.
```

**Prompt for Task 9 execution:**

```text
Implement Task 9 from docs/superpowers/plans/2026-07-02-market-info-ops-task7-9-plan.md. Use TDD exactly as written. Add the quality evaluation and safe settings center with service functions, route, template, nav entry, and CSS. Reuse export_golden_template, evaluate_golden, Settings, and job_runner. Never render raw secrets, webhook URLs, article body text, or embeddings. Run `python -m pytest tests/test_web_quality_service.py tests/test_web_app.py -v`, then `python -m pytest -q`, then smoke-test `/quality`. Report changed files and verification output.
```

---

## Final Acceptance for Task 7-9

Run:

```powershell
python -m pytest tests/test_web_review_service.py tests/test_web_project_service.py tests/test_web_quality_service.py tests/test_web_app.py -v
python -m pytest -q
market-info web --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/reviews
http://127.0.0.1:8080/projects
http://127.0.0.1:8080/quality
```

Expected:

```text
All pages render in the existing white liquid-glass shell, all write actions use POST and redirect, sensitive fields are masked, and the full pytest suite passes.
```

## Self-Review Checklist

- Spec coverage: Task 7 resolves review records, Task 8 browses project ledger/timeline, Task 9 covers golden evaluation and masked settings.
- Scope control: No migrations, no SPA, no authentication system, no persisted job table, no article body rendering.
- Interface consistency: Every route calls a service function defined in this plan; every dataclass used by templates is defined before use.
- Security coverage: Secrets, webhook URLs, embeddings, semantic text, and article full text are excluded from UI dataclasses.
- Visual coverage: New pages reuse existing liquid-glass tokens and add only dense operational layout classes.
- Test coverage: Each new service has a focused test file; route smoke tests extend `tests/test_web_app.py`; full acceptance uses `python -m pytest -q`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-02-market-info-ops-task7-9-plan.md`.

Recommended execution approach:

1. Subagent-Driven - dispatch a fresh worker for Task 7, review, then continue Task 8 and Task 9.
2. Inline Execution - execute each task in this session with review checkpoints after every task.

Suggested first execution prompt:

```text
Start with Task 7 from docs/superpowers/plans/2026-07-02-market-info-ops-task7-9-plan.md. Use TDD, keep changes scoped to Task 7, and stop after selected tests plus full pytest pass so the result can be reviewed before Task 8.
```
