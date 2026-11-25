#!/usr/bin/env bash
# verify.sh — repository self-check entry point (contract in kb.yaml, implementation in verify.py)
#
#   bash _scripts/verify.sh          # full check
#   bash _scripts/verify.sh --quiet  # print problems only
#
# Exit code: 0 = PASS (WARN allowed) | 1 = FAIL (has ERROR)
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
    echo "FAIL: python3 is required to run verify (_scripts/verify.py)" >&2
    exit 1
  fi
fi

exec "$PYTHON" _scripts/verify.py "$@"
