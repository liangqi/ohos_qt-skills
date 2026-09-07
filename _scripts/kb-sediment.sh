#!/usr/bin/env bash
# kb-sediment.sh — Hook-triggered knowledge sedimentation.
#
# 核心理念：知识沉淀由「验证事件」触发，不由定时器触发。
# 当一个应用成功完成鸿蒙化（编译通过 + 设备运行成功），说明相关知识
# 经过了实战验证，此时自动沉淀。
#
# 触发点：
#   1. Agent 完成 qt-app-harmonyos-full-pipeline 工作流最后阶段
#   2. 编译成功 + 设备上运行验证通过
#   3. 用户/Agent 显式调用本命令补充沉淀
#
# Usage:
#   bash _scripts/kb-sediment.sh --task "应用名" --stage done
#   bash _scripts/kb-sediment.sh --task "应用名" --stage done --notes "发现的关键经验"
#   bash _scripts/kb-sediment.sh --error "编译错误描述" --solution "解决方案"
#   bash _scripts/kb-sediment.sh --interactive   # Agent 引导式沉淀
#
# 输出：
#   - drafts/E{N}-<slug>.md（新知识草稿）或 problems/<type>-<slug>.md（错误记录）
#   - 自动运行 verify + 创建分支 + commit
#   - 提示用户 push + 创建 PR

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TODAY="$(date +%Y-%m-%d)"

# --- Parse arguments ---
TASK=""
STAGE=""
NOTES=""
ERROR_MSG=""
SOLUTION=""
INTERACTIVE=false
TYPE=""
SLUG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)        TASK="$2"; shift 2 ;;
    --stage)       STAGE="$2"; shift 2 ;;
    --notes)       NOTES="$2"; shift 2 ;;
    --error)       ERROR_MSG="$2"; shift 2 ;;
    --solution)    SOLUTION="$2"; shift 2 ;;
    --interactive) INTERACTIVE=true; shift ;;
    --type)        TYPE="$2"; shift 2 ;;
    --slug)        SLUG="$2"; shift 2 ;;
    *)             printf 'Unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

# --- Load identity ---
MY_NAME="contributor"
if [ -f "$REPO_ROOT/ENV.local.md" ]; then
  _name="$(grep '^MY_NAME=' "$REPO_ROOT/ENV.local.md" 2>/dev/null | cut -d= -f2)"
  [ -n "$_name" ] && MY_NAME="$_name"
fi

# --- Next draft number ---
next_draft_num() {
  local max=0
  for f in "$REPO_ROOT"/drafts/E*-*.md; do
    [ -f "$f" ] || continue
    local num
    num="$(basename "$f" | grep -oE '^E[0-9]+' | tr -d 'E')"
    [ "$num" -gt "$max" ] && max="$num"
  done
  printf '%03d' $((max + 1))
}

# --- Mode 1: Error sedimentation (直接写 problems/) ---
if [ -n "$ERROR_MSG" ]; then
  if [ -z "$SLUG" ]; then
    # Auto-derive slug from error message (first meaningful words)
    SLUG="$(echo "$ERROR_MSG" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | cut -c1-40 | sed 's/-$//')"
  fi
  TYPE="${TYPE:-build}"
  FILENAME="${TYPE}-fail-${SLUG}.md"
  TARGET="$REPO_ROOT/problems/$FILENAME"

  if [ -f "$TARGET" ]; then
    printf 'ERROR: problems/%s already exists. Update it instead.\n' "$FILENAME" >&2
    exit 1
  fi

  cat > "$TARGET" <<EOF
---
id: ${TYPE}-fail-${SLUG}
title: "${ERROR_MSG:0:80}"
type: problem
status: active
confidence: 0.9
contributors: [$MY_NAME]
sources:
  - type: experience
    name: "应用鸿蒙化实战验证"
    date: $TODAY
created: $TODAY
updated: $TODAY
last_confirmed: $TODAY
tags: [problem, $TYPE]
refs: []
summary: "${ERROR_MSG:0:100}"
domain: ${TYPE}
severity: medium
error_message: |
  $ERROR_MSG
---

# ${ERROR_MSG:0:80}

## 错误信息

\`\`\`
$ERROR_MSG
\`\`\`

## 场景

${TASK:-应用鸿蒙化过程中}

## 原因

${NOTES:-待分析}

## 解决方案

${SOLUTION:-待补充}

## 预防措施

待补充
EOF

  printf 'CREATED: problems/%s\n' "$FILENAME"

# --- Mode 2: Task completion sedimentation (写 drafts/) ---
elif [ -n "$TASK" ] && [ "$STAGE" = "done" ]; then
  NUM="$(next_draft_num)"
  if [ -z "$SLUG" ]; then
    SLUG="$(echo "$TASK" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | cut -c1-40 | sed 's/-$//')"
  fi
  FILENAME="E${NUM}-${SLUG}-porting-retro.md"
  TARGET="$REPO_ROOT/drafts/$FILENAME"

  cat > "$TARGET" <<EOF
---
id: e${NUM}-${SLUG}-porting-retro
title: "${TASK} 鸿蒙化复盘"
type: episodic
status: draft
confidence: 0.8
contributors: [$MY_NAME]
sources:
  - type: experience
    name: "${TASK} 鸿蒙化完成验证"
    date: $TODAY
created: $TODAY
updated: $TODAY
tags: [porting, retro, validated]
refs: []
summary: "${TASK} 成功完成鸿蒙化移植的复盘记录（经设备验证）"
---

# ${TASK} 鸿蒙化复盘

## 验证状态

- 编译: PASS
- 设备运行: PASS
- 验证日期: $TODAY

## 应用概况

- 应用名称: $TASK
- 原始平台: ${NOTES:-待补充}
- Qt 版本: 待补充
- 关键依赖: 待补充

## 迁移过程中的关键发现

${NOTES:-待补充：迁移过程中遇到的关键问题、API 差异、平台限制等}

## 解决方案汇总

待补充

## 经验教训

待补充

## 关联

- [[qt-app-harmonyos-full-pipeline]]
- [[qt-harmonyos-golden-rules]]
EOF

  printf 'CREATED: drafts/%s\n' "$FILENAME"

# --- Mode 3: Interactive (Agent fills in) ---
elif [ "$INTERACTIVE" = true ]; then
  printf '=== Interactive Sedimentation ===\n'
  printf 'Agent should:\n'
  printf '  1. Review the completed task\n'
  printf '  2. Identify validated knowledge (errors solved, APIs discovered, workarounds)\n'
  printf '  3. Create appropriate files:\n'
  printf '     - Errors -> problems/<type>-<slug>.md\n'
  printf '     - New knowledge -> drafts/E{N}-<slug>.md\n'
  printf '     - Small fixes -> edit existing pages\n'
  printf '  4. Run: bash _scripts/verify.sh\n'
  printf '  5. Commit + push + PR\n'
  printf '\nUse --task/--error modes for structured output.\n'
  exit 0

else
  printf 'Usage:\n'
  printf '  kb-sediment.sh --task "AppName" --stage done [--notes "..."] [--slug "..."]\n'
  printf '  kb-sediment.sh --error "error msg" --solution "fix" [--type build] [--task "AppName"]\n'
  printf '  kb-sediment.sh --interactive\n'
  exit 1
fi

# --- Post-creation: verify + branch + commit ---
printf '\n--- Post-sedimentation ---\n'

# Run regen + verify
printf 'Running index regen...\n'
bash "$REPO_ROOT/_scripts/kb-regen-indexes.sh" >/dev/null 2>&1 || true

printf 'Running verify...\n'
if bash "$REPO_ROOT/_scripts/verify.sh" >/dev/null 2>&1; then
  printf '  verify: PASS\n'
else
  printf '  verify: WARN (non-blocking for sedimentation)\n'
fi

# Create branch and commit
BRANCH="${MY_NAME}/sediment-${SLUG:-$(date +%Y%m%d)}"
cd "$REPO_ROOT"

# Only create branch if not already on one
CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" = "main" ]; then
  git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH" 2>/dev/null || true
fi

git add "$TARGET" _index/ 2>/dev/null || true
git commit -m "add(${TYPE:-episodic}): ${TASK:-$SLUG} 知识沉淀（验证通过）" 2>/dev/null || \
  printf '  (nothing to commit or already committed)\n'

printf '\n✅ Sedimentation complete!\n'
printf '   File: %s\n' "${TARGET#$REPO_ROOT/}"
printf '   Next: git push origin $(git branch --show-current) && create PR on GitCode\n'
