---
title: "Life OS 工程说明"
type: project-readme
created: 2026-09-18T14:30:00+08:00
updated: 2026-09-19T21:31:25+08:00
status: draft
related:
  - "[[项目说明]]"
  - "[[里程碑计划]]"
  - "[[部署与迁移指南]]"
---

# Life OS

Life OS 是一个本地优先、以日期为中心的个人生活管理系统。当前已完成 M1–M3：具备 Flask 工程与可移植运行时、SQLite 数据库与领域服务，以及统一 JSON 合同下的日期聚合、日历、习惯、任务、健康、日记和个人财务 API。正式业务界面将在后续里程碑实现。

## 环境要求

- Windows 10 或 Windows 11，推荐 64 位系统。
- 64 位 Python 3.12 或更高版本；推荐安装 Python Launcher（`py`）或将 `python` 加入 PATH。
- 现代版 Edge、Chrome 或 Firefox。
- 首次安装依赖时需要访问 Python 包源；安装完成后，M1 基础服务可离线运行。
- 普通用户权限即可，不需要 Docker、Node.js、单独安装 SQLite 或数据库服务。
- 默认使用 `127.0.0.1:5000`，该端口必须空闲。

迁移目标设备的完整要求、目录复制步骤和配置格式见 [[部署与迁移指南]]。

## 快速启动

双击 `start.bat`。首次启动会在项目目录创建 `.venv`，安装 `requirements.txt` 中的依赖，然后启动服务并打开浏览器。

默认运行时目录是项目目录下的 `life-os-data/`。要使用已迁移的数据目录，可在命令提示符中执行：

```bat
start.bat "D:\LifeOSData"
```

需要阻止自动打开浏览器时，可追加 `--no-browser`：

```bat
start.bat "D:\LifeOSData" --no-browser
```

也可以预先设置绝对路径环境变量：

```bat
set LIFE_OS_HOME=D:\LifeOSData
start.bat
```

选择顺序为：命令行 `--home`/`start.bat` 第一个参数、`LIFE_OS_HOME` 环境变量、项目内默认 `life-os-data/`。

## 运行时目录

程序首次启动会创建：

```text
life-os-data/
├── config/settings.json
├── database/life.db
├── backups/
├── exports/
├── cache/
├── logs/app.log
├── temp/life-os.lock
└── metadata.json
```

所有应用生成的配置、数据库、备份、导出、缓存、日志和临时文件必须位于这一根目录。`.venv` 是设备相关的 Python 环境，不属于应用数据，不应随数据目录迁移。

## 命令行启动与检查

使用已建立的虚拟环境：

```bat
.venv\Scripts\python.exe app.py --check
.venv\Scripts\python.exe app.py --no-browser
.venv\Scripts\python.exe app.py --home "D:\LifeOSData"
```

服务健康检查：

```text
GET http://127.0.0.1:5000/api/system/health
```

## 核心 API

M3 提供以下路径，成功响应统一使用 `{"success": true, "data": ...}`，失败响应统一使用 `{"success": false, "error": ...}`：

- `GET /api/day/{date}`：聚合指定日期的日历标记、习惯日志、计划/到期/逾期任务、健康、日记和当日财务流水。
- `GET /api/calendar/month/{year-month}` 与 `PUT|DELETE /api/calendar/days/{date}`：查询月历及轻量数据/习惯摘要，并设置或清除工作日、休息日、节假日和自定义标记。
- `/api/habits` 与 `/api/habits/{id}/log/{date}`：管理习惯及每日记录。
- `/api/tasks`：创建、查询、编辑和归档任务，支持日期、状态和归档筛选。
- `/api/health/{date}` 与 `/api/journal/{date}`：按日期读写健康/睡眠数据和 Markdown 日记。
- `/api/finance/accounts`、`/api/finance/transactions` 与 `/api/finance/summary`：管理 CNY 资产/负债账户、收入/支出/转账流水和总体财务摘要。
- `GET /api/system/info`：返回应用版本、schema 版本和可移植运行时状态，不暴露本机绝对路径。

详细字段、状态码与验收行为见 [[接口验收清单]]。

## 开发与测试

开发依赖与测试命令：

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

测试使用临时 `LIFE_OS_HOME`，不会向默认 `life-os-data/` 写入测试状态。

## 数据库基础

首次启动会自动创建 `LIFE_OS_HOME/database/life.db`，不需要手工执行 SQL。当前 schema 版本为 `2`，在既有生活数据表外包含 `finance_accounts` 和 `finance_transactions`。现有 schema v1 会在启动时原地升级为 v2，不删除既有数据。

每个连接启用 SQLite 外键约束、5 秒 busy timeout、WAL 与 NORMAL synchronous；启动后执行完整性检查，正常关闭时执行 WAL checkpoint。日期服务默认把周一至周五解析为工作日、周六与周日解析为休息日，显式记录可以覆盖该推断并保存节假日名称与自定义标签。

## 当前边界

M4 已完成 Today Dashboard、月历与日期导航、工作/休息日标记、统一 API Client 和前端状态框架。任务与习惯当前只读展示聚合结果，完整交互在 M5；健康、日记和财务当前只读展示或保留稳定容器，完整交互在 M6。复杂预算、账单导入、多币种和投资分析不在 v0.1 范围内。备份、导出与跨路径迁移演练按计划在 M7 完成。
