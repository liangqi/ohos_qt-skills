---
updated: 2026-07-02
total_pages: 32
description: >
  开发者版知识地图（audience:public 过滤）。按 summary 判断相关性。
---

# 知识地图

> 按 summary 判断相关性；沿 refs 追深度上下文。

## semantic

- [deveco-mcp-toolchain](../semantic/deveco-mcp-toolchain.md) — DevEco MCP工具链安装配置：三种安装方式(npx推荐/二进制/Toolbox可视化)、 七种IDE配置模板(Trae CN/国际版/Cursor/VS Code/Gemini Code Assist/Claude Desktop/ OpenCode)、ArkTS语法校验插件、11个MCP工具验证表。
- [harmonyos-dev-fundamentals](../semantic/harmonyos-dev-fundamentals.md) — 鸿蒙开发基础知识：HarmonyOS vs OpenHarmony 区别、技术架构、 DevEco Studio IDE、Node-API（C/C++与ArkTS交互）、ArkTS 语言、 ArkUI 框架、hdc 调试工具、常用链接和示例。
- [qt-harmonyos-api-mapping](../semantic/qt-harmonyos-api-mapping.md) — Qt鸿蒙API迁移映射表：12大类Before/After对照——进程管理、应用间通信、 窗口管理、关闭事件、文件系统、启动参数、拖放、主题外观、时区、线程、 分享、应用接续。每类含映射表和代码示例。
- [qt-harmonyos-api](../semantic/qt-harmonyos-api.md) — Qt 鸿蒙化 API 兼容性要点：argv 参数差异、QProcess 不可用（改用 startAbility/ startNoUiChildProcess）、窗口模型差异（QDialog/Popup 为子窗口）、 modality 仅子窗口有效、winId() 非原生句柄、hide() 语义不同、 setMask() 仅子窗口、closeEvent 可能来自系统生命周期。 平台判断：Qt.platform.os 在鸿蒙返回 "linux"（上游 os() 缺 Q_OS_OHOS 分支），临时用 pluginName，建议上游修复。 设备类型判断：Qt 不导出公开设备类型接口；私有层 QtCore 的 QOhosDeviceInfo（Q_CORE_EXPORT，可 include 可 link，但仅 2in1/tablet/phone 三档、本质是 @ohos.deviceInfo 缓存）可用，应用层推荐直接走 Node-API 调 @ohos.deviceInfo。
- [qt-harmonyos-build-run-workflow](../semantic/qt-harmonyos-build-run-workflow.md) — Qt 鸿蒙编译运行全流程：DevEco MCP 工具链配置、构建/启动/日志/UI测试操作步骤、构建失败排查四步法。
- [qt-harmonyos-build](../semantic/qt-harmonyos-build.md) — Qt for HarmonyOS 构建指南：macOS/Windows 编译环境搭建、configure 参数、 Qt Creator Kit 配置、DevEco Studio 集成、OpenSSL/OpenGL 配置、Qt 5.15 skip 列表。
- [qt-harmonyos-code-patterns](../semantic/qt-harmonyos-code-patterns.md) — Qt鸿蒙移植12组Before/After代码模式速查：子进程→NoUi、启动外部应用→StartAbility、 独立对话框→tagged子窗口、关闭事件处理、文件权限守卫、参数解析、 平台构建配置、深色模式、拖放、等宽字体、浮窗、分享数据。
- [qt-harmonyos-golden-rules](../semantic/qt-harmonyos-golden-rules.md) — Qt 鸿蒙化铁律速查：33 条黄金规则覆盖构建部署、窗口管理、API/枚举路径、 平台限制、生命周期、跨平台守卫。每条含严重度（🔴🟠🟡🟢）、"为什么"和出处。 Agent 执行任何 Qt for HarmonyOS 任务前应先扫描此页。
- [qt-harmonyos-lifecycle](../semantic/qt-harmonyos-lifecycle.md) — Qt鸿蒙应用生命周期详解：Stage模型/UIAbility启动流程、启动其他应用 (显式/隐式Want)、被其他应用启动(module.json5 skills)、多实例管理、 3级关闭拦截(WindowStageClose/AbilityClose/InternalClose)、 应用接续(跨设备迁移)、分享(ShareKit)、无UI子进程、argv组装规则、主题管理。
- [qt-harmonyos-modules](../semantic/qt-harmonyos-modules.md) — Qt 5.12/5.15 鸿蒙模块适配状态速查：核心模块(QtCore/GUI/Widgets/QML/Quick/ Network/SQL)全部完成；**QtMultimedia 未包含在 SDK 中**（需自行编译）； 不支持的模块(QtWebEngine/D-Bus/RemoteObjects/SerialBus)； 部分支持的模块(QtPDF/QtQuickTimeline 仅5.15)。
- [qt-harmonyos-overview](../semantic/qt-harmonyos-overview.md) — Qt for HarmonyOS 总览：鸿蒙系统简介、Qt 鸿蒙化架构（QPA 插件机制）、 适配进展（Qt 5.12.12/5.15.16，适配率约90%）、 支持设备（手机/平板/PC/2in1）、源码获取方式（Gerrit tqtc-qt5）。
- [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md) — 鸿蒙平台限制汇总：chmod/setPermissions 不可用、symlink 禁止第三方使用、 stat() 系统路径 EACCES、dlopen() 拒绝可写路径、无 tzdata（时区用 ICU）、 无等宽字体（需自带）、XComponent（SURFACE 类型）在 API 20 弃用、 MUSL 不能加载 stripped ELF。每条含华为确认状态和 QTBUG 编号。
- [qt-harmonyos-porting-workflow](../semantic/qt-harmonyos-porting-workflow.md) — Qt鸿蒙移植8步决策树工作流：扫描平台代码→API映射→窗口适配→生命周期适配→ 检查平台限制→构建系统适配→添加鸿蒙特性→验证模块支持。含5条核心原则。
- [qt-harmonyos-project-structure](../semantic/qt-harmonyos-project-structure.md) — Qt 鸿蒙工程结构详解：OHOS 模板（胶水代码）目录布局、CMake 交叉编译配置、 库名规则（QtAppConstants.ets ↔ add_library）、两种场景（从零创建 / 已有工程鸿蒙化）。
- [qt-harmonyos-qt6-status](../semantic/qt-harmonyos-qt6-status.md) — Qt 6 鸿蒙化状态：qtbase dev 已合并 HarmonyOS 支持（Gerrit 733351）， 最低 SDK API 20（HarmonyOS 6.0.0），CMake 构建系统。 从 Qt6 源码验证：QStandardPaths 映射（4 枚举已确认）、QPA 插件 API 变更 （关闭事件私有化、枚举值改变）、QtOhosExtras 功能内联到 QPA 插件。 Qt5→Qt6 关键差异（QStandardPaths、CMake API、QML、QPA API）。
- [qt-harmonyos-third-party-libs](../semantic/qt-harmonyos-third-party-libs.md) — 三方库鸿蒙化指南：OHOS NDK 交叉编译（CMake 工具链配置）、.so 部署规则 （entry/libs/arm64-v8a/）、CMake find_package 集成、平台限制对三方库的影响 （chmod/symlink/dlopen/pthread_cancel）、vcpkg 参考、静态/动态链接策略、 系统库可用性、header-only 库、已知兼容清单。
- [qt-harmonyos-window-model](../semantic/qt-harmonyos-window-model.md) — Qt鸿蒙窗口模型详解：MainWindow(有Dock/任务图标/独立生命周期) vs Subwindow(无Dock/属于主窗口/随主窗口关闭最小化恢复)。核心规则： 首个窗口自动绑定、后续窗口默认新主窗口、tagging必须在show/winId之前。 QOhosFunctions API、6种代码模式、浮窗、全屏规则、嵌入式子窗口、跨进程嵌入。 含【QPA层】visible的来源（QWindowPrivate::visible）、OHOS系统回调链 （window.on('windowEvent')→WINDOW_SHOWN/HIDDEN/ACTIVE/INACTIVE）、 所有修改visible的7个位置、QOhosFloatingWindow命名陷阱、浮窗hide销毁链(setOrResetWindowProxy→destroyWindow)。
- [qt-ohos-extras](../semantic/qt-ohos-extras.md) — QtOhosExtras 模块：Qt 与鸿蒙系统交互的桥梁。提供 startAbility()、 startNewAbilityInstance()、startAppProcess()、startNoUiChildProcess()、 QOhosWant、tryGetNativeWindowId() 等鸿蒙专有 API。使用方式：QT += ohosextras。
- [qt-ohos-js-thread-gateway](../semantic/qt-ohos-js-thread-gateway.md) — Qt↔ArkTS/JS 线程桥接的私有 API：QOhosJsThreadGateway 命名空间（invoke/runAndWait/eval/ evalWithPromise/invokeAndWaitForContinue）是把 Qt 线程的调用安全 marshal 到唯一 JS 主线程的入口， QOhosJsThreadOps 是其背后的抽象接口（QPA 插件用 JsThreadOpsImpl 注册实现）。位于 QtCore 私有头 qcore_ohos_p.h，非公共 API。开发者用命名空间自由函数，不直接碰 QOhosJsThreadOps。
- [qt-ohos-project-analyzer-workflow](../semantic/qt-ohos-project-analyzer-workflow.md) — Qt项目移植OHOS的核心工作流：铁律约束、依赖梳理方法、编译编排流程、双重交验协议
- [qt515-vs-qt512-api-diff](../semantic/qt515-vs-qt512-api-diff.md) — QtWidgets 模块 Qt 5.15.17 vs 5.12.12 (OHOS SDK) 公共 API 完整差异报告： 1 个新头文件、67 个头文件有差异、~50 个新 API（QStyleOptionTabV4/QCalendar/Markdown/ExclusionPolicy/ OHOS 专有 QSystemTrayIcon/QFileDialog）、50+ 个废弃 API、Qt6 预备双重签名、迁移风险评估。

## procedural

- [demo-generation](../procedural/demo-generation.md) — 独立 Demo 生成工作流（六步闭环）：需求理解→技术设计→工程创建→代码编写→编译验证→文档沉淀。 适用于用户直接要求"写一个 demo"/"生成测试工程"等独立 demo 创建场景。 区别于框架问题分析 [I] 和系统问题验证 [P] 中嵌入的复现 demo 生成。
- [framework-fix-verification](../procedural/framework-fix-verification.md) — 框架问题修复验证工作流：获取验证清单→编写验证工程→人工手动验证→记录验证结果。 用于系统性地验证Qt框架bug修复的有效性。
- [framework-issue-analysis](../procedural/framework-issue-analysis.md) — 框架内部问题分析工作流（四阶段闭环）：复现demo生成→编译修复迭代→问题定位(日志法)→根因分析(框架代码调用链)→系统接口验证→上游issue打包提交（工作流最终步骤）。 阶段四为工作流闭合点：生成clean patch、整理issue说明单、输出纯Qt复现demo、更新知识库索引。 适用于Qt框架在鸿蒙平台的bug分析。
- [qt-app-harmonyos-migration](../procedural/qt-app-harmonyos-migration.md) — Qt应用鸿蒙化迁移工作流：评估可行性→创建工程结构→按8步决策树逐步迁移→编译验证→知识积累。 将其他平台的Qt应用迁移到HarmonyOS平台的端到端流程。

## episodic

- [coin3d-quarter-ohos](../episodic/postmortems/coin3d-quarter-ohos.md) — Coin3D Quarter 鸿蒙化完整迁移：交叉编译 libQuarter.so (ARM aarch64) + Demo 应用构建 (37MB HAP) + 3D 渲染验证通过。关键发现：OHOS Qt5 不含 UiTools 模块、FindOpenGL 需自定义（OHOS 用 GLES/EGL）、 CMAKE_FIND_ROOT_PATH_MODE ONLY 需绝对路径绕过、hvigor 需 DEVECO_SDK_HOME。 可复用：OHOS 交叉编译 CMake 模板 + FindOpenGL 映射模式 + 预编译库集成模式。
- [qt-opensource-apps-harmonyos-survey](../episodic/postmortems/qt-opensource-apps-harmonyos-survey.md) — 2026-06-25 多 agent 工作流扫描 GitHub/KDE Apps/Gitee/SourceForge/Wikipedia，筛选 229 个 Qt 开源桌面应用并逐个评估鸿蒙化难度。难度分布：低 3 / 中 23 / 高 126 / 阻断 77；D-Bus(107)、 QtMultimedia(76)、QtWebEngine(62) 为三大阻断模块。产出清单在 <INTERNAL_OUTPUT>。沉淀"大 schema 输出失败→主循环生成"的工作流教训。
- [quit-deadlock-tsfn](../episodic/postmortems/quit-deadlock-tsfn.md) — 退出死锁复盘：<STAKEHOLDER>(<PRODUCT>) qApp->quit()后应用卡死~2分钟。 根因：HarmonyOS在Ability销毁阶段不处理N-API ThreadSafeFunction回调， 导致qWindowDestroyPromise的resolve回调永远不被执行，Promise永不resolve。 修复：客户补丁通过原子变量+并行轮询绕过TSFN机制，已在生产环境验证。
- [saribbon-ohos](../episodic/postmortems/saribbon-ohos.md) — SARibbon v2.5.5 鸿蒙化完整迁移：独立构建文件 + MainWindowExample 应用编译 (48MB HAP) + 两个编译问题修复（QDesktopWidget::screen 类型不匹配 + lazy import 语法不兼容）。 关键发现：SARibbon 源码内 QDesktopWidget API 在 Qt 5.12 OHOS 下返回 QWidget* 而非 QScreen*、 模板 lazy import 语法需 API 12 beta3、需为项目创建独立 CMakeLists.txt 避免改源码。 可复用：三方 Qt 库鸿蒙化时保持源码完整性的独立构建文件模式。
- [toolwindow-crossscreen-flicker](../episodic/postmortems/toolwindow-crossscreen-flicker.md) — ToolWindow跨屏闪烁系统问题分析：moveWindowToGlobalDisplay与resizeAsync在跨屏拖拽场景冲突， screenIdChanged仅拖拽结束时触发，Qt已通过完整调用链追踪定位根因，归属鸿蒙系统接口。
- [wa-nativewindow-leave-bug](../episodic/postmortems/wa-nativewindow-leave-bug.md) — WA_NativeWindow Leave 事件不灵敏 Bug 完整分析：双重盲区根因（Qt Widget 层 internalWinId() 跳过 + OHOS QPA hover 回调不可靠）、完整调用链追踪、 修复策略评估（3 种方案对比）、10 场景风险矩阵、时序图。Qt 5.12 OHOS。 ✅ 手动验证通过，交付件已输出至 <WORK_DIR>/leave-event-fix/（2026-06-09 最终整理）。

## preference

_（开发者版无活跃页）_

## problems

- [_lookup](../problems/_lookup.md) — 错误速查表（13 条）


---

## 快速查找指南

| 我想知道... | 去看哪类知识 |
|------------|------------|
| 某个技术/概念是什么 | semantic |
| 某件事怎么操作 | procedural |
| 某个项目经验 | episodic |
| 遇到某个错误怎么办 | problems → _lookup.md |
| Qt 鸿蒙化的某个方面 | semantic → qt-harmonyos-* |
| 某个 Qt 模块是否在鸿蒙支持 | semantic → qt-harmonyos-modules |
| 鸿蒙平台有什么限制 | semantic → qt-harmonyos-platform-limits |
| 分析 Qt 应用 bug / 定位问题 | procedural → framework-issue-analysis |
| 验证修复是否生效 | procedural → framework-fix-verification |
| 把 Qt 应用迁移到鸿蒙 | procedural → qt-app-harmonyos-migration |
| 创建独立 demo / 测试工程 | procedural → demo-generation |
