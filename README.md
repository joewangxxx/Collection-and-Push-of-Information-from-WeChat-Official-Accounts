# 微信公众号市场项目信息自动收集与推送系统

本项目用于自动收集微信公众号中的市场项目信息，使用 AI 抽取结构化字段，识别重复项目和状态变化，生成 Excel 周报并通过邮件推送给业务团队。它的目标是减少市场和销售团队在项目信息搜集、整理、去重、初筛上的重复劳动，让业务团队更快发现潜在商机。

## 致谢

感谢 [wechat-article-exporter](https://github.com/wechat-article/wechat-article-exporter) 提供微信公众号文章导出能力和实现思路。

## 1. 项目背景

销售团队需要持续跟踪新建项目动态，例如投资额、地点、建设主体、产业方向和项目状态。这些信息分散在微信公众号文章中，人工阅读和整理容易漏看、重复记录，也不容易及时发现项目状态变化。

系统链路：

```text
公众号文章 -> 正文抓取 -> AI 抽取 -> 数据库存储 -> 去重匹配 -> Excel 报告 -> 邮件推送
```

## 2. 当前能力

当前版本支持：

- 抓取指定微信公众号文章。
- 下载文章标题、发布时间、链接和正文。
- 使用 AI 抽取项目字段。
- 对长文进行项目相关段落预处理。
- 支持 AI 抽取与 embedding 有限并行处理。
- 使用 PostgreSQL + pgvector 存储数据并检索相似项目。
- 使用规则评分 + 向量相似度识别重复项目。
- 识别项目状态变化。
- 生成 Excel 周报。
- 通过邮件发送运行摘要和 Excel 附件。
- 记录并处理 pending / failed 文章。
- 使用 pytest / CodeRabbit 做质量检查。

当前默认不做：

- 不抓取阅读量。
- 不抓取评论。
- 不默认启用企业微信机器人。
- 不提交真实配置、文章正文和运行产物。

## 3. 系统架构

```text
wechat-article-exporter
        |
        v
source_articles
        |
        v
AI 文章预处理与项目抽取
        |
        v
project_records
        |
        v
规则评分 + pgvector 向量相似度
        |
        v
projects / project_events
        |
        v
Excel 周报
        |
        v
邮件推送
```

主要数据表：

- `source_articles`：原始文章、正文和 AI 处理状态。
- `project_records`：从文章中抽取出的项目记录。
- `projects`：去重后的项目台账。
- `project_events`：项目状态变化事件。
- `push_logs`：推送记录。

## 4. 快速开始

检查本地环境：

```powershell
python --version
docker --version
git --version
```

安装依赖并启动服务：

```powershell
python -m pip install -e ".[dev]"
docker compose up -d
alembic upgrade head
```

检查 wechat-exporter 登录并运行周报：

```powershell
market-info check-auth
market-info run-weekly --limit 10
```

## 5. 配置说明

复制配置模板：

```powershell
Copy-Item .env.example .env
```

重点关注以下配置项：

- `DATABASE_URL`
- `WECHAT_EXPORTER_BASE_URL`
- `WECHAT_EXPORTER_AUTH_KEY`
- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_EXTRACTION_MODEL`
- `AI_EMBEDDING_MODEL`
- `AI_CONCURRENCY`
- `AI_EXTRACTION_TIMEOUT_SECONDS`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`
- `EXPORT_DIR`

说明：

- `SMTP_PASSWORD` 通常是邮箱授权码，不是网页登录密码。
- `MAIL_TO` 支持多个收件人，通常用英文逗号分隔。
- `.env` 是本地私密配置，不提交到 Git。

## 6. wechat-exporter 登录

1. 打开 `http://localhost:3000`。
2. 使用微信扫码登录。
3. 进入 API 页面。
4. 复制 auth-key。
5. 写入 `.env` 的 `WECHAT_EXPORTER_AUTH_KEY`。

验证：

```powershell
market-info check-auth
```

有效时输出：

```text
wechat exporter auth valid
```

auth-key 与 exporter 登录状态绑定，登录失效后需要重新扫码并更新 `.env`。云服务器部署时建议通过 SSH 隧道访问 exporter，不要公开暴露 `3000` 端口。

## 7. 公众号配置

创建 `config/accounts.yml`：

```yaml
accounts:
  - name: 光伏前沿
    fakeid: replace_with_fakeid
    enabled: true
```

说明：

- 新增公众号就是追加 `name`、`fakeid`、`enabled`。
- 只有 `enabled: true` 的公众号会被抓取。
- `config/accounts.yml` 是本地私密配置，不提交到 Git。
- fakeid 可通过 wechat-exporter 搜索公众号获取。

## 8. 常用命令

```powershell
market-info --help
```

查看全部 CLI 命令。

```powershell
market-info check-auth
```

检查 wechat-exporter auth-key 是否有效。

```powershell
market-info ingest --limit 10
```

只抓取文章并入库，不执行 AI 抽取、Excel 或邮件。

```powershell
market-info pending-status
```

查看文章 AI 处理状态统计。

```powershell
market-info process-pending --limit 10
```

分批处理历史 pending 或可重试 failed 文章。

```powershell
market-info retry-failed --article-ids 12,18
```

定向重试指定失败文章。

```powershell
market-info send-report --excel-path exports/sample.xlsx
```

发送已有 Excel 报表附件。

```powershell
market-info run-weekly --limit 10
```

执行完整周报流程：抓取文章、AI 抽取、去重入库、生成 Excel 并发送邮件。

```powershell
market-info export-golden --output-dir data/golden_articles_v1 --limit 30
```

导出黄金测试集标注模板。

```powershell
market-info eval-golden --labels data/golden_articles_v1/golden_labels.xlsx
```

使用人工标注结果评估 AI 抽取和去重效果。

## 9. Excel 与邮件输出

Excel 主表面向销售和市场团队，只展示业务字段，例如发布日期、公众号名称、文章标题、文章链接、项目名称、地点、企业名称、投资额、产业、领域、市场、状态等。

主表不展示内部字段：

- 抽取置信度
- 去重决策
- 去重分数

主表排序规则：

```text
公众号名称升序 -> 发布时间降序 -> 记录 ID 升序
```

邮件正文包含运行摘要，Excel 作为附件发送。邮件模块支持多个收件人和抄送，并已处理 UTF-8 中文编码，避免中文标题、正文或附件名显示为 `???`。

## 10. 数据安全

不要提交以下文件或目录：

- `.env`
- `.env.*`
- `config/accounts.yml`
- `data/`
- `exports/`
- `.data/`
- 数据库卷
- wechat-exporter 数据卷

不要在日志、截图、聊天记录或提交记录中公开：

- `SMTP_PASSWORD`
- `AI_API_KEY`
- `WECHAT_EXPORTER_AUTH_KEY`
- webhook
- 邮箱授权码

提交前建议检查：

```powershell
git status --short --ignored
git diff
```
