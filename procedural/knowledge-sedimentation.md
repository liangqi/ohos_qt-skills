---
id: knowledge-sedimentation
title: "知识沉淀协议（Hook 触发）"
type: procedural
status: active
confidence: 1.0
contributors: [lzh]
sources:
  - type: experience
    name: "Trunk Flip v3.0.0 架构设计"
    date: 2026-09-07
created: 2026-09-07
updated: 2026-09-07
tags: [sedimentation, hook, protocol, automation]
refs: [qt-app-harmonyos-full-pipeline, qt-harmonyos-golden-rules]
summary: "知识沉淀的触发条件、验证事件、分类规则和操作流程 — 所有 Agent 必须遵循的通用协议"
---

# 知识沉淀协议（Hook 触发）

> **本文件是所有 Agent 的通用沉淀协议**。CLAUDE.md / AGENTS.md / .cursorrules / 其他工具配置
> 应引用本文件，而非内联复制规则。

## 核心原则

**知识沉淀由「验证事件」触发，不由定时器触发。**

完成鸿蒙化 = 知识经过实战验证 → 此时才值得沉淀。未经验证的知识不入库。

## 验证事件（Hook 触发点）

| # | 验证事件 | 触发条件 | 沉淀内容 | 目标路径 |
|---|----------|---------|---------|---------|
| 1 | **应用鸿蒙化完成** | 编译 PASS + 设备运行 PASS | 完整复盘记录 | `drafts/E{N}-<app>-porting-retro.md` |
| 2 | **编译错误解决** | 错误修复后重新编译通过 | 错误 + 原因 + 方案 | `problems/build-fail-<slug>.md` |
| 3 | **运行时问题解决** | 设备上验证修复有效 | 错误 + 原因 + 方案 | `problems/runtime-<slug>.md` |
| 4 | **API 差异发现** | 实际代码验证了差异行为 | 更新 API 映射表 | 编辑 `semantic/qt-harmonyos-api-mapping.md` |
| 5 | **平台限制确认** | 实际触发了限制 | 更新限制清单 | 编辑 `semantic/qt-harmonyos-platform-limits.md` |
| 6 | **三方库编译成功** | 交叉编译产物在设备运行正常 | 更新兼容性记录 | 编辑 `semantic/qt-harmonyos-third-party-libs.md` |

### 何时不触发

- 任务中途放弃（未验证）
- 仅理论分析未有实际代码验证
- 重复已知问题（`problems/` 已收录）

## 沉淀命令

```bash
# Hook 1: 应用鸿蒙化完成
bash _scripts/kb-sediment.sh --task "AppName" --stage done --notes "关键发现..."

# Hook 2/3: 编译/运行时错误解决
bash _scripts/kb-sediment.sh --error "完整错误信息" --solution "解决方案" --type build|runtime

# Agent 引导式（由 Agent 自行判断沉淀内容和格式）
bash _scripts/kb-sediment.sh --interactive
```

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
| **新知识**：复盘/流程/API 差异 | `drafts/E{N}-<slug>.md` | `_templates/draft.md` | 是 |

## 操作流程

```
验证事件发生
    │
    ├─ 1. 分类判断（公开 or 私有？）
    │      └─ 私有 → STOP，提醒用户
    │
    ├─ 2. 选择写入路径（problems/ or drafts/ or 编辑已有页）
    │
    ├─ 3. 写入内容（使用对应模板）
    │      └─ contributors: [MY_NAME] 从 ENV.local.md 读取
    │
    ├─ 4. 验证
    │      bash _scripts/kb-regen-indexes.sh
    │      bash _scripts/verify.sh
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

## 与 kb-bot.py 的关系

| 职责 | 负责方 | 触发方式 |
|------|--------|---------|
| **知识生成** | Agent + `kb-sediment.sh` | Hook（验证事件） |
| **PR 审核** | `kb-bot.py --job pr` | 定时轮询（10-15min） |
| **草稿 Promote** | `kb-bot.py --job merge` | 合入后自动 |
| **索引维护** | `kb-bot.py --job merge` | 合入后自动 |
| **版本发布** | `kb-bot.py --job merge` / 手动 | 合入后自动 / editor 手动 |

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
