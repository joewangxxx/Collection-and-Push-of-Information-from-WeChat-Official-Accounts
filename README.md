# 微信公众号市场项目信息自动收集与推送系统

本项目用于自动收集微信公众号中的市场项目信息，使用 AI 抽取结构化字段，通过规则去重与向量相似度识别同一项目及状态变化，最终生成 Excel 周报并通过邮件推送给业务团队。项目目标是减少市场和销售团队在项目信息搜集、整理、去重、初筛上的重复劳动，让销售更快发现潜在商机。

本文档同时作为本地验证手册、运行维护手册和业务验收指南。文档不包含真实密钥、授权码或本地运行产物。

## 1. 项目背景

销售团队需要持续跟踪新建项目动态，例如投资额、项目地点、建设主体、产业方向和项目状态。此类信息大量分散在微信公众号文章中，人工阅读和整理效率低，且容易出现漏看、重复记录、状态变化未及时发现等问题。

本系统把这一流程拆成可自动运行的链路：

```text
公众号文章 -> 正文抓取 -> AI 抽取 -> 数据库存储 -> 去重匹配 -> Excel 报告 -> 邮件推送
```

系统的核心不是简单保存文章，而是从文章中识别有业务价值的项目线索，并持续维护项目台账。

## 2. 当前能力

当前版本已经支持：

- 抓取指定微信公众号文章列表。
- 下载文章标题、发布时间、文章链接和正文。
- 使用 AI 从正文中抽取市场项目字段。
- 对长文进行预处理，减少无关内容对 AI 抽取的干扰。
- 支持 AI 抽取并行处理，通过 `AI_CONCURRENCY` 控制并发数。
- 使用 PostgreSQL 保存文章、项目记录、项目台账和状态事件。
- 使用 pgvector 保存项目语义向量并做相似度检索。
- 使用规则评分 + 向量相似度识别重复项目。
- 识别同一项目在备案、环评、招标、开工、投产等阶段的状态变化。
- 生成 Excel 周报。
- 通过邮件正文摘要 + Excel 附件推送。
- 记录 pending / failed 文章状态，并支持补处理和失败重试。
- 建立黄金测试集，用人工标注结果评估 AI 抽取和去重效果。
- 使用 pytest 和 CodeRabbit 辅助质量检查。

当前默认不做：

- 不抓取阅读量。
- 不抓取评论。
- 不默认启用企业微信机器人推送。
- 不把真实 `.env`、公众号配置、运行产物或文章正文提交到 Git。

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

- `source_articles`：原始文章及处理状态。
- `project_records`：从文章中抽取出的项目记录。
- `projects`：去重后的项目台账。
- `project_events`：项目状态变化事件。
- `push_logs`：推送记录。

## 4. 技术栈

- Python 3.11+
- Typer CLI
- SQLAlchemy
- Alembic
- PostgreSQL
- pgvector
- Docker Compose
- wechat-article-exporter
- OpenAI-compatible AI API
- openpyxl
- pytest

## 5. 本地环境准备

请先准备：

- Windows 电脑。
- Docker Desktop。
- Python 3.11 或更高版本。
- Git。
- 可用的 SMTP 邮箱授权码。
- 可用的 OpenAI-compatible AI 服务，例如阿里云百炼兼容模式。
- 可扫码登录的微信账号，用于 wechat-exporter。

检查命令：

```powershell
python --version
docker --version
git --version
```

## 6. 安装与启动

克隆仓库：

```powershell
git clone https://github.com/joewangxxx/Collection-and-Push-of-Information-from-WeChat-Official-Accounts.git
cd Collection-and-Push-of-Information-from-WeChat-Official-Accounts
```

安装依赖：

```powershell
python -m pip install -e ".[dev]"
```

启动 Docker 服务：

```powershell
docker compose up -d
docker compose ps
```

会启动两个本地服务：

- `market-info-postgres`：PostgreSQL + pgvector，端口 `5432`。
- `wechat-article-exporter`：微信公众号文章导出服务，端口 `3000`。

如果出现 `no configuration file provided`，通常说明当前目录不是项目根目录。请切换到包含 `docker-compose.yml` 的目录后重试。

## 7. 配置说明

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`：

```dotenv
DATABASE_URL=postgresql+psycopg://market_info:market_info@localhost:5432/market_info
WECHAT_EXPORTER_BASE_URL=http://localhost:3000
WECHAT_EXPORTER_AUTH_KEY=
ACCOUNTS_CONFIG_PATH=config/accounts.yml
AI_BASE_URL=
AI_API_KEY=
AI_EXTRACTION_MODEL=
AI_EMBEDDING_MODEL=
EMBEDDING_DIM=1536
AI_CONCURRENCY=3
AI_EXTRACTION_TIMEOUT_SECONDS=180
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

配置说明：

- `WECHAT_EXPORTER_AUTH_KEY` 来自 wechat-exporter 的 API 页面。
- `AI_BASE_URL` 使用兼容 OpenAI API 的模型服务地址。
- `AI_CONCURRENCY` 控制 AI 抽取和 embedding 并发数，本地建议先用 `2` 到 `3`。
- `AI_EXTRACTION_TIMEOUT_SECONDS` 控制单篇文章 AI 抽取超时时间，默认 `180` 秒。
- `SMTP_PASSWORD` 通常是邮箱授权码，不是网页登录密码。
- `MAIL_TO` 支持多个收件人，通常用逗号分隔。
- `MAIL_CC` 可选。
- `WECOM_WEBHOOK_URL` 当前为预留配置，默认流程不依赖企业微信。
- `.env` 是本地私密配置，不允许提交到 Git。

## 8. wechat-exporter 登录与 auth-key

首次使用或登录失效时：

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

失效时需要重新扫码，并更新 `.env` 中的 `WECHAT_EXPORTER_AUTH_KEY`。auth-key 与 wechat-exporter 登录状态绑定，登录状态失效后 auth-key 也会失效。

部署到云服务器时，建议使用 SSH 隧道访问云端 wechat-exporter，再在本地浏览器扫码：

```powershell
ssh -L 3000:127.0.0.1:3000 root@服务器IP
```

然后在本地打开 `http://localhost:3000`，实际访问的是云服务器上的 exporter。不要直接把 `3000` 端口暴露到公网。

## 9. 数据库初始化

首次运行或迁移更新后执行：

```powershell
alembic upgrade head
```

迁移会创建业务表，并启用 pgvector 扩展。

## 10. 公众号配置

创建 `config/accounts.yml`：

```yaml
accounts:
  - name: 光伏前沿
    fakeid: replace_with_fakeid
    enabled: true
```

说明：

- `config/accounts.yml` 是本地私密配置，不提交到 Git。
- 只有 `enabled: true` 的公众号会被抓取。
- fakeid 可通过 wechat-exporter 或公众号检索流程获取。

## 11. 常用命令

查看 CLI：

```powershell
market-info --help
```

当前命令包括：

```text
check-auth
ingest
send-report
pending-status
process-pending
retry-failed
export-golden
eval-golden
run-weekly
```

检查 wechat-exporter 登录：

```powershell
market-info check-auth
```

只抓文章入库，不做 AI 抽取：

```powershell
market-info ingest --limit 20
```

查看待处理和失败文章状态：

```powershell
market-info pending-status
```

补处理历史 pending / retryable failed 文章：

```powershell
market-info process-pending --limit 20
```

重试指定失败文章：

```powershell
market-info retry-failed --article-ids 12,18,25
```

如需重试 exhausted 文章：

```powershell
market-info retry-failed --article-ids 12 --include-exhausted
```

发送已有 Excel：

```powershell
market-info send-report --excel-path exports/sample.xlsx
```

完整周报流程：

```powershell
market-info run-weekly --limit 20
```

`run-weekly` 会依次执行：

```text
检查 auth -> 抓取文章 -> 下载正文 -> AI 抽取 -> 生成 embedding
-> 去重匹配 -> 写入项目台账 -> 生成 Excel -> 邮件推送
```

## 12. 完整本地验证流程

从零开始建议按以下顺序执行：

```powershell
docker compose up -d
python -m pip install -e ".[dev]"
alembic upgrade head
market-info check-auth
market-info run-weekly --limit 20
```

完成后检查：

- `exports/` 下是否生成新的 `.xlsx` 文件。
- 邮箱是否收到周报邮件。
- Excel 是否能正常打开。
- Excel 是否包含公众号名称、文章标题和文章链接。
- `market-info pending-status` 中 pending 是否可控。

## 13. Excel 输出说明

Excel 周报用于销售和市场团队阅读，主表只展示业务字段，不展示内部调试字段。

主表字段包括：

- 发布日期
- 公众号名称
- 文章标题
- 文章链接
- 项目名称
- 项目信息
- 省份
- 1级地级市
- 详细地址
- 企业名称
- 项目投资额（亿）
- 产业
- 领域
- 市场
- 状态
- 状态变化标注
- 是否新增项目
- 是否状态更新

主表不展示：

- 抽取置信度
- 去重决策
- 去重分数

排序规则：

```text
公众号名称升序 -> 发布时间降序 -> 记录 ID 升序
```

工作簿通常包含：

- 本周新增与更新
- 项目全量台账
- 疑似重复待复核
- 运行摘要

## 14. 邮件推送说明

当前默认推送方式为邮件：

- 邮件正文包含运行摘要。
- Excel 周报作为附件发送。
- 支持多个收件人。
- 支持可选抄送。

邮件正文会包含：

- 新增项目数
- 合并/更新项目数
- 疑似重复待复核数
- 项目台账总数
- 状态变化事件数
- Excel 文件名
- 生成时间

邮件模块已处理 UTF-8 编码，中文标题、正文和附件名不应显示为 `???`。如果仍出现乱码，请确认使用的是项目内的 `send_report_email` 模块，而不是手写的未指定 UTF-8 的邮件脚本。

## 15. 去重与状态变化识别

系统先计算规则评分，再用 pgvector 语义向量相似度补强。

规则评分主要考虑：

- 项目名称
- 企业名称
- 省份和城市
- 详细地址
- 投资额
- 产业和领域

去重结果分为：

- `new`：新项目，创建项目台账。
- `merge`：与已有项目匹配，合并到已有项目。
- `review`：疑似重复但不自动合并，进入人工复核。

如果同一项目被合并时状态发生变化，系统会记录状态事件。例如同一项目从 `环评公示` 变为 `招标`，会在项目事件中留下记录，并在 Excel 中体现状态变化。

## 16. 黄金测试集与人工标注

黄金测试集用于评估 AI 抽取和去重效果。它不是运行周报的必要步骤，但对持续优化 Prompt、模型和去重策略很重要。

导出黄金测试集模板：

```powershell
market-info export-golden --output-dir data/golden_articles_v1 --limit 30
```

输出目录包含：

- `golden_labels.xlsx`
- `articles/` 正文文本目录

`data/` 已加入 `.gitignore`，真实文章正文不会提交到 Git。

标注文件包含三个核心 sheet：

### articles

用于标注文章级判断：

- `is_project_article`：是否为项目文章。
- `expected_project_count`：文章中真实项目数量。
- `notes`：备注。

非项目文章应填写：

```text
is_project_article = FALSE
expected_project_count = 0
```

### expected_projects

用于标注项目级标准答案。一篇文章有几个真实项目，就填写几行。

重要规则：

- 只根据标题和正文标注。
- 正文没有明确写出的字段留空。
- 不要脑补外部信息。
- 投资额统一填写为“亿”的数字，未披露则留空。
- 状态必须尽量映射到系统状态。
- `evidence` 必须填写原文证据句。

系统状态包括：

```text
拟建、备案、环评公示、环评批复、招标、开工、建设中、投产、停缓建、未知
```

### expected_dedupe

用于标注项目去重关系。

同一个真实项目必须使用同一个 `project_group_id`。例如同一项目出现在两篇文章中，第一篇标为：

```text
expected_decision = new
```

后续重复文章标为：

```text
expected_decision = merge
```

如果项目状态发生变化，填写：

```text
expected_status_change = TRUE
```

运行评估：

```powershell
market-info eval-golden --labels data/golden_articles_v1/golden_labels.xlsx
```

评估会输出：

- 项目识别 precision
- 项目识别 recall
- 字段准确率
- 状态准确率
- 投资额准确率
- 幻觉数量
- 漏抽数量
- 去重准确率
- 误合并数量
- 漏合并数量
- 状态变化识别准确率

同时会生成：

```text
evaluation_report.json
```

## 17. 销售团队参与标注流程

建议让销售团队先参与 10 篇小样本标注，不要一开始就标 100 篇。

推荐流程：

1. 技术侧导出黄金测试集和正文。
2. 销售先阅读原文，不先看 AI 抽取结果。
3. 销售判断文章是否包含真实项目。
4. 销售确认项目数量。
5. 销售填写项目名称、企业、地点、投资额、状态等字段。
6. 销售填写证据句。
7. 技术侧再拿 AI 预抽取结果与人工答案对照。
8. 对差异进行讨论，形成统一标注口径。
9. 跑 `market-info eval-golden` 生成评估指标。
10. 根据错误样例优化 Prompt、预处理、字段规则和去重策略。

销售标注时的关键原则：

- 原文没写就留空。
- 不确定就写备注。
- 不把政策、价格、会议、企业新闻强行标成项目。
- 同一真实项目必须使用同一个 `project_group_id`。
- 标注不是为了证明 AI 对，而是为了校准 AI。

## 18. 运行维护

查看处理状态：

```powershell
market-info pending-status
```

如果 pending 数量较多：

```powershell
market-info process-pending --limit 20
```

如果存在 retryable failed：

```powershell
market-info retry-failed --article-ids 文章ID列表
```

如果存在 exhausted failed，需要先判断失败原因，再决定是否使用：

```powershell
market-info retry-failed --article-ids 文章ID列表 --include-exhausted
```

如果 `run-weekly` 时间过长，可以检查：

- 是否有大量历史 pending 文章。
- `AI_CONCURRENCY` 是否过低。
- AI 服务是否响应慢。
- 单篇文章是否过长。
- `AI_EXTRACTION_TIMEOUT_SECONDS` 是否设置过大。

建议每次运行后确认：

- pending 是否清零或保持在可解释范围。
- retryable failed 是否为 0。
- exhausted failed 是否有明确原因。
- 邮件是否成功送达。
- Excel 是否包含本次新增或更新项目。

## 19. 云服务器部署注意事项

本地验证通过后可以迁移到云服务器长期运行。需要迁移或重新配置：

- Docker 环境。
- `.env`。
- `config/accounts.yml`。
- PostgreSQL 数据卷或数据库备份。
- wechat-exporter 登录状态。
- 定时任务。

云服务器上的 wechat-exporter 登录建议使用 SSH 隧道，不建议公开暴露 `3000` 端口。

定时任务可选：

- Windows 任务计划程序。
- Linux cron。
- 云服务器自带计划任务。

Linux cron 示例：

```cron
0 8 * * 1 cd /path/to/project && market-info run-weekly --limit 20 >> logs/weekly.log 2>&1
```

## 20. 常见问题

### docker compose 提示 no configuration file provided

原因：当前目录不是项目根目录。

解决：

```powershell
cd Collection-and-Push-of-Information-from-WeChat-Official-Accounts
docker compose up -d
```

### market-info 找不到

原因：项目未安装，或当前 Python 环境不对。

解决：

```powershell
python -m pip install -e ".[dev]"
market-info --help
```

### pytest 找不到

解决：

```powershell
python -m pip install -e ".[dev]"
python -m pytest -v
```

### auth invalid

原因：wechat-exporter 登录状态失效，或 `.env` 中 auth-key 不是最新。

解决：

1. 打开 `http://localhost:3000`。
2. 重新扫码登录。
3. 复制新的 auth-key。
4. 更新 `.env`。
5. 重新执行 `market-info check-auth`。

### SMTP 失败

请检查：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`
- 邮箱是否开启 SMTP 服务
- `SMTP_PASSWORD` 是否为授权码

### 没有抽取出项目

可能原因：

- 最近文章本身不是项目文章。
- 文章正文为空或抓取失败。
- 项目信息过于模糊。
- AI 返回空项目。

可以先提高抓取数量：

```powershell
market-info run-weekly --limit 30
```

也可以查看 backlog：

```powershell
market-info pending-status
```

### eval-golden 报标注不一致

通常是因为：

- `expected_project_count` 与 `expected_projects` 行数不一致。
- 非项目文章却填写了项目行。
- 项目行中的 `article_id` 不存在于 `articles` sheet。
- Excel 表头被改动。

按错误提示修正后重新运行。

## 21. 安全注意事项

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

确认 diff 中没有真实密钥、真实授权码或不应提交的运行产物。

## 22. 开发与质量检查

运行测试：

```powershell
python -m pytest -v
```

编译检查：

```powershell
python -m compileall src tests scripts
```

如已安装并登录 CodeRabbit CLI，可进行代码审查：

```powershell
wsl -d Ubuntu-24.04 --cd 'C:\Users\29929\Desktop\AI信息自动抓取推送' -- coderabbit review --agent --type uncommitted
```

README 或文档更新通常至少执行：

```powershell
git diff --check
```

代码或逻辑更新应同时执行相关 pytest。
