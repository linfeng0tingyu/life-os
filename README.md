---
title: "Life OS 工程说明"
type: project-readme
created: 2026-09-18T14:30:00+08:00
updated: 2026-09-18T15:04:44+08:00
status: draft
related:
  - "[[项目说明]]"
  - "[[里程碑计划]]"
  - "[[部署与迁移指南]]"
---

# Life OS

Life OS 是一个本地优先、以日期为中心的个人生活管理系统。当前已完成 M1–M2：具备 Flask 工程与可移植运行时、自动初始化的 SQLite 数据库、版本与完整性检查，以及日期标记、习惯、任务、健康、睡眠和日记领域服务。HTTP 业务 API 与正式界面将在后续里程碑实现。

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

## 开发与测试

开发依赖与测试命令：

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

测试使用临时 `LIFE_OS_HOME`，不会向默认 `life-os-data/` 写入测试状态。

## 数据库基础

首次启动会自动创建 `LIFE_OS_HOME/database/life.db`，不需要手工执行 SQL。当前 schema 版本为 `1`，包含 `schema_meta`、`calendar_days`、`habits`、`habit_logs`、`tasks`、`daily_health` 和 `journals`。

每个连接启用 SQLite 外键约束、5 秒 busy timeout、WAL 与 NORMAL synchronous；启动后执行完整性检查，正常关闭时执行 WAL checkpoint。日期服务默认把周一至周五解析为工作日、周六与周日解析为休息日，显式记录可以覆盖该推断并保存节假日名称与自定义标签。

## 当前边界

M2 已创建业务模型和领域服务，但不提供任务、习惯、日期标记、健康或日记 HTTP 接口。当前页面仅用于确认本地服务、运行时和数据库基础可用；后续实现顺序以 [[里程碑计划]] 为准。
