---
id: kb-status-dashboard
type: meta
domain: quality
tags: [knowledge-base, dashboard, quality]
created: 2026-06-27
updated: 2026-07-17
status: active
refs: [semantic-qt-harmonyos-golden-rules]
summary: >
  开发者版知识库仪表盘：文件计数、分域活跃数、错误库条目数。
  由 _scripts/kb-dev-edition.sh 从 dev-edition.manifest 自动生成，请勿手改。
---

# 知识库仪表盘（开发者版）

> **总活跃页面**：35 | **归档页面**：1 | **元页面**：2

本知识库是 **Qt for HarmonyOS 移植参考**，覆盖 API 映射、窗口模型、生命周期、平台限制、构建部署、常见错误。完整页面清单见 [_map](_map.md)，按标签浏览见 [_tags](_tags.md)，任务路由见 [_task-routing](_task-routing.md)。

---

## 分域统计

### semantic（21 活跃）

语义知识——概念、API 参考、平台限制、模块状态、构建/工程/工作流。核心入口：
- [golden-rules](../semantic/qt-harmonyos-golden-rules.md) — 33 条铁律速查
- [api-mapping](../semantic/qt-harmonyos-api-mapping.md) — 12 大类 API 迁移映射
- [platform-limits](../semantic/qt-harmonyos-platform-limits.md) — 平台限制清单
- [code-patterns](../semantic/qt-harmonyos-code-patterns.md) — Before/After 代码模式

### procedural（7 活跃）

程序知识——应用鸿蒙化迁移、框架问题分析与修复验证、Demo 生成等工作流。

### episodic（6 活跃）

情景知识——实际移植项目复盘（SARibbon、Coin3D Quarter、退出死锁、跨屏闪烁、Leave Bug、开源应用难度调研）。

### preference（0 活跃）

开发者版不含个人偏好页。

> **problems/** 错误知识库，共 23 条目——编译/构建/运行时实际报错与解决方案，速查入口 [_lookup](../problems/_lookup.md)。

---

## 使用建议

| 我想做... | 入口页 |
|----------|--------|
| 移植一个 Qt 应用到鸿蒙 | [qt-app-harmonyos-migration](../procedural/qt-app-harmonyos-migration.md) + [api-mapping](../semantic/qt-harmonyos-api-mapping.md) + [code-patterns](../semantic/qt-harmonyos-code-patterns.md) |
| 分析 Qt 应用问题/崩溃 | 先 [golden-rules](../semantic/qt-harmonyos-golden-rules.md) 扫铁律，再 [framework-issue-analysis](../procedural/framework-issue-analysis.md) |
| 遇到已知报错 | 先查 [_lookup](../problems/_lookup.md) |
| 构建/部署报错 | [qt-harmonyos-build](../semantic/qt-harmonyos-build.md) + [build-run-workflow](../semantic/qt-harmonyos-build-run-workflow.md) + [_lookup](../problems/_lookup.md) |
| 查 API 替换 | [api-mapping](../semantic/qt-harmonyos-api-mapping.md) + [code-patterns](../semantic/qt-harmonyos-code-patterns.md) |
| 查窗口/生命周期/平台限制 | [window-model](../semantic/qt-harmonyos-window-model.md) / [lifecycle](../semantic/qt-harmonyos-lifecycle.md) / [platform-limits](../semantic/qt-harmonyos-platform-limits.md) |
