#!/usr/bin/env bash
# verify.sh - Public verification interface for ohos_qt-skills (canonical trunk).
# Tooling contract: 2.
# Usage: bash _scripts/verify.sh
# Exit: 0 = PASS (may contain WARN), 1 = FAIL

set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTRACT="$REPO_ROOT/kb.yaml"

contract_value() {
  awk -F: -v key="$1" '$1 == key { sub(/^[^:]*:[[:space:]]*/, ""); print; exit }' "$CONTRACT"
}

require_contract_value() {
  local contract_key="$1" expected_value="$2"
  local actual_value
  actual_value="$(contract_value "$contract_key")"
  if [ "$actual_value" != "$expected_value" ]; then
    printf 'FAIL: kb.yaml %s must be %s, found %s\n' "$contract_key" "$expected_value" "${actual_value:-missing}" >&2
    exit 1
  fi
}

# --- Contract validation ---
if [ ! -f "$CONTRACT" ]; then
  printf 'FAIL: missing kb.yaml\n' >&2
  exit 1
fi

require_contract_value schema_version 1
require_contract_value id ohos-qt-kb
require_contract_value kind framework
require_contract_value entrypoint AGENTS.md
require_contract_value map _index/_map.md
require_contract_value verify 'bash _scripts/verify.sh'
require_contract_value tooling_contract_version 2

# --- AGENTS.md == CLAUDE.md sync check ---
if ! cmp -s "$REPO_ROOT/AGENTS.md" "$REPO_ROOT/CLAUDE.md"; then
  printf 'FAIL: AGENTS.md and CLAUDE.md differ; they must be identical\n' >&2
  exit 1
fi

# --- Bash version check ---
MODERN_BASH=''
if [ "${BASH_VERSINFO[0]}" -ge 4 ]; then
  MODERN_BASH="$BASH"
elif [ -x /opt/homebrew/bin/bash ] && /opt/homebrew/bin/bash -c 'test "${BASH_VERSINFO[0]}" -ge 4'; then
  MODERN_BASH=/opt/homebrew/bin/bash
elif command -v bash >/dev/null 2>&1 && bash -c 'test "${BASH_VERSINFO[0]}" -ge 4'; then
  MODERN_BASH="$(command -v bash)"
else
  printf 'FAIL: Bash >=4 is required for index regeneration and gate checks\n' >&2
  exit 1
fi

# --- Secret scan (optional: warn if gitleaks not available) ---
if command -v gitleaks >/dev/null 2>&1; then
  if [ -f "$REPO_ROOT/_scripts/verify-secrets.sh" ]; then
    bash "$REPO_ROOT/_scripts/verify-secrets.sh"
  fi
else
  printf 'WARN: gitleaks not found; secret scan skipped (install: https://github.com/gitleaks/gitleaks)\n' >&2
fi

# --- Index regeneration ---
"$MODERN_BASH" "$REPO_ROOT/_scripts/kb-regen-indexes.sh"

# --- Consistency gate ---
"$MODERN_BASH" "$REPO_ROOT/_scripts/kb-gate.sh"

printf '\nPASS: ohos_qt-skills verification completed\n'
