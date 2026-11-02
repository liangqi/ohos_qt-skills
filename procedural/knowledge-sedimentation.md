---
id: procedural-knowledge-sedimentation
type: procedural
domain: workflow
title: "知识沉淀协议（验证事件触发）"
status: active
audience: public
confidence: 1.0
contributors: [lzh]
sources:
  - type: experience
    name: "Trunk Flip v3.0.0 架构设计"
    date: 2026-09-07
created: 2026-09-07
updated: 2026-09-07
tags: [sedimentation, hook, protocol, automation]
refs: [procedural-qt-app-harmonyos-migration, semantic-qt-harmonyos-golden-rules, faults/_index]
summary: "知识沉淀的触发条件、验证事件、分类规则和操作流程 — 所有 Agent 必须遵循的通用协议"
---

# 知识沉淀协议（Hook 触发）

> **本文件是所有 Agent 的通用沉淀协议**。`AGENTS.md` / `CLAUDE.md` / `.cursorrules` / 其他工具配置
> 引用本文件，不内联复制规则。

## 核心原则

**知识沉淀由「验证事件」触发，不由定时器触发。**

完成鸿蒙化 = 知识经过实战验证 → 此时才值得沉淀。未经验证的知识不入库。

## 验证事件（Hook 触发点）

| # | 验证事件 | 触发条件 | 沉淀内容 | 目标路径 |
|---|----------|---------|---------|---------|
| 1 | **应用鸿蒙化完成** | `verify` G0–G12 全 PASS | 完整复盘记录 | `episodic/postmortems/`（或先入 `faults/_drafts/`） |
| 2 | **编译错误解决** | 错误修复后重新编译通过 | 错误 + 原因 + 方案 | `problems/build-fail-<slug>.md` |
| 3 | **运行时问题解决** | 设备上验证修复有效 | 错误 + 原因 + 方案 | `problems/runtime-<slug>.md` |
| 4 | **API 差异发现** | 实际代码验证了差异行为 | 更新 API 映射表 | 编辑 `semantic/qt-harmonyos-api-mapping.md` |
| 5 | **平台限制确认** | 实际触发了限制 | 更新限制清单 | 编辑 `semantic/qt-harmonyos-platform-limits.md` |
| 6 | **三方库编译成功** | 交叉编译产物在设备运行正常 | 更新兼容性记录 | 编辑 `semantic/qt-harmonyos-third-party-libs.md` |

### 何时不触发

- 任务中途放弃（未验证）
- 仅理论分析未有实际代码验证
- 重复已知问题（`problems/` 已收录）

## 沉淀命令（本仓实际入口）

本仓不提供 `kb-sediment.sh` 这类定时/钩子脚本：沉淀由**验证事件的终态**触发，入口是这些：

```bash
# 编译/运行时错误已修复 → 先建草稿（含证据类型与复现 demo 要求）
cp faults/_drafts/_template.md faults/_drafts/C-00XX-<slug>.md

# 故障定性/闭环：改真源后必须重建派生物，check 必须 error=0
python tools/faults-build.py build
python tools/faults-build.py check

# 页面类知识：套模板写入对应目录，再跑门禁
cp _templates/problem.md problems/build-<slug>.md
cp _templates/knowledge-page.md semantic/<slug>.md

# 收工自检（任何写入之后）
bash _scripts/ci.sh
```

草稿合入走主编门禁（`faults/_index.md` §六），Agent 侧流程见 `skills/kb-iterator/SKILL.md`。

## 分类规则（写入前强制判断）

| 内容特征 | 归属 | 动作 |
|----------|------|------|
| 含商业 Qt 客户往来、合同内容 | 私有 overlay | **停止**，提醒用户写入私有仓 |
| 含客户名称、内部项目代号 | 私有 overlay | **停止** |
| 含内部绝对路径（C:/Users/xxx 等） | 需脱敏 | 用 `${ENV_VAR}` 占位符替代 |
| 含同事真名 | 需脱敏 | 移除或用角色代替 |
| 含框架内部调试 trace（带内部路径） | 私有 overlay | **停止** |
| 通用技术知识（API、构建、错误、流程） | **本仓** | 继续写入 |

## 写入路径选择

| 知识类型 | 目标 | 模板 | 是否走草稿 |
|---------|------|------|:---------:|
| 编译/部署/运行时**报错**（已验证修复） | `problems/<type>-<slug>.md` | `_templates/problem.md` | 否（直接正式） |
| 对已有页面的**小修正** | 直接编辑 + bump `updated` | — | 否 |
| **新知识**：复盘/流程/API 差异 | `faults/_drafts/`（故障类）或直接正式页（知识类） | `_templates/draft.md` | 是 |

## 操作流程

```
验证事件发生
    │
    ├─ 1. 分类判断（公开 or 私有？）
    │      └─ 私有 → STOP，提醒用户
    │
    ├─ 2. 选择写入路径（problems/ or faults/_drafts/ or 编辑已有页）
    │
    ├─ 3. 写入内容（使用对应模板）
    │      └─ contributors: [MY_NAME] 从 ENV.local.md 读取
    │
    ├─ 4. 验证
    │      python tools/faults-build.py build && python tools/faults-build.py check
    │      bash _scripts/ci.sh
    │
    ├─ 5. 提交
    │      git checkout -b <MY_NAME>/sediment-<slug>
    │      git add <files>
    │      git commit -m "add(<scope>): <summary>（验证通过）"
    │      git push origin <branch>
    │
    └─ 6. 创建 PR（GitCode API 或 Web）
           └─ PR body 注明验证状态（编译 PASS / 设备 PASS）
```

## 各环节在本仓的对应物

| 职责 | 本仓做法 | 触发方式 |
|------|---------|---------|
| **知识生成** | Agent 按本协议写入；故障类先入 `faults/_drafts/` | 验证事件（`verify` 终态） |
| **草稿合入** | 主编门禁（`faults/_index.md` §六）+ `skills/kb-iterator` | 人工核验后 promote |
| **索引维护** | 计数由 `tests/test_kb_consistency.py` 守；仪表盘随合并更新 | 门禁失败即暴露 |
| **派生物重建** | `python tools/faults-build.py build` | 改 `knowledge/` 或 `faults/` 之后强制 |
| **版本发布** | `_scripts/gen-manifest.py` → tag → `release/vX.Y.Z` | 维护者手动，见 `CONTRIBUTING.md` |

## Why

传统定时沉淀的问题：
- 未经验证的知识入库 → 质量低、可能误导
- 定时器不知道何时有值得沉淀的内容 → 空跑或漏掉
- Agent 无法区分"做了一半"和"验证完成"

Hook 触发的优势：
- **质量保障**：只有验证通过的知识才入库
- **零遗漏**：每个验证事件必然触发沉淀
- **可追溯**：每条知识都关联到具体的验证场景
- **参考**：`build_in_harmonyos` 的 finish 命令 → 编译完成即沉淀
