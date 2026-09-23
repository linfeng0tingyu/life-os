---
title: "Life OS Changelog"
type: changelog
created: 2026-09-23T09:15:00+08:00
updated: 2026-09-23T13:58:00+08:00
status: completed
---

# Changelog

## Unreleased

### 新增

- 信用卡负债账户支持 1–28 日的每月账单日，默认采用 18 日。
- 财务页增加账期视图、信用卡消费与还款快捷入口；还款使用现有账户转账，账期在账单日次日自动滚动。
- 数据库升级到 schema v5，原有信用账户安全补入默认账单日，账户 CSV 导出增加 `billing_day`。

## 0.1.0 — 2026-09-23

Life OS 的第一个可用桌面版本。

### 新增

- 日期中心化的 Today Dashboard 与可访问过去、现在、未来的完整月历。
- 离线农历、2025/2026 年法定节假日和调休，以及自定义工作日/休息日标记。
- 任务、习惯、生活节律、Markdown 日记和个人财务管理闭环。
- 默认、古风竹青、古风藏青、古风水色、新拟物派、macOS 毛玻璃和吉卜力七套主题。
- Waitress + pywebview + PyInstaller `onedir` Windows 桌面发行方式。
- 每日/手动 SQLite 一致性备份、CSV/Markdown/ZIP 全量导出和启动前安全恢复。
- 单一 `LIFE_OS_HOME` 可移植运行时，支持不同设备和不同绝对路径迁移。
- 项目源码与发行包采用 MIT License 开放使用、修改与分发。

### 数据兼容

- 当前数据库 schema 为 v4。
- 支持 schema v1、v2、v3 启动时原地升级，且不删除既有业务记录。
- v0.1 数据可通过 SQLite 备份和开放格式导出离开应用。

### 已知限制

- 仅支持 64 位 Windows 10/11 和 CNY 单币种。
- 需要兼容的 Microsoft Edge WebView2 Runtime。
- 不支持云同步、多人协作、手机端、通知、CSV 回导或自动异地备份。
