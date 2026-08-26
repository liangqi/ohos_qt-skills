---
name: Qt 行为与文档不一致（Qt bug）
about: Qt 在鸿蒙上的行为与 Qt 文档明确不一致，判定为 Qt bug
title: "[Qt 文档不一致] "
labels: ["qt-bug", "needs-triage"]
---

## 现象一句话
<!-- 哪个 Qt API / 行为，与 Qt 文档明确矛盾 -->

## Qt 文档依据（必填）
- Qt 文档链接：
- 文档原文引用：<!-- 贴出文档说"应怎样"的片段 -->

## 鸿蒙上的实际行为
<!-- 与文档不一致的具体点；崩溃贴 backtrace，返回值/渲染异常贴细节 -->

## 环境信息（必填，用于内部复现 + 上报 Qt 团队）
- Qt 版本：<!-- 5.12.12 / 5.15.16 / 6.x；贴 tqtc/harmonyos 分支 + commit -->
- 鸿蒙版本 / API：<!-- API 17 / 20 等 -->
- 设备型号 + 系统版本：
- DevEco Studio 版本：
- OHOS SDK（native）版本：

## 最小复现
<!-- 纯 Qt 最小 demo（剥离鸿蒙业务），便于上报 Qt 团队 -->
1.
2.
3.
- [ ] 可附 demo 仓库链接：

## 日志
<!-- hilog / Qt debug 关键片段；崩溃贴 backtrace -->

## 是否已提 QTBUG
<!-- 如已上报 bugreports.qt.io，贴编号/链接；如未提，注明是否需要我们协助上报 -->

## 是否可提供纯鸿蒙最小 demo
<!-- 用于区分是 Qt 问题还是鸿蒙系统接口问题（纯鸿蒙 demo 复现 = 系统问题，纯 Qt demo 复现 = Qt 问题） -->
