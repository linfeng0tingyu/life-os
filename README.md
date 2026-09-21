---
title: "Life OS 工程说明"
type: project-readme
created: 2026-09-18T14:30:00+08:00
updated: 2026-09-21T10:48:12+08:00
status: draft
related:
  - "[[项目说明]]"
  - "[[里程碑计划]]"
  - "[[部署与迁移指南]]"
  - "[[桌面封装架构与改造工作量评估]]"
  - "[[M4.5桌面封装建设记录]]"
  - "[[界面主题设计规范]]"
  - "[[M5任务与习惯闭环建设记录]]"
---

# Life OS

Life OS 是一个本地优先、以日期为中心的个人生活管理系统。当前已完成 M1–M5：具备可移植运行时、SQLite 数据库与领域服务、统一核心 API、日期界面、完整任务与习惯闭环、七套可切换视觉主题，以及可直接打开的 Windows 独立桌面窗口和 `onedir` 便携发行基础。

## 当前状态与目标运行方式

普通用户入口现为 PyInstaller `onedir` 包中的 `LifeOS.exe`。双击后由 Waitress 在随机回环端口承载现有 Flask 应用，并由 pywebview/WebView2 显示独立窗口；不显示终端、不打开外部浏览器，也不要求安装 Python。`start.bat` 与 `app.py` 继续作为源码开发和故障诊断入口。

## 桌面版快速启动

1. 保持 `dist/LifeOS/` 整个目录结构不变，不能只复制 `LifeOS.exe`。
2. 双击 `dist/LifeOS/LifeOS.exe`。首次启动会在可执行文件旁创建 `life-os-data/`。
3. 正常关闭窗口后再复制或迁移 `life-os-data/`。

目标设备需要 64 位 Windows 10/11 和兼容的 Microsoft Edge WebView2 Runtime；不需要 Python、pip、Node.js、SQLite 服务或外部浏览器。要使用另一个绝对数据目录，可执行：

```bat
LifeOS.exe --home "D:\LifeOSData"
```

完整环境要求、迁移方法和故障处理见 [[部署与迁移指南]]。

## 界面主题与 Logo

共享导航中的“界面风格”可以即时切换：默认、古风竹青、古风藏青、古风水色、新拟物派、macOS 毛玻璃和吉卜力风格。切换只修改色彩、字体、圆角、边框、阴影、背景与图标表现，不调用业务 API，也不修改 SQLite。桌面版会把选择作为可丢弃的 WebView 本地偏好保存在 `life-os-data/cache/webview/`，并兼容随机端口重启；清空缓存后回到默认。

页面和桌面图标统一来自 `design-assets/logo-concepts/life-os-logo-02a-ref-a-full-landscape-contained.png`。七套风格的具体色板、组件语言和验收边界见 [[界面主题设计规范]]。

## 当前源码运行环境要求

- Windows 10 或 Windows 11，推荐 64 位系统。
- 64 位 Python 3.12 或更高版本；推荐安装 Python Launcher（`py`）或将 `python` 加入 PATH。
- 现代版 Edge、Chrome 或 Firefox。
- 首次安装依赖时需要访问 Python 包源；安装完成后，M1 基础服务可离线运行。
- 普通用户权限即可，不需要 Docker、Node.js、单独安装 SQLite 或数据库服务。
- 默认使用 `127.0.0.1:5000`，该端口必须空闲。

桌面发行与源码诊断两种运行方式的完整要求、目录复制步骤和配置格式见 [[部署与迁移指南]]。

## 当前源码快速启动

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
│   └── webview/                # 桌面模式的 WebView 缓存、主题偏好与存储
├── logs/app.log
├── temp/life-os.lock
└── metadata.json
```

所有应用生成的配置、数据库、备份、导出、缓存、日志和临时文件必须位于这一根目录。`.venv` 是设备相关的 Python 环境，不属于应用数据，不应随数据目录迁移。

## 源码开发与诊断启动

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

上述固定端口和外部浏览器只属于源码诊断模式。正式桌面模式使用进程内协商的随机 `127.0.0.1` 端口，并由窗口生命周期统一启动和关闭服务。

## 核心 API

M3 提供以下路径，成功响应统一使用 `{"success": true, "data": ...}`，失败响应统一使用 `{"success": false, "error": ...}`：

- `GET /api/day/{date}`：聚合指定日期的日历标记、习惯日志、计划/到期/逾期任务、健康、日记和当日财务流水。
- `GET /api/calendar/month/{year-month}` 与 `PUT|DELETE /api/calendar/days/{date}`：查询月历及轻量数据/习惯摘要，并设置或清除工作日、休息日、节假日和自定义标记。
- `/api/habits` 与 `/api/habits/{id}/log/{date}`：管理习惯、停用/恢复、排序及每日记录。
- `/api/tasks` 与 `/api/tasks/{id}/restore`：创建、查询、编辑、归档和恢复任务，支持日期、状态和归档筛选。
- `GET|POST /api/categories`：按任务或习惯作用域列出、创建可单选分类。
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

构建桌面便携包：

```bat
build_desktop.bat
```

脚本会安装 `requirements-build.txt`、生成应用图标，并通过 `LifeOS.spec` 重建 `dist/LifeOS/`。该目录已被 Git 忽略，发布时应整体复制；构建要求 64 位 Python 3.12+，本轮已在 Python 3.14.6 上验证。

## 数据库基础

首次启动会自动创建 `LIFE_OS_HOME/database/life.db`，不需要手工执行 SQL。当前 schema 版本为 `3`，在既有生活数据表外包含财务表与任务/习惯分类表。现有 schema v1/v2 会在启动时原地升级，并按作用域把旧任务、习惯中的非空分类回填为单选选项，不删除既有数据。

每个连接启用 SQLite 外键约束、5 秒 busy timeout、WAL 与 NORMAL synchronous；启动后执行完整性检查，正常关闭时执行 WAL checkpoint。日期服务默认把周一至周五解析为工作日、周六与周日解析为休息日，显式记录可以覆盖该推断并保存节假日名称与自定义标签。

## 当前边界

M4 已完成 Today Dashboard、独立日历页、任意日期访问、未来任务快速规划、工作/休息日标记、统一 API Client 和前端状态框架。“今日”只呈现设备本地当天数据；过去与未来月份、完整日期聚合和节假日/自定义标记统一在 `/calendar` 中处理。日历详情与 Today 使用相同的任务、习惯、生活节律、日记和财务布局，其中生活节律概览只显示睡眠时长、体重、运动和身体健康；未来日期可以新增安排到当天的任务。主内容随视口自适应填满可用空间，超宽屏自动分栏、窄屏保持单列。

M4.5 已完成桌面入口、Waitress 生命周期、动态回环端口、WebView 缓存归位、冻结资源定位、统一 Logo 图标/版本资源和 `onedir` 构建脚本。M4 的主题增量已实现七套风格、即时切换、偏好恢复和本地 Logo；最终发布前仍需在 M8 的全新 Windows 设备上完成完整迁移和恢复验收。

M5 已完成 `/tasks` 与 `/habits` 独立管理页。任务支持创建、编辑、开始、完成、取消、重新打开、排序、归档与恢复；习惯支持创建、编辑、排序、停用、恢复，以及今天或过去日期的即时打卡。新增与编辑表单默认隐藏，点击按钮后以应用内模态窗口打开；任务和习惯分类是分作用域、可现场创建的单选项。Calendar 页首“回到今日”返回 Today，月历内部“回到今天”才会把日期详情、月历和 URL 同步定位到系统今天。Today 与 Calendar 的日期详情可直接切换任务和习惯状态，写入期间会阻止重复触发。健康、日记和财务的完整交互仍在 M6。
