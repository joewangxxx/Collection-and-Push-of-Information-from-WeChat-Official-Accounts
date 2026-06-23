# Market Info Local Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-local validation system that collects WeChat public account articles, extracts project information with AI, deduplicates projects using PostgreSQL + pgvector, generates Excel reports, emails the Excel attachment, and sends a WeCom summary.

**Architecture:** The system uses `wechat-article-exporter` as a private WeChat article gateway, PostgreSQL with pgvector as the single source of truth, and a Python application for ingestion, AI extraction, deduplication, reporting, and push notifications. The local Docker Compose setup mirrors the future cloud deployment path.

**Tech Stack:** Python 3.11+, Docker Desktop, PostgreSQL 16 + pgvector, SQLAlchemy, Alembic, Pydantic, httpx, rapidfuzz, pgvector Python integration, pandas, openpyxl, APScheduler, pytest.

## Global Constraints

- Data source is WeChat public account articles through private `wechat-article-exporter`.
- Do not collect read count.
- Do not collect comments.
- Collect only public account name, article title, publication time, article URL, and body text.
- Use PostgreSQL + pgvector from the first implementation version.
- Use rule deduplication plus pgvector similarity; do not use pure vector-only deduplication.
- Send Excel by email attachment.
- Send only summary text to Enterprise WeChat.
- Do not build a complex web admin UI in the local validation version.
- Excel must include `公众号名称` and `文章链接`.

---

## File Structure

Create this project structure:

```text
.
├─ docker-compose.yml
├─ .env.example
├─ README.md
├─ alembic.ini
├─ pyproject.toml
├─ src/
│  └─ market_info/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ db/
│     │  ├─ __init__.py
│     │  ├─ base.py
│     │  ├─ models.py
│     │  └─ session.py
│     ├─ wechat/
│     │  ├─ __init__.py
│     │  └─ exporter_client.py
│     ├─ ingest/
│     │  ├─ __init__.py
│     │  ├─ article_ingestor.py
│     │  └─ url_normalizer.py
│     ├─ ai/
│     │  ├─ __init__.py
│     │  ├─ extractor.py
│     │  ├─ embeddings.py
│     │  └─ schemas.py
│     ├─ dedupe/
│     │  ├─ __init__.py
│     │  ├─ normalizers.py
│     │  ├─ rule_score.py
│     │  ├─ vector_search.py
│     │  └─ matcher.py
│     ├─ reports/
│     │  ├─ __init__.py
│     │  └─ excel_report.py
│     ├─ push/
│     │  ├─ __init__.py
│     │  ├─ email_sender.py
│     │  └─ wecom_sender.py
│     └─ jobs/
│        ├─ __init__.py
│        └─ weekly_job.py
├─ alembic/
│  ├─ env.py
│  └─ versions/
├─ config/
│  └─ accounts.example.yml
├─ exports/
└─ tests/
   ├─ test_config.py
   ├─ test_url_normalizer.py
   ├─ test_rule_score.py
   ├─ test_matcher.py
   ├─ test_excel_report.py
   ├─ test_email_sender.py
   └─ test_wecom_sender.py
```

Responsibilities:

- `config.py`: environment and YAML settings.
- `db/models.py`: SQLAlchemy models for accounts, articles, records, projects, events, push logs.
- `wechat/exporter_client.py`: HTTP wrapper around wechat-article-exporter APIs.
- `ingest/article_ingestor.py`: article list fetching, content fetching, article-level dedupe.
- `ai/extractor.py`: AI project extraction.
- `ai/embeddings.py`: embedding generation.
- `dedupe/rule_score.py`: deterministic rule score.
- `dedupe/vector_search.py`: pgvector candidate retrieval.
- `dedupe/matcher.py`: final merge/new/review decision.
- `reports/excel_report.py`: Excel workbook generation.
- `push/email_sender.py`: SMTP email with Excel attachment.
- `push/wecom_sender.py`: Enterprise WeChat markdown summary.
- `jobs/weekly_job.py`: orchestration of one full run.
- `cli.py`: local command entry points.

## Task 1: Project Scaffold and Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `config/accounts.example.yml`
- Create: `src/market_info/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` Pydantic model with `database_url`, `wechat_exporter_base_url`, `wechat_exporter_auth_key`, SMTP, WeCom, AI, and embedding settings.
- Produces: `load_accounts_config(path: Path) -> list[AccountConfig]`.

- [ ] **Step 1: Define dependencies**

Add dependencies in `pyproject.toml`:

```toml
[project]
name = "market-info-auto-collector"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "alembic>=1.13",
  "apscheduler>=3.10",
  "httpx>=0.27",
  "openpyxl>=3.1",
  "pandas>=2.2",
  "pgvector>=0.3",
  "psycopg[binary]>=3.2",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "python-dotenv>=1.0",
  "pyyaml>=6.0",
  "rapidfuzz>=3.9",
  "sqlalchemy>=2.0",
  "typer>=0.12"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "respx>=0.21",
  "freezegun>=1.5"
]

[project.scripts]
market-info = "market_info.cli:app"
```

- [ ] **Step 2: Add local environment template**

Create `.env.example` with:

```text
DATABASE_URL=postgresql+psycopg://market_info:market_info@localhost:5432/market_info
WECHAT_EXPORTER_BASE_URL=http://localhost:3000
WECHAT_EXPORTER_AUTH_KEY=
ACCOUNTS_CONFIG_PATH=config/accounts.yml
AI_BASE_URL=
AI_API_KEY=
AI_EXTRACTION_MODEL=
AI_EMBEDDING_MODEL=
EMBEDDING_DIM=1536
SMTP_HOST=
SMTP_PORT=465
SMTP_USER=
SMTP_PASSWORD=
MAIL_FROM=
MAIL_TO=
MAIL_CC=
WECOM_WEBHOOK_URL=
EXPORT_DIR=exports
```

- [ ] **Step 3: Add Docker Compose**

Create `docker-compose.yml` with services:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: market-info-postgres
    environment:
      POSTGRES_DB: market_info
      POSTGRES_USER: market_info
      POSTGRES_PASSWORD: market_info
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  wechat-exporter:
    image: ghcr.io/wechat-article/wechat-article-exporter:latest
    container_name: wechat-article-exporter
    environment:
      NODE_TLS_REJECT_UNAUTHORIZED: "0"
      NITRO_KV_DRIVER: fs
      NITRO_KV_BASE: /app/.data/kv
    ports:
      - "3000:3000"
    volumes:
      - wechat_exporter_data:/app/.data

volumes:
  postgres_data:
  wechat_exporter_data:
```

- [ ] **Step 4: Add account config example**

Create `config/accounts.example.yml`:

```yaml
accounts:
  - name: "示例公众号"
    fakeid: "replace_with_fakeid"
    enabled: true
```

- [ ] **Step 5: Implement settings loader**

Create `src/market_info/config.py` with:

```python
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(alias="DATABASE_URL")
    wechat_exporter_base_url: str = Field(alias="WECHAT_EXPORTER_BASE_URL")
    wechat_exporter_auth_key: str = Field(default="", alias="WECHAT_EXPORTER_AUTH_KEY")
    accounts_config_path: str = Field(default="config/accounts.yml", alias="ACCOUNTS_CONFIG_PATH")
    ai_base_url: str = Field(default="", alias="AI_BASE_URL")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_extraction_model: str = Field(default="", alias="AI_EXTRACTION_MODEL")
    ai_embedding_model: str = Field(default="", alias="AI_EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1536, alias="EMBEDDING_DIM")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=465, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    mail_from: str = Field(default="", alias="MAIL_FROM")
    mail_to: str = Field(default="", alias="MAIL_TO")
    mail_cc: str = Field(default="", alias="MAIL_CC")
    wecom_webhook_url: str = Field(default="", alias="WECOM_WEBHOOK_URL")
    export_dir: str = Field(default="exports", alias="EXPORT_DIR")


class AccountConfig(BaseModel):
    name: str
    fakeid: str
    enabled: bool = True


def load_accounts_config(path: Path) -> list[AccountConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [AccountConfig(**item) for item in data.get("accounts", [])]
```

- [ ] **Step 6: Test configuration loading**

Create `tests/test_config.py`:

```python
from pathlib import Path
from market_info.config import load_accounts_config


def test_load_accounts_config(tmp_path: Path):
    config_path = tmp_path / "accounts.yml"
    config_path.write_text(
        """
accounts:
  - name: "测试公众号"
    fakeid: "fakeid123"
    enabled: true
""",
        encoding="utf-8",
    )

    accounts = load_accounts_config(config_path)

    assert len(accounts) == 1
    assert accounts[0].name == "测试公众号"
    assert accounts[0].fakeid == "fakeid123"
    assert accounts[0].enabled is True
```

- [ ] **Step 7: Run tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected:

```text
1 passed
```

## Task 2: Database Schema with pgvector

**Files:**
- Create: `src/market_info/db/base.py`
- Create: `src/market_info/db/models.py`
- Create: `src/market_info/db/session.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial_schema.py`

**Interfaces:**
- Produces: SQLAlchemy models `MpAccount`, `SourceArticle`, `ProjectRecord`, `Project`, `ProjectEvent`, `PushLog`.
- Produces: `get_session() -> Iterator[Session]`.

- [ ] **Step 1: Define models**

Implement models with these required columns:

```text
MpAccount: id, name, fakeid, enabled, last_fetch_at, created_at, updated_at
SourceArticle: id, account_id, account_name, title, article_url, normalized_url, published_at, content_text, content_hash, fetched_at, created_at
ProjectRecord: id, source_article_id, project_id, project_name, project_info, province, city, detailed_address, company_name, investment_amount_yi, industry, field, market, status, confidence, semantic_text, embedding, dedupe_decision, dedupe_score, created_at
Project: id, canonical_project_name, canonical_company_name, province, city, detailed_address, investment_amount_yi, industry, field, market, current_status, first_seen_at, last_seen_at, semantic_text, embedding, created_at, updated_at
ProjectEvent: id, project_id, source_article_id, event_status, previous_status, event_date, change_label, created_at
PushLog: id, run_id, channel, status, recipient, subject, message, artifact_path, error_message, created_at
```

- [ ] **Step 2: Create migration**

The first migration must:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then create all tables. Add:

```text
unique index on source_articles.normalized_url
index on source_articles.content_hash
index on projects.province
index on projects.city
HNSW index on projects.embedding using vector_cosine_ops
```

- [ ] **Step 3: Run migration locally**

Run:

```bash
docker compose up -d postgres
alembic upgrade head
```

Expected:

```text
Running upgrade  -> 0001_initial_schema
```

- [ ] **Step 4: Verify pgvector extension**

Run:

```bash
psql postgresql://market_info:market_info@localhost:5432/market_info -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

Expected:

```text
vector
```

## Task 3: WeChat Exporter Client

**Files:**
- Create: `src/market_info/wechat/exporter_client.py`
- Test: add `tests/test_wechat_exporter_client.py`

**Interfaces:**
- Produces: `WechatArticleSummary(title: str, url: str, published_at: datetime | None)`.
- Produces: `WechatExporterClient.check_auth() -> bool`.
- Produces: `WechatExporterClient.list_articles(fakeid: str, begin: int, size: int) -> list[WechatArticleSummary]`.
- Produces: `WechatExporterClient.download_text(url: str) -> str`.

- [ ] **Step 1: Implement auth and article calls**

Use `httpx.Client` with `X-Auth-Key` header. Endpoints:

```text
GET /api/public/v1/authkey
GET /api/public/v1/article?fakeid={fakeid}&begin={begin}&size={size}
GET /api/public/v1/download?url={encoded_url}&format=text
```

- [ ] **Step 2: Normalize exporter responses**

For article list responses, map exporter article fields to:

```python
WechatArticleSummary(
    title=raw_title,
    url=raw_link,
    published_at=parsed_datetime_or_none,
)
```

- [ ] **Step 3: Test with mocked HTTP**

Use `respx` to test:

```python
def test_check_auth_success(respx_mock):
    respx_mock.get("http://localhost:3000/api/public/v1/authkey").respond(
        json={"code": 0, "data": "abc"}
    )
    client = WechatExporterClient("http://localhost:3000", "abc")
    assert client.check_auth() is True
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_wechat_exporter_client.py -v
```

Expected:

```text
all tests passed
```

## Task 4: Article Ingestion and Article-Level Deduplication

**Files:**
- Create: `src/market_info/ingest/url_normalizer.py`
- Create: `src/market_info/ingest/article_ingestor.py`
- Test: `tests/test_url_normalizer.py`

**Interfaces:**
- Produces: `normalize_article_url(url: str) -> str`.
- Produces: `hash_content(text: str) -> str`.
- Produces: `ArticleIngestor.ingest_account(account: MpAccount) -> IngestResult`.

- [ ] **Step 1: Implement URL normalization**

Rules:

```text
preserve scheme, host, path
preserve query keys needed by WeChat article identity when present: __biz, mid, idx, sn
remove tracking and session-like query keys
sort query keys
strip URL fragment
```

- [ ] **Step 2: Test URL normalization**

Create:

```python
from market_info.ingest.url_normalizer import normalize_article_url


def test_normalize_article_url_keeps_identity_params():
    url = "https://mp.weixin.qq.com/s?sn=abc&idx=1&mid=2&__biz=biz&utm_source=x#rd"
    normalized = normalize_article_url(url)
    assert normalized == "https://mp.weixin.qq.com/s?__biz=biz&idx=1&mid=2&sn=abc"
```

- [ ] **Step 3: Implement article dedupe**

Before inserting a fetched article:

```text
compute normalized_url
compute sha256 content_hash
if normalized_url exists, skip
if content_hash exists with same account, skip
otherwise insert source_articles
```

- [ ] **Step 4: Run ingestion against one account**

Manual command after Task 10 CLI exists:

```bash
market-info ingest --account "示例公众号" --limit 5
```

Expected:

```text
inserted_articles >= 0
skipped_articles >= 0
```

## Task 5: AI Extraction and Structured Validation

**Files:**
- Create: `src/market_info/ai/schemas.py`
- Create: `src/market_info/ai/extractor.py`
- Test: add `tests/test_extractor_schema.py`

**Interfaces:**
- Produces: `ExtractedProject` Pydantic model.
- Produces: `ProjectExtractor.extract(article_title: str, article_text: str) -> list[ExtractedProject]`.

- [ ] **Step 1: Define extraction schema**

The Pydantic model must include:

```text
project_name: str | None
project_info: str | None
province: str | None
city: str | None
detailed_address: str | None
company_name: str | None
investment_amount_yi: float | None
industry: str | None
field: str | None
market: str | None
status: Literal["拟建", "备案", "环评公示", "环评批复", "招标", "开工", "建设中", "投产", "停缓建", "未知"]
confidence: float
```

- [ ] **Step 2: Implement prompt and JSON parsing**

The prompt must require:

```text
return JSON array only
return [] when no project exists
use null for unknown fields
convert investment amount to 亿元
normalize status to the allowed enum
```

- [ ] **Step 3: Test schema validation**

Create a test that validates:

```python
def test_extracted_project_accepts_known_status():
    project = ExtractedProject(
        project_name="XX项目",
        project_info="建设生产线",
        province="江苏省",
        city="盐城市",
        detailed_address=None,
        company_name="XX有限公司",
        investment_amount_yi=12.5,
        industry="新能源",
        field="电池材料",
        market="工业项目",
        status="环评公示",
        confidence=0.88,
    )
    assert project.status == "环评公示"
```

- [ ] **Step 4: Run schema tests**

Run:

```bash
pytest tests/test_extractor_schema.py -v
```

Expected:

```text
all tests passed
```

## Task 6: Embeddings and pgvector Candidate Search

**Files:**
- Create: `src/market_info/ai/embeddings.py`
- Create: `src/market_info/dedupe/vector_search.py`
- Test: add `tests/test_semantic_text.py`

**Interfaces:**
- Produces: `build_project_semantic_text(project: ExtractedProject) -> str`.
- Produces: `EmbeddingClient.embed(text: str) -> list[float]`.
- Produces: `VectorSearch.find_candidates(embedding: list[float], province: str | None, limit: int = 20) -> list[VectorCandidate]`.

- [ ] **Step 1: Build semantic text**

Use this format:

```text
项目名称：{project_name}
企业名称：{company_name}
地点：{province} {city} {detailed_address}
投资额：{investment_amount_yi}亿元
产业：{industry}
领域：{field}
市场：{market}
状态：{status}
项目信息：{project_info}
```

- [ ] **Step 2: Test semantic text excludes source metadata**

Create:

```python
def test_semantic_text_does_not_include_article_url():
    text = build_project_semantic_text(sample_project)
    assert "mp.weixin.qq.com" not in text
    assert "文章链接" not in text
```

- [ ] **Step 3: Implement pgvector query**

Query:

```sql
SELECT id, 1 - (embedding <=> :embedding) AS vector_similarity
FROM projects
WHERE (:province IS NULL OR province = :province)
ORDER BY embedding <=> :embedding
LIMIT :limit
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_semantic_text.py -v
```

Expected:

```text
all tests passed
```

## Task 7: Rule Scoring and Final Matcher

**Files:**
- Create: `src/market_info/dedupe/normalizers.py`
- Create: `src/market_info/dedupe/rule_score.py`
- Create: `src/market_info/dedupe/matcher.py`
- Test: `tests/test_rule_score.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Produces: `calculate_rule_score(new_record, existing_project) -> RuleScoreBreakdown`.
- Produces: `calculate_final_score(rule_score: float, vector_score: float) -> float`.
- Produces: `MatchDecision(decision: Literal["merge", "review", "new"], final_score: float, project_id: int | None)`.

- [ ] **Step 1: Implement normalization**

Normalize:

```text
project names by removing 公告, 公示, 环评, 批复, 备案, 开工, 建设项目
company names by removing 有限公司, 股份有限公司, 有限责任公司, 集团
addresses by mapping 经开区 to 经济技术开发区
```

- [ ] **Step 2: Implement rule score**

Weights:

```text
project_name: 30
company_name: 25
province_city: 15
detailed_address: 10
investment_amount_yi: 10
industry_field: 10
```

- [ ] **Step 3: Implement final score**

Formula:

```python
final_score = rule_score * 0.65 + vector_score * 0.35
```

Decision:

```text
final_score >= 85: merge
70 <= final_score < 85: review
final_score < 70: new
```

- [ ] **Step 4: Test known merge example**

Use the example from the design document:

```python
def test_matcher_merges_high_rule_and_vector_score():
    rule_score = 89
    vector_score = 91
    final = calculate_final_score(rule_score, vector_score)
    assert round(final, 1) == 89.7
    assert classify_score(final) == "merge"
```

- [ ] **Step 5: Test similar-but-different example**

```python
def test_matcher_reviews_when_vector_high_but_company_differs():
    rule_score = 66
    vector_score = 88
    final = calculate_final_score(rule_score, vector_score)
    assert round(final, 1) == 73.7
    assert classify_score(final) == "review"
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/test_rule_score.py tests/test_matcher.py -v
```

Expected:

```text
all tests passed
```

## Task 8: Project Merge and Status Event Persistence

**Files:**
- Modify: `src/market_info/dedupe/matcher.py`
- Create: `src/market_info/jobs/weekly_job.py`
- Test: add `tests/test_project_merge.py`

**Interfaces:**
- Produces: `apply_match_decision(record: ProjectRecord, decision: MatchDecision) -> Project`.
- Produces: `ProjectEvent` when status changes.

- [ ] **Step 1: Implement new project creation**

When decision is `new`:

```text
insert projects row
set first_seen_at from article published_at
set last_seen_at from article published_at
set current_status from extracted status
link project_records.project_id
```

- [ ] **Step 2: Implement merge without status change**

When decision is `merge` and status equals `projects.current_status`:

```text
link project_records.project_id
update projects.last_seen_at
do not create project_events row
```

- [ ] **Step 3: Implement merge with status change**

When decision is `merge` and status differs:

```text
create project_events row
previous_status = old projects.current_status
event_status = new record status
change_label = "{previous_status} -> {event_status}"
update projects.current_status
update projects.last_seen_at
```

- [ ] **Step 4: Test status transition**

Create:

```python
def test_merge_creates_event_when_status_changes(db_session):
    existing = make_project(current_status="环评公示")
    record = make_project_record(status="开工")
    decision = MatchDecision(decision="merge", final_score=90, project_id=existing.id)

    project = apply_match_decision(db_session, record, decision)

    assert project.current_status == "开工"
    events = db_session.query(ProjectEvent).filter_by(project_id=project.id).all()
    assert len(events) == 1
    assert events[0].change_label == "环评公示 -> 开工"
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_project_merge.py -v
```

Expected:

```text
all tests passed
```

## Task 9: Excel Report Generation

**Files:**
- Create: `src/market_info/reports/excel_report.py`
- Test: `tests/test_excel_report.py`

**Interfaces:**
- Produces: `generate_weekly_excel(run_summary: RunSummary, output_dir: Path) -> Path`.

- [ ] **Step 1: Implement workbook sheets**

Create sheets:

```text
本周新增与更新
项目全量台账
疑似重复待复核
运行摘要
```

- [ ] **Step 2: Implement required columns**

The first sheet must include:

```text
发布日期
公众号名称
文章标题
文章链接
项目名称
项目信息
省份
1级地级市
详细地址
企业名称
项目投资额（亿）
产业
领域
市场
状态
状态变化标注
是否新增项目
是否状态更新
抽取置信度
```

- [ ] **Step 3: Test workbook columns**

Create:

```python
from openpyxl import load_workbook


def test_excel_contains_source_columns(tmp_path):
    path = generate_weekly_excel(sample_run_summary(), tmp_path)
    workbook = load_workbook(path)
    sheet = workbook["本周新增与更新"]
    headers = [cell.value for cell in sheet[1]]
    assert "公众号名称" in headers
    assert "文章链接" in headers
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_excel_report.py -v
```

Expected:

```text
all tests passed
```

## Task 10: Email and Enterprise WeChat Summary Push

**Files:**
- Create: `src/market_info/push/email_sender.py`
- Create: `src/market_info/push/wecom_sender.py`
- Test: `tests/test_email_sender.py`
- Test: `tests/test_wecom_sender.py`

**Interfaces:**
- Produces: `send_email_with_attachment(subject: str, body: str, attachment_path: Path, settings: Settings) -> PushResult`.
- Produces: `send_wecom_markdown_summary(summary: WeeklySummary, settings: Settings) -> PushResult`.

- [ ] **Step 1: Implement SMTP email**

Use `smtplib.SMTP_SSL`. Attach Excel as:

```text
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

- [ ] **Step 2: Implement WeCom markdown**

Payload:

```json
{
  "msgtype": "markdown",
  "markdown": {
    "content": "### 市场项目信息周报\n本周新增项目：32 个\n状态更新项目：8 个\n疑似重复待复核：3 个\n涉及公众号：6 个\nExcel 已发送至市场部邮箱。"
  }
}
```

- [ ] **Step 3: Test WeCom payload**

Create:

```python
def test_wecom_summary_payload_contains_no_file_upload():
    payload = build_wecom_summary_payload(sample_weekly_summary())
    assert payload["msgtype"] == "markdown"
    assert "file" not in payload
    assert "Excel 已发送至市场部邮箱" in payload["markdown"]["content"]
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_email_sender.py tests/test_wecom_sender.py -v
```

Expected:

```text
all tests passed
```

## Task 11: CLI and Weekly Job Orchestration

**Files:**
- Create: `src/market_info/cli.py`
- Modify: `src/market_info/jobs/weekly_job.py`
- Test: add `tests/test_weekly_job.py`

**Interfaces:**
- Produces CLI command `market-info check-auth`.
- Produces CLI command `market-info ingest --limit 20`.
- Produces CLI command `market-info run-weekly`.
- Produces CLI command `market-info send-summary --excel-path exports/sample.xlsx`.

- [ ] **Step 1: Implement `check-auth` command**

Command:

```bash
market-info check-auth
```

Expected behavior:

```text
prints "wechat exporter auth valid" when auth is valid
prints "wechat exporter auth invalid; please scan login again" when invalid
```

- [ ] **Step 2: Implement `ingest` command**

Command:

```bash
market-info ingest --limit 20
```

Expected behavior:

```text
loads enabled accounts
fetches article list
downloads new article text
inserts source_articles
prints inserted and skipped counts
```

- [ ] **Step 3: Implement `run-weekly` command**

Command:

```bash
market-info run-weekly
```

Expected behavior:

```text
check auth
ingest new articles
extract projects
generate embeddings
deduplicate and merge
generate Excel
email Excel
send WeCom summary
write push logs
```

- [ ] **Step 4: Implement `send-summary` command**

Command:

```bash
market-info send-summary --excel-path exports/sample.xlsx
```

Expected behavior:

```text
sends test email with sample attachment
sends WeCom summary
```

- [ ] **Step 5: Run integration-style tests with mocked services**

Run:

```bash
pytest tests/test_weekly_job.py -v
```

Expected:

```text
all tests passed
```

## Task 12: Local Validation Runbook

**Files:**
- Create: `README.md`

**Interfaces:**
- Produces: human-run validation steps for Windows local testing.

- [ ] **Step 1: Document local setup**

README must include:

```text
install Docker Desktop
copy .env.example to .env
copy config/accounts.example.yml to config/accounts.yml
docker compose up -d
open http://localhost:3000
scan login
visit http://localhost:3000/api/public/v1/authkey and copy auth key to .env
run alembic upgrade head
run market-info check-auth
```

- [ ] **Step 2: Document weekly run**

README must include:

```bash
market-info run-weekly
```

Expected outputs:

```text
Excel file under exports/
email sent with Excel attachment
WeCom markdown summary sent
push_logs row created for each push channel
```

- [ ] **Step 3: Document validation criteria**

README must include:

```text
3-5 public accounts can be fetched
duplicate article runs are skipped
AI extraction produces project records
pgvector returns candidate projects
status changes create project_events
Excel contains 公众号名称 and 文章链接
email attachment is received
WeCom summary is received
```

- [ ] **Step 4: Run full local smoke test**

Run:

```bash
docker compose up -d
alembic upgrade head
market-info check-auth
market-info ingest --limit 5
market-info run-weekly
```

Expected:

```text
all commands complete without unhandled exceptions
exports/ contains an .xlsx file
email recipient receives the Excel attachment
WeCom group receives the markdown summary
```

## Self-Review Checklist

- Spec coverage: The plan covers WeChat article collection, source fields, PostgreSQL + pgvector, AI extraction, hybrid deduplication, status events, Excel generation, email attachment, WeCom summary, and local validation.
- Placeholder scan: The plan does not use unresolved placeholder markers.
- Type consistency: Interfaces use consistent names across tasks: `ExtractedProject`, `WechatExporterClient`, `ProjectRecord`, `Project`, `ProjectEvent`, `MatchDecision`, `RunSummary`, `WeeklySummary`, and `PushResult`.
- Scope: The plan is focused on local validation and does not include web admin UI, read/comment collection, Enterprise WeChat file upload, or independent vector database deployment.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-23-market-info-local-validation-plan.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.
