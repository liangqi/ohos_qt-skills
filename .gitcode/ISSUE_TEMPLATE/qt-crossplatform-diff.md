---
name: Qt 跨平台行为差异（无文档说明）
about: Qt 在鸿蒙上的行为与其他平台不同，且 Qt 文档未说明该差异
title: "[Qt 跨平台差异] "
labels: ["qt-crossplatform", "needs-triage"]
---

## 现象一句话
<!-- 哪个 Qt API / 行为，在鸿蒙上与其它平台不同 -->

## 环境信息（必填，用于内部复现分析）
- Qt 版本：<!-- 5.12.12 / 5.15.16 / 6.x；贴 tqtc/harmonyos 分支 + commit -->
- 鸿蒙版本 / API：<!-- API 17 / 20 等 -->
- 设备型号 + 系统版本：
- DevEco Studio 版本：
- OHOS SDK（native）版本：
- CMake / 工具链版本：

## 其它平台的预期行为
<!-- Windows / Linux / macOS / Android 上的行为；贴平台 + Qt 版本 -->

## 鸿蒙上的实际行为
<!-- 详细描述；含是否崩溃 / 渲染异常 / 静默 no-op / 返回值不同 -->

## 是否查过文档
- [ ] Qt 官方文档（贴链接；是否提到该平台差异？）
- [ ] HarmonyOS 官方文档（贴链接）
- [ ] 本知识库 semantic/qt-harmonyos-platform-limits.md（是否已记录为已知限制）

## 最小复现
<!-- 剥离业务的 Qt 最小工程步骤；可附 demo 仓库链接 -->
1.
2.
3.

## 日志
<!-- hilog / Qt debug 输出关键片段；崩溃贴 backtrace -->

## 归属初判
<!-- 你倾向认为是：Qt 问题 / 鸿蒙系统问题 / 应用问题？简述依据 -->
