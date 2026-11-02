#!/usr/bin/env bash
# 一条命令跑完仓库门禁。供 GitCode / GitHub / Jenkins / 本地 pre-push 直接调用。
#
#   bash _scripts/ci.sh
#
# 退出码 0 = 全部通过；非 0 = 有门禁失败（CI 直接据此判红）。
# Windows 无 bash 时按顺序执行注释里的等价命令即可。

set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || PY=python

echo "== 1/4 仓库自检（契约/结构/引用/索引/发版清单/卫生，10 类） =="
"$PY" _scripts/verify.py

echo
echo "== 2/4 故障库真源 ↔ 派生物 =="
"$PY" tools/faults-build.py check

echo
echo "== 3/4 用例（一致性 + 引擎 + 扫描） =="
"$PY" -m unittest discover -s tests

echo
echo "== 4/4 CLI 冒烟（--help 全部 exit 0） =="
"$PY" tools/qt-ohos-run.py --help >/dev/null
"$PY" tools/qt-sdk-run.py --help >/dev/null
"$PY" tools/faults-build.py --help >/dev/null
"$PY" tools/cpp20-gap-scan.py --help >/dev/null
"$PY" tools/kb-cef-graft.py --help >/dev/null
"$PY" portgraph/portgraph.py --help >/dev/null

# 注：发版清单在非发版提交上必然是"快照"，不参与 CI 判定；
# 只在发版流程里用 `python _scripts/gen-manifest.py --check` 对账。

echo
echo "CI: 全部通过"
