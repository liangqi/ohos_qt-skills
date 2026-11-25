#!/usr/bin/env bash
# Repository gate -- thin wrapper: the real work is done by _scripts/ci.py (pure Python, runs on Windows without bash).
#
#   bash _scripts/ci.sh
#   python _scripts/ci.py          # equivalent; recommended on Windows
#
# Exit code 0 = all passed; non-zero = a gate failed.

set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || PY=python
exec "$PY" _scripts/ci.py "$@"
