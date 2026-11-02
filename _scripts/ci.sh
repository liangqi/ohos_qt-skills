#!/usr/bin/env bash
# 仓库门禁 —— 薄壳：真正干活的是 _scripts/ci.py（纯 Python，Windows 无 bash 也能跑）。
#
#   bash _scripts/ci.sh
#   python _scripts/ci.py          # 等价，推荐 Windows 用这条
#
# 退出码 0 = 全部通过；非 0 = 有门禁失败。

set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || PY=python
exec "$PY" _scripts/ci.py "$@"
