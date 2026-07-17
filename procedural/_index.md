---
domain: procedural
description: >
  程序知识域索引。工作流、操作步骤。
---

# procedural

## 本域知识页

- [demo-generation](demo-generation.md) — 独立 Demo 生成工作流（六步闭环）：需求理解→技术设计→工程创建→代码编写→编译验证→文档沉淀。 适用于用户直接要求"写一个 demo"/"生成测试工程"等独立 demo 创建场景。 区别于框架问题分析中嵌入的复现 demo 生成。
- [fetch-ohos-third-party-lib](fetch-ohos-third-party-lib.md) — 从 Harmonybrew 一键下载 arm64-OpenHarmony 预编译 bottle（.so）并校验解压， 免交叉编译即可链接到 Qt 鸿蒙工程。含依赖递归、qmake/CMake 链接片段、版本解析陷阱。
- [framework-fix-verification](framework-fix-verification.md) — 框架问题修复验证工作流：获取验证清单→编写验证工程→人工手动验证→记录验证结果。 用于系统性地验证Qt框架bug修复的有效性。
- [framework-issue-analysis](framework-issue-analysis.md) — 框架内部问题分析工作流（四阶段闭环）：复现demo生成→编译修复迭代→问题定位(日志法)→根因分析(框架代码调用链)→系统接口验证→上游issue打包提交（工作流最终步骤）。 阶段四为工作流闭合点：生成clean patch、整理issue说明单、输出纯Qt复现demo、更新知识库索引。 适用于Qt框架在鸿蒙平台的bug分析。
- [qt-app-harmonyos-completion](qt-app-harmonyos-completion.md) — 应用鸿蒙化完善工作流（功能级测试用例闭环,四阶段）：扫描应用源码识别核心功能点→生成10核心测试用例（AI扫源码+人工review）→ 人工测试/反馈问题/修复/回归循环→10用例全pass闭合。前置：运行测试(qt-ohos-run-test)通过。 含三件套(ASCII循环图/循环退出条件✅10用例全pass/门控检查⚠️)。
- [qt-app-harmonyos-migration](qt-app-harmonyos-migration.md) — Qt应用鸿蒙化迁移工作流：评估可行性→创建工程结构→按8步决策树逐步迁移→编译验证→知识积累。 将其他平台的Qt应用迁移到HarmonyOS平台的端到端流程。
- [qt-ohos-run-test](qt-ohos-run-test.md) — 鸿蒙化运行测试工作流（CLI全流程,七阶段闭环）：环境SDK预检→构建静态预检(DT_NEEDED/符号可见性/QML插件部署)→ 签名安装→启动运行时测试(渲染黑屏三类定位/Ability生命周期退出/窗口行为回归/输入事件/平台限制回归)→ 崩溃日志分析→修复回归→Playbook B Demo。聚焦让应用在真机跑起来,非全量功能验证(功能用例闭环见应用鸿蒙化完善)。 含三件套(ASCII循环图/循环退出条件✅/门控检查⚠️)。被应用移植/构建排障/修复验证复用。
