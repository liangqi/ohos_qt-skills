---
id: fault-C-XXXX
cid: C-XXXX
type: cause
title: <一句话根因标题（写根因，不写现象）>
nature: defect            # defect（会修→T 跟踪+fix_route）/ limitation（规格→W 替代方案+evidence/evolution）/ undetermined
domain: runtime           # build/deploy/runtime/render/api/input/lifecycle/toolchain/filesystem
fault_type: bug           # bug/crash/build-blocker/hang/gap/regression/caveat/deprecation
responsible: undetermined # qt-port/qt-upstream/ohos-runtime/ohos-toolchain/ohos-ndk/third-party/app/undetermined
co_responsible: []        # 可选：叠加责任次要方
component: "<组件/文件>"
severity: medium          # blocker/critical/high/medium/low
# 证据标准见 _index §六：defect 禁 docs；静态可判定类才可用 source，
# Qt 框架侧 source 会收 WARN（提上游前补 demo/日志）
evidence_type: logs
status: open              # open/diagnosed/workaround/reported/fix-confirmed/verified/wontfix/watching/closed
fix_route: "<defect：修复到达路径一句话>"
evidence: "<limitation：定性证据（官方文档/平台行为实证）>"
evolution: "<limitation：演进方向与观察点>"
review_note: "<复核要点（review 输出用）>"
depends_on: []            # 本根因解除所依赖的其他 C 节点（仅实证时填写，禁止推测连边）
affects_qt: []            # 对齐根文档校验基准；不确定写 "未记录"
affects_ohos: []
qoh: []                   # 可选：关联机器层错误模式
first_seen: YYYY-MM-DD
review_due: YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
audience: public
refs: []
summary: >
  <一句话：根因 + nature + 责任领域 + 当前状态 + W/T 有无。>
---

# C-XXXX <根因标题>

> nature: defect ｜ 责任: qt-port ｜ 状态: open ｜ 表现: S-XXXX ｜ 方案: W-XXXX ｜ 跟踪: T-XXXX ｜ 复核: YYYY-MM-DD

## 表现（symptoms）

### S-XXXX <现象标题>

<该症状的详细可观察表现：错误信息原文、日志关键行、触发条件。症状本体是薄记录
（_data/symptoms.yaml），细节落在这里。>

## 根因 / 定性依据

<defect：源码级/日志级证据链；limitation：规格证据；undetermined：已知边界与待定性问题。>

## 责任判定

<为什么归这个 responsible；修复到达路径（随哪个版本流到手上）；叠加责任说明。>

## 根治方案（defect）

<上游修复方式 / 建议 patch；无则写等待方向。>

## 替代方案与演进（limitation）

<替代方案引用 W-xxxx 展开；演进方向与观察点。defect 节点删除本节。>

## 临时方案（Workarounds）

- **W-XXXX（status，验证 date env）**：<方案展开 + 代价 + 退役条件>。

<方案记录本体在 _data/workarounds.yaml（targets 指向本 C）；详细步骤写在这里，
W.detail 指向本小节。>

## 跟踪单（Tickets）

- **T-XXXX（tracker，单号，status）**：<单据性质/答复摘要/fix_version>。

<跟踪单记录本体在 _data/tickets.yaml（tracks 指向本 C）；released 时 fix_version
必填，build 会聚合进 _graph.yaml 的 C.fixed_in。>

## 版本验证记录

| 日期 | 环境（Qt/OHOS） | 动作 | 结果 | 状态变化 |
|------|----------------|------|------|---------|
|      |                |      |      |         |

## 关联

- 症状（S）：
- 临时方案（W）：
- 跟踪单（T）：
- problems / semantic / episodic：
- QOH（机器层）：
- 相关根因（C，含 depends_on 说明）：

---

<!-- 录入流程（faults/_index.md §六）：
     ①查/建 S（_data/symptoms.yaml）②查/建 C（勿重复建档）③定性 nature
     ④登记 W（_data/workarounds.yaml，含 retire_when）⑤登记 T（_data/tickets.yaml）
     ⑥连边（S.causes/W.targets/T.tracks 在真源文件写；C.depends_on 仅实证）
     ⑦python tools/faults-build.py build（ERROR 必须先修）
     ⑧关联页 refs 回填 fault-C-XXXX。不确定的字段留空，不要编造。 -->

<!-- S 记录模板（追加到 _data/symptoms.yaml）：
  - id: S-XXXX
    title: "现象一句话（检索锚点）"
    domain: input
    severity: high
    status: active            # active/mitigated/resolved
    causes: [C-XXXX]          # 多根因加 cause_relation: all_of|any_of（默认 any_of）
    first_seen: YYYY-MM-DD
    refs: [problem-xxx]
-->

<!-- W 记录模板（追加到 _data/workarounds.yaml）：
  - id: W-XXXX
    title: "方案一句话"
    targets: [C-XXXX]
    status: proposed          # proposed/tested/adopted/retired
    cost: "代价一句话"
    verified:
      date: YYYY-MM-DD
      env: "验证环境"
    retire_when: "退役条件（官方修复/迁移后要撤销什么）"
    detail: "C-XXXX-slug.md §临时方案"
-->

<!-- T 记录模板（追加到 _data/tickets.yaml）：
  - id: T-XXXX
    tracker: qt-bug           # qt-bug/ohos-issue/gitee/partner/forum/upstream
    number: "QTBUG-xxxxxx"
    url: "https://..."
    tracks: [C-XXXX]
    status: submitted         # draft/submitted/accepted/dup/wontfix/fixed/released/closed
    filed: YYYY-MM-DD
    fix_version: ""           # released 起必填（如 "Qt 6.12-beta4"、"API 25"）
    fix_commit: ""
    last_update: ""
    notes: "单据性质/答复摘要"
-->
