---
domain: procedural
description: >
  程序知识域索引。工作流、操作步骤。
---

# procedural

## 本域知识页

- [demo-generation](demo-generation.md) — 独立 Demo 生成工作流（六步闭环）：需求理解→技术设计→工程创建→代码编写→编译验证→文档沉淀。 适用于用户直接要求"写一个 demo"/"生成测试工程"等独立 demo 创建场景。 区别于框架问题分析 [I] 和系统问题验证 [P] 中嵌入的复现 demo 生成。
- [framework-fix-verification](framework-fix-verification.md) — 框架问题修复验证工作流：获取验证清单→编写验证工程→人工手动验证→记录验证结果。 用于系统性地验证Qt框架bug修复的有效性。
- [framework-issue-analysis](framework-issue-analysis.md) — 框架内部问题分析工作流（四阶段闭环）：复现demo生成→编译修复迭代→问题定位(日志法)→根因分析(框架代码调用链)→系统接口验证→上游issue打包提交（工作流最终步骤）。 阶段四为工作流闭合点：生成clean patch、整理issue说明单、输出纯Qt复现demo、更新知识库索引。 适用于Qt框架在鸿蒙平台的bug分析。
- [qt-app-harmonyos-migration](qt-app-harmonyos-migration.md) — Qt应用鸿蒙化迁移工作流：评估可行性→创建工程结构→按8步决策树逐步迁移→编译验证→知识积累。 将其他平台的Qt应用迁移到HarmonyOS平台的端到端流程。
