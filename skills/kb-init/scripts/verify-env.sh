#!/bin/bash
# verify-env.sh — deterministic environment verification
#
# Usage: bash skills/kb-init/scripts/verify-env.sh
# Output: a verification report (pass / fail / skip per item + an overall STATUS)
# Exit codes: 0=success (STATUS=ready or not-ready)

set -uo pipefail

# Go up three levels from scripts/ to reach the KB root
KB_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
ENV_LOCAL="$KB_ROOT/ENV.local.md"

PASS=0
FAIL=0
SKIP=0

check() {
  local name="$1"
  local result="$2"
  local detail="${3:-}"
  if [ "$result" = "pass" ]; then
    echo "  PASS: $name"
    PASS=$((PASS + 1))
  elif [ "$result" = "fail" ]; then
    echo "  FAIL: $name${detail:+ -- $detail}"
    FAIL=$((FAIL + 1))
  else
    echo "  SKIP: $name${detail:+ -- $detail}"
    SKIP=$((SKIP + 1))
  fi
}

echo "--- Environment verification ---"
echo ""

# 1. ENV.local.md exists
if [ -f "$ENV_LOCAL" ]; then
  check "ENV.local.md exists" "pass"
else
  check "ENV.local.md exists" "fail" "Run the initialization skill first to generate ENV.local.md"
  echo ""
  echo "STATUS=not-ready"
  echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
  exit 0
fi

# 2. Read paths from ENV.local.md
read_env() {
  local key="$1"
  grep -E "^\| \`${key}\`" "$ENV_LOCAL" 2>/dev/null | sed 's/.*| `\([^`]*\)` |$/\1/' | head -1
}

DEVECO_PATH=$(read_env "DEVECO_PATH")
QT5_12_SRC=$(read_env "QT5_12_SRC")
QT5_15_SRC=$(read_env "QT5_15_SRC")
QT_BUILD_ROOT=$(read_env "QT_BUILD_ROOT")
QT5_12_OHOS_SDK=$(read_env "QT5_12_OHOS_SDK")
QT5_15_OHOS_SDK=$(read_env "QT5_15_OHOS_SDK")
OHOS_SDK_NATIVE=$(read_env "OHOS_SDK_NATIVE")

# 3. DevEco Studio
if [ -n "$DEVECO_PATH" ] && [ -d "$DEVECO_PATH" ]; then
  check "DevEco Studio path" "pass" "$DEVECO_PATH"
elif [ -n "$DEVECO_PATH" ]; then
  check "DevEco Studio path" "fail" "Path does not exist: $DEVECO_PATH"
else
  check "DevEco Studio path" "fail" "Not configured"
fi

# 4. OHOS SDK native
if [ -n "$OHOS_SDK_NATIVE" ] && [ -d "$OHOS_SDK_NATIVE" ]; then
  check "OHOS SDK native" "pass" "$OHOS_SDK_NATIVE"
  if [ -f "$OHOS_SDK_NATIVE/llvm/bin/clang" ] || [ -f "$OHOS_SDK_NATIVE/llvm/bin/clang.exe" ]; then
    check "OHOS clang compiler" "pass"
  else
    check "OHOS clang compiler" "fail" "llvm/bin/clang does not exist"
  fi
  if [ -d "$OHOS_SDK_NATIVE/sysroot" ]; then
    check "OHOS sysroot" "pass"
  else
    check "OHOS sysroot" "fail" "The sysroot directory does not exist"
  fi
elif [ -n "$OHOS_SDK_NATIVE" ]; then
  check "OHOS SDK native" "fail" "Path does not exist: $OHOS_SDK_NATIVE"
else
  check "OHOS SDK native" "fail" "Not configured"
fi

# 5. Qt OHOS SDK (at least one version must be configured)
QT_SDK_COUNT=0
if [ -n "$QT5_12_OHOS_SDK" ] && [ -d "$QT5_12_OHOS_SDK" ]; then
  check "Qt 5.12 OHOS SDK" "pass" "$QT5_12_OHOS_SDK"
  QT_SDK_COUNT=$((QT_SDK_COUNT + 1))
elif [ -n "$QT5_12_OHOS_SDK" ]; then
  check "Qt 5.12 OHOS SDK" "fail" "Path does not exist: $QT5_12_OHOS_SDK"
else
  check "Qt 5.12 OHOS SDK" "skip" "Not configured"
fi

if [ -n "$QT5_15_OHOS_SDK" ] && [ -d "$QT5_15_OHOS_SDK" ]; then
  check "Qt 5.15 OHOS SDK" "pass" "$QT5_15_OHOS_SDK"
  QT_SDK_COUNT=$((QT_SDK_COUNT + 1))
elif [ -n "$QT5_15_OHOS_SDK" ]; then
  check "Qt 5.15 OHOS SDK" "fail" "Path does not exist: $QT5_15_OHOS_SDK"
else
  check "Qt 5.15 OHOS SDK" "skip" "Not configured"
fi

if [ "$QT_SDK_COUNT" -eq 0 ]; then
  check "Qt OHOS SDK (at least one version)" "fail" "No Qt OHOS SDK is configured"
fi

# 6. Base tools
if command -v git &>/dev/null; then
  check "git" "pass" "$(git --version 2>/dev/null | head -1)"
else
  check "git" "fail" "Not installed"
fi

if command -v cmake &>/dev/null; then
  check "cmake" "pass" "$(cmake --version 2>/dev/null | head -1)"
else
  check "cmake" "fail" "Not installed (brew install cmake, or https://cmake.org/download/)"
fi

if command -v hdc &>/dev/null; then
  check "hdc" "pass"
else
  check "hdc" "skip" "Not on PATH (usually included in the DevEco SDK; used for device debugging)"
fi

# 7. Qt source (optional; only needed when building the framework)
if [ -n "$QT5_12_SRC" ] && [ -d "$QT5_12_SRC" ]; then
  check "Qt 5.12 source" "pass" "$QT5_12_SRC"
elif [ -n "$QT5_12_SRC" ]; then
  check "Qt 5.12 source" "fail" "Path does not exist: $QT5_12_SRC"
else
  check "Qt 5.12 source" "skip" "Not configured (only needed when building the Qt framework)"
fi

if [ -n "$QT5_15_SRC" ] && [ -d "$QT5_15_SRC" ]; then
  check "Qt 5.15 source" "pass" "$QT5_15_SRC"
elif [ -n "$QT5_15_SRC" ]; then
  check "Qt 5.15 source" "fail" "Path does not exist: $QT5_15_SRC"
else
  check "Qt 5.15 source" "skip" "Not configured (only needed when building the Qt framework)"
fi

echo ""
echo "--- Verification results ---"
echo "  PASS: $PASS  FAIL: $FAIL  SKIP: $SKIP"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo "STATUS=ready"
  echo ""
  echo "The environment is ready; you can start using the Qt for HarmonyOS knowledge base to port applications."
else
  echo "STATUS=not-ready"
  echo ""
  echo "The environment is not ready. Fix the FAIL items above and run the verification again."
fi
