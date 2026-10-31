#!/usr/bin/env bash
# verify.sh — 仓库自检入口（契约见 kb.yaml，实现见 verify.py）
#
#   bash _scripts/verify.sh          # 全量检查
#   bash _scripts/verify.sh --quiet  # 只输出问题
#
# 退出码：0 = PASS（可有 WARN）｜1 = FAIL（有 ERROR）
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON=python
  else
    echo "FAIL: 需要 python3 才能执行 verify（_scripts/verify.py）" >&2
    exit 1
  fi
fi

exec "$PYTHON" _scripts/verify.py "$@"
