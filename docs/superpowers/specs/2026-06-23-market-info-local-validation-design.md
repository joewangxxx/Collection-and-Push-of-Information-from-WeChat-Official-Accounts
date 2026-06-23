# 市场信息自动收集本地验证版设计文档

## 1. 背景

市场部需要定期收集微信公众号中发布的新建项目信息，包括投资、地点、企业、产业、领域、市场、项目状态等字段，用于识别潜在商机。当前人工收集效率低，信息容易重复，且同一项目在不同阶段会多次出现，需要系统自动识别项目状态变化。

本地验证版的目标是在 Windows 电脑上跑通完整闭环，确认采集、AI 抽取、去重、状态识别、Excel 生成、邮件和企业微信推送都可行。验证通过后，使用同一套 Docker 和数据库架构迁移到云服务器长期运行。

## 2. 已确认需求

### 2.1 数据来源

- 主要来源为微信公众号文章。
- 使用 `wechat-article-exporter` 私有部署作为公众号文章采集网关。
- 不采集阅读量。
- 不采集评论。
- 只采集文章基础内容：
  - 公众号名称
  - 文章标题
  - 发布时间
  - 文章链接
  - 正文

### 2.2 项目字段

AI 抽取后的项目字段包括：

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

其中 `发布日期`、`公众号名称`、`文章标题`、`文章链接` 来自采集元数据，不由 AI 猜测。

### 2.3 推送方式

- Excel 文件通过邮件附件发送。
- 企业微信只推送摘要，不发送 Excel 文件。

### 2.4 数据库与向量能力

- 直接使用 `PostgreSQL + pgvector`。
- 不单独准备 Milvus、Qdrant、Weaviate 等独立向量库。
- 使用规则去重 + pgvector 向量相似度补强。

## 3. 非目标

本地验证版不做以下内容：

- 不做阅读量和评论抓取。
- 不做复杂 Web 管理后台。
- 不做企业微信文件上传。
- 不做多用户权限系统。
- 不做独立向量数据库。
- 不做全网网站采集，先聚焦微信公众号。

## 4. 本地验证架构

```text
Windows 本地电脑
├─ Docker Desktop / WSL2
├─ wechat-article-exporter
│  └─ 公众号登录、公众号搜索、文章列表、正文下载
├─ PostgreSQL + pgvector
│  └─ 文章、项目、状态事件、embedding 向量
├─ market-info-app
│  └─ 调度、采集、AI抽取、去重、Excel、邮件、企业微信摘要
└─ exports/
   └─ 每周生成的 Excel 文件
```

推荐数据库镜像：

```text
pgvector/pgvector:pg16
```

## 5. 核心数据流

```text
定时任务或手动命令启动
 -> 检查 wechat-article-exporter 登录状态
 -> 按公众号配置拉取文章列表
 -> 对新文章下载正文
 -> 文章去重并写入 source_articles
 -> 调用 AI 抽取项目 JSON
 -> 为项目记录生成 embedding
 -> pgvector 检索相似历史项目
 -> 规则分 + 向量分综合判定
 -> 新增项目或合并到已有项目
 -> 记录状态变化事件
 -> 生成 Excel
 -> 邮件发送 Excel 附件
 -> 企业微信发送摘要
 -> 写入 push_logs
```

## 6. 模块设计

### 6.1 wechat-article-exporter 采集网关

职责：

- 负责微信公众号扫码登录。
- 负责搜索公众号并获取 `fakeid`。
- 负责获取公众号文章列表。
- 负责下载文章正文。

本地地址：

```text
http://localhost:3000
```

主程序通过 HTTP API 调用 exporter。登录过期时，主程序停止采集并提示用户重新扫码。

### 6.2 主程序 market-info-app

职责：

- 读取公众号配置。
- 调用 exporter 抓取文章。
- 维护文章去重。
- 调用 AI 抽取结构化项目数据。
- 调用 embedding 模型生成向量。
- 执行规则去重 + 向量相似度匹配。
- 维护项目主档案与状态事件。
- 生成 Excel。
- 发送邮件附件。
- 发送企业微信摘要。

建议使用 Python：

```text
Python 3.11+
SQLAlchemy
Alembic
psycopg
pgvector
Pydantic
httpx
rapidfuzz
pandas
openpyxl
APScheduler
```

## 7. 数据库设计

### 7.1 mp_accounts

保存目标公众号配置。

```text
id
name
fakeid
enabled
last_fetch_at
created_at
updated_at
```

### 7.2 source_articles

保存公众号文章原始内容。

```text
id
account_id
account_name
title
article_url
normalized_url
published_at
content_text
content_hash
fetched_at
created_at
```

唯一约束：

```text
normalized_url 唯一
content_hash 可用于辅助去重
```

### 7.3 project_records

保存每次 AI 从文章中抽取出的原始项目记录。

```text
id
source_article_id
project_id
project_name
project_info
province
city
detailed_address
company_name
investment_amount_yi
industry
field
market
status
confidence
semantic_text
embedding vector(1536)
dedupe_decision
dedupe_score
created_at
```

### 7.4 projects

保存去重后的项目主档案。

```text
id
canonical_project_name
canonical_company_name
province
city
detailed_address
investment_amount_yi
industry
field
market
current_status
first_seen_at
last_seen_at
semantic_text
embedding vector(1536)
created_at
updated_at
```

### 7.5 project_events

保存项目状态变化。

```text
id
project_id
source_article_id
event_status
previous_status
event_date
change_label
created_at
```

### 7.6 push_logs

保存推送记录。

```text
id
run_id
channel
status
recipient
subject
message
artifact_path
error_message
created_at
```

## 8. AI 抽取设计

每篇文章可以返回 0 个、1 个或多个项目。AI 必须返回 JSON 数组。

输出结构：

```json
[
  {
    "project_name": "XX新能源材料项目",
    "project_info": "建设年产10万吨新能源电池材料生产线",
    "province": "江苏省",
    "city": "盐城市",
    "detailed_address": "盐城经济技术开发区",
    "company_name": "江苏XX新材料有限公司",
    "investment_amount_yi": 12.5,
    "industry": "新能源",
    "field": "电池材料",
    "market": "工业项目",
    "status": "环评公示",
    "confidence": 0.86
  }
]
```

抽取规则：

- 没有项目时返回空数组。
- 多个项目时返回多条。
- 投资额统一换算为“亿元”。
- 无法判断的字段填 `null`。
- 状态归一化为枚举值。
- 每条记录必须有 `confidence`。

状态枚举：

```text
拟建
备案
环评公示
环评批复
招标
开工
建设中
投产
停缓建
未知
```

## 9. pgvector 向量设计

### 9.1 语义文本

不直接使用整篇文章生成向量，而是使用结构化字段拼接项目语义文本：

```text
项目名称：XX新能源材料项目
企业名称：江苏XX新材料有限公司
地点：江苏省 盐城市 盐城经济技术开发区
投资额：12.5亿元
产业：新能源
领域：电池材料
市场：工业项目
状态：环评公示
项目信息：建设年产10万吨新能源电池材料生产线
```

`公众号名称`、`文章标题`、`文章链接` 不参与核心项目 embedding，但会保存在来源记录中。

### 9.2 检索方式

新项目记录生成 embedding 后，在 `projects` 表中查询相似项目：

```sql
SELECT
  id,
  canonical_project_name,
  canonical_company_name,
  1 - (embedding <=> :new_embedding) AS vector_similarity
FROM projects
WHERE province = :province
ORDER BY embedding <=> :new_embedding
LIMIT 20;
```

本地验证版优先用省份过滤，数据规模很小时可以直接全表 Top 20。后续数据增多后增加 HNSW 索引：

```sql
CREATE INDEX projects_embedding_hnsw
ON projects
USING hnsw (embedding vector_cosine_ops);
```

## 10. 去重评分策略

### 10.1 规则分

规则分满分 100：

```text
项目名称相似度：30分
企业名称相似度：25分
省份 + 地级市一致：15分
详细地址相似度：10分
投资额接近度：10分
产业/领域相似度：10分
```

投资额得分：

```text
差异 <= 5%：10分
差异 <= 10%：8分
差异 <= 20%：5分
差异 <= 30%：2分
超过 30%：0分
一方缺失：3分
双方缺失：5分
```

### 10.2 向量分

向量相似度转换为百分制：

```text
vector_score = vector_similarity * 100
```

### 10.3 综合分

本地验证版采用：

```text
综合分 = 规则分 * 0.65 + 向量分 * 0.35
```

判定区间：

```text
>= 85：自动合并为同一项目
70-84：疑似重复，标记待复核
< 70：新增项目
```

### 10.4 示例

历史项目：

```text
项目名称：江苏华能年产10万吨新能源电池材料项目
企业名称：江苏华能新材料有限公司
省市：江苏省 盐城市
地址：盐城经济技术开发区
投资额：12.0亿
产业：新能源
领域：电池材料
状态：环评公示
```

新项目：

```text
项目名称：华能新材料电池正极材料生产基地项目
企业名称：江苏华能新材料有限公司
省市：江苏省 盐城市
地址：盐城经开区
投资额：12.3亿
产业：新能源
领域：锂电材料
状态：开工
```

规则分：

```text
项目名称：22 / 30
企业名称：25 / 25
省市一致：15 / 15
详细地址：8 / 10
投资额：10 / 10
产业/领域：9 / 10
合计：89
```

向量分：

```text
91
```

综合分：

```text
89 * 0.65 + 91 * 0.35 = 89.7
```

判定为同一项目，并触发状态变化：

```text
环评公示 -> 开工
```

## 11. 状态变化识别

如果新记录匹配到已有项目：

- 状态相同：补充来源文章，不新增状态事件。
- 状态不同：写入 `project_events`，更新 `projects.current_status`。

Excel 标注：

```text
状态变化：环评公示 -> 开工
是否状态更新：是
```

## 12. Excel 输出设计

文件命名：

```text
exports/market_projects_YYYY-WW.xlsx
```

工作表：

```text
本周新增与更新
项目全量台账
疑似重复待复核
运行摘要
```

核心列：

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

## 13. 邮件推送

邮件为正式交付渠道。

配置：

```text
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
MAIL_FROM
MAIL_TO
MAIL_CC
```

邮件内容：

```text
主题：市场项目信息周报 - YYYY年第WW周
附件：market_projects_YYYY-WW.xlsx
正文：新增项目数、状态更新数、疑似重复数、涉及公众号数、生成时间
```

## 14. 企业微信摘要推送

企业微信只发送摘要。

配置：

```text
WECOM_WEBHOOK_URL
```

摘要示例：

```text
### 市场项目信息周报
本周新增项目：32 个
状态更新项目：8 个
疑似重复待复核：3 个
涉及公众号：6 个
Excel 已发送至市场部邮箱。
```

## 15. 异常处理

### 15.1 exporter 登录失效

表现：

```text
auth-key 无效
文章列表接口返回认证失败
```

处理：

```text
停止采集
记录运行失败
企业微信推送登录失效摘要
提示用户访问 exporter 重新扫码
```

### 15.2 AI 抽取失败

处理：

```text
单篇文章重试 2 次
仍失败则记录 extraction_failed
继续处理后续文章
运行摘要中列出失败数量
```

### 15.3 邮件失败

处理：

```text
记录 push_logs
企业微信摘要提示邮件发送失败
Excel 文件仍保存在 exports/
```

### 15.4 企业微信失败

处理：

```text
记录 push_logs
不影响邮件发送
```

## 16. 本地验证验收标准

本地验证通过需要满足：

- Docker 能启动 exporter 和 PostgreSQL + pgvector。
- 能完成公众号扫码登录。
- 能抓取 3-5 个公众号文章。
- 重复运行不会重复入库同一篇文章。
- AI 能抽取项目字段。
- `projects` 和 `project_records` 能保存 embedding。
- pgvector 能召回相似项目。
- 规则分 + 向量分能识别同一项目。
- 状态变化能写入 `project_events`。
- Excel 字段完整，包含公众号名称和文章链接。
- 邮件能发送 Excel 附件。
- 企业微信能推送摘要。
- 登录过期时能给出明确提示。

## 17. 云服务器迁移原则

本地验证通过后，迁移到云服务器时保持架构不变：

```text
Docker Compose
wechat-article-exporter
PostgreSQL + pgvector
market-info-app
exports 挂载目录
.env 配置
```

上线时需要重新扫码登录公众号后台。数据库、公众号配置、邮件配置、企业微信 webhook 和 AI API Key 可直接迁移。
