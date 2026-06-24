# 微信公众号市场项目信息自动收集与推送系统

本 README 是 Windows 本地验证操作手册，也可以作为后续云服务器部署前的检查清单。文档中的密钥、授权码和本地产物都只说明配置方式，不包含真实值。

## 一、项目简介

本项目用于自动收集指定微信公众号中的市场项目信息，并生成可通过邮件发送的 Excel 周报。当前版本已经支持：

- 自动抓取指定微信公众号文章。
- 下载文章标题、发布时间、文章链接和正文。
- 使用 AI 从文章正文中抽取市场项目字段。
- 使用规则评分 + PostgreSQL pgvector 向量相似度进行项目去重。
- 识别项目状态变化，并记录状态事件。
- 生成 Excel 周报。
- 通过邮件发送运行摘要和 Excel 附件。

当前版本说明：

- 不抓取阅读量。
- 不抓取评论。
- 不使用企业微信机器人。
- 当前数据规模较小，数据库使用 PostgreSQL + pgvector。

## 二、已验证的真实测试结果

Task11.5 已使用真实公众号完成端到端本地验证：

- 测试公众号：光伏前沿
- 抓取文章：20 篇
- 抽取项目记录：6 条
- 项目台账：6 个项目
- 状态事件：0 条
- 生成 Excel：`market_info_weekly_20260624_102824.xlsx`
- 邮件发送：成功

对应数据库计数：

- `source_articles`：20
- `project_records`：6
- `projects`：6
- `project_events`：0

生成的 Excel 包含 4 个 Sheet：

- `本周新增与更新`
- `项目全量台账`
- `疑似重复待复核`
- `运行摘要`

Excel 中已验证包含以下关键字段：

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

运行摘要结果：

- 新增项目记录数：6
- 合并项目记录数：0
- 疑似重复待复核数：0
- 项目台账总数：6
- 状态变化事件数：0

注意：`market_info_weekly_20260624_102824.xlsx` 只是本地运行产物示例，不要提交到 Git。`exports/` 目录下的 Excel 都属于运行产物，也不要提交。

## 三、本地环境准备

请先准备以下环境：

- Windows 电脑。
- Docker Desktop。
- Python 3.11 或更高版本。
- Git。
- 可用的 SMTP 邮箱授权码。
- 阿里云百炼或其他兼容 OpenAI API 的模型服务。
- wechat-exporter 登录需要微信扫码。

检查命令：

```powershell
python --version
docker --version
git --version
```

## 四、下载代码与安装依赖

克隆仓库并进入项目根目录：

```powershell
git clone https://github.com/joewangxxx/Collection-and-Push-of-Information-from-WeChat-Official-Accounts.git
cd Collection-and-Push-of-Information-from-WeChat-Official-Accounts
```

安装项目依赖和测试依赖：

```powershell
python -m pip install -e ".[dev]"
```

验证 CLI 是否可用：

```powershell
market-info --help
```

预期能看到以下命令：

- `check-auth`
- `ingest`
- `send-report`
- `run-weekly`

## 五、启动 Docker 服务

在项目根目录执行：

```powershell
docker compose up -d
docker compose ps
```

这会启动两个本地服务：

- PostgreSQL + pgvector
- wechat-article-exporter

如果命令提示 `no configuration file provided`，通常表示当前目录不是项目根目录。请先进入包含 `docker-compose.yml` 的目录。

## 六、配置 .env

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，至少需要配置以下字段：

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
SMTP_HOST=
SMTP_PORT=465
SMTP_USER=
SMTP_PASSWORD=
MAIL_FROM=
MAIL_TO=
EXPORT_DIR=exports
```

说明：

- `SMTP_PASSWORD` 通常是邮箱授权码，不是网页登录密码。
- `MAIL_FROM` 通常与 `SMTP_USER` 相同。
- `.env` 是本地私密配置，不允许提交到 Git。
- 不要在命令行、日志、截图或提交记录中公开 `SMTP_PASSWORD`、`AI_API_KEY`、`WECHAT_EXPORTER_AUTH_KEY`。

## 七、配置微信公众号账号

创建 `config/accounts.yml`：

```yaml
accounts:
  - name: 光伏前沿
    fakeid: MzI1MTExODAzNw==
    enabled: true
```

说明：

- `config/accounts.yml` 是本地私密配置，不提交到 Git。
- 后续可以在 `accounts` 下继续添加多个公众号。
- 只有 `enabled: true` 的公众号会被抓取。

## 八、wechat-exporter 登录与 auth-key

首次使用或登录失效时，需要重新扫码：

1. 打开 `http://localhost:3000`。
2. 使用微信扫码登录。
3. 进入 API 页面。
4. 复制 auth-key。
5. 写入 `.env` 的 `WECHAT_EXPORTER_AUTH_KEY`。

验证 auth-key：

```powershell
market-info check-auth
```

有效时输出：

```text
wechat exporter auth valid
```

失效时输出：

```text
wechat exporter auth invalid; please scan login again
```

auth-key 会随 wechat-exporter 登录状态失效。网站登录失效后，请重新扫码，并更新 `.env` 中的 `WECHAT_EXPORTER_AUTH_KEY`。

## 九、初始化数据库

首次运行、数据库容器重建或迁移文件更新后，需要执行：

```powershell
alembic upgrade head
```

数据库使用 PostgreSQL + pgvector。迁移会创建业务表，并启用 pgvector 扩展。

## 十、常用命令

### 1. 检查 wechat-exporter 登录

```powershell
market-info check-auth
```

用于确认 `.env` 中的 `WECHAT_EXPORTER_AUTH_KEY` 是否仍然有效。

### 2. 只抓文章

```powershell
market-info ingest --limit 5
```

只抓取并入库文章，不执行 AI 抽取，不生成 Excel，不发送邮件。

### 3. 发送已有 Excel

```powershell
market-info send-report --excel-path exports/sample.xlsx
```

用于单独验证邮件正文和 Excel 附件发送能力。请确保指定的 Excel 文件真实存在。

### 4. 完整周报流程

```powershell
market-info run-weekly --limit 20
```

`run-weekly` 会依次执行：

- 检查 auth。
- 抓取公众号文章。
- 下载正文。
- AI 抽取项目。
- 生成 embedding。
- 去重匹配。
- 写入项目台账。
- 记录状态变化事件。
- 生成 Excel。
- 发送邮件。

## 十一、完整本地验证流程

从零开始可以按下面顺序执行：

```powershell
docker compose up -d
alembic upgrade head
market-info check-auth
market-info ingest --limit 5
market-info run-weekly --limit 20
```

完成后检查：

- `exports/` 下是否生成新的 `.xlsx` 文件。
- 邮箱是否收到周报邮件。
- Excel 是否包含 4 个 Sheet。
- `本周新增与更新` 中是否有项目记录。
- Excel 中是否包含公众号名称和文章链接。
- 文章链接是否为 `mp.weixin.qq.com` 链接。

## 十二、Excel 输出说明

Excel 周报包含 4 个 Sheet。

### 1. 本周新增与更新

包含本次新增或合并更新的项目记录，字段包括：

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
- 抽取置信度
- 去重决策
- 去重分数

### 2. 项目全量台账

保存项目级别的最新状态，包括项目名称、企业名称、地区、投资额、产业、领域、市场、当前状态、首次发现时间和最近发现时间。

### 3. 疑似重复待复核

保存系统不确定是否重复的项目。`review` 记录不会自动合并到已有项目，需要人工复核。

### 4. 运行摘要

保存本次运行统计，例如新增项目记录数、合并项目记录数、疑似重复待复核数、项目台账总数和状态变化事件数。

## 十三、邮件说明

邮件发送功能会把运行摘要写入正文，并把 Excel 文件作为附件发送。

邮件正文包含：

- 新增项目数
- 合并/更新项目数
- 疑似重复待复核数
- 项目台账总数
- 状态变化事件数
- Excel 文件名
- 生成时间

当前项目邮件模块已处理中文 UTF-8 编码，邮件标题、正文和附件文件名不应显示为 `???`。

如果 Gmail 或其他邮箱中仍出现中文乱码，请确认使用的是项目内 `send_report_email` 邮件模块，而不是手写的未指定 UTF-8 的 MIME 邮件脚本。

## 十四、去重逻辑说明

系统会先用规则字段进行评分，再使用 pgvector 语义向量相似度进行补强。

规则评分主要考虑：

- 项目名称
- 企业名称
- 省份/城市
- 详细地址
- 投资额
- 产业/领域

综合评分后分为三类：

- `new`：新项目，会创建项目台账。
- `merge`：与已有项目匹配，会合并到已有项目。
- `review`：疑似重复，但系统不自动合并，需要人工复核。

如果合并时发现项目状态发生变化，系统会创建状态事件，并在 Excel 中显示状态变化标注。

## 十五、常见问题

### 1. `docker compose no configuration file provided`

原因：当前命令不是在项目根目录执行。

解决：进入包含 `docker-compose.yml` 的目录后重试。

```powershell
cd Collection-and-Push-of-Information-from-WeChat-Official-Accounts
docker compose up -d
```

### 2. `market-info` 找不到

原因：项目依赖尚未安装，或当前 Python 环境不是安装项目的环境。

解决：

```powershell
python -m pip install -e ".[dev]"
market-info --help
```

### 3. `pytest` 找不到

原因：测试依赖尚未安装。

解决：

```powershell
python -m pip install -e ".[dev]"
python -m pytest -v
```

### 4. `auth invalid`

原因：wechat-exporter 登录状态失效，或 `.env` 中的 auth-key 不是最新值。

解决：

1. 打开 `http://localhost:3000`。
2. 重新扫码登录。
3. 复制新的 auth-key。
4. 更新 `.env` 中的 `WECHAT_EXPORTER_AUTH_KEY`。
5. 重新执行 `market-info check-auth`。

### 5. SMTP 失败

请检查：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`
- QQ 邮箱或其他邮箱是否已开启 SMTP 服务。
- `SMTP_PASSWORD` 是否使用授权码，而不是网页登录密码。

### 6. Gmail 中文显示 `???`

解决：

- 使用项目内邮件模块发送周报。
- 不要使用未指定 UTF-8 编码的手写邮件脚本。
- 确认附件文件名和邮件正文由 `send_report_email` 生成。

### 7. 没有抽取出项目

可能原因是最近文章不是项目公告，或文章中没有明确的市场项目信息。

可以提高抓取数量后重试：

```powershell
market-info run-weekly --limit 30
```

## 十六、安全注意事项

不要提交以下本地文件或目录：

- `.env`
- `config/accounts.yml`
- `exports/`

不要在日志、截图、提交记录或聊天消息中打印：

- `SMTP_PASSWORD`
- `AI_API_KEY`
- `WECHAT_EXPORTER_AUTH_KEY`
- webhook

提交前建议检查：

```powershell
git status --short --ignored
git diff
```

确认 diff 中没有真实 SMTP 密码、真实 AI Key、真实 wechat auth-key 或 webhook。

## 十七、后续云服务器部署说明

本地验证通过后，可以迁移到云服务器运行。迁移时通常需要重新配置或迁移：

- `.env`
- `config/accounts.yml`
- Docker 环境
- PostgreSQL 数据卷或数据库备份
- wechat-exporter 登录状态
- 定时任务

定时任务可以选择：

- Windows 任务计划程序。
- Linux cron。
- 云服务器自带的计划任务能力。

云服务器部署前建议先在本地确认：

- `market-info check-auth` 有效。
- `market-info run-weekly --limit 20` 能完整运行。
- Excel 能正常生成。
- 邮件能正常收到附件。
