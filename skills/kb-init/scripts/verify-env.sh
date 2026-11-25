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

# path_exists — dual-form path check: ENV.local.md may record a Windows drive-letter path (C:\Qt\...)
# or a WSL POSIX path (/mnt/c/...); the bash environment running this script only understands one of them,
# so check the path as-is first, then convert a drive-letter path into the /mnt/<drive>/ form and retry.
path_exists() {
  local p="$1"
  [ -d "$p" ] && return 0
  case "$p" in
    [A-Za-z]:\\*|[A-Za-z]:/*)
      local drive rest
      drive=$(printf '%s' "${p:0:1}" | tr 'A-Z' 'a-z')
      rest=$(printf '%s' "${p:2}" | tr '\\' '/')
      [ -d "/mnt/$drive$rest" ] && return 0
      ;;
  esac
  return 1
}

# path_variants — the two spellings of the same path under the current bash (as-is / /mnt/<drive>/...).
# Use it for file-level checks: path_exists only recognizes directories, while here we're checking specific files in the kit.
path_variants() {
  printf '%s\n' "$1"
  case "$1" in
    [A-Za-z]:\\*|[A-Za-z]:/*)
      local drive rest
      drive=$(printf '%s' "${1:0:1}" | tr 'A-Z' 'a-z')
      rest=$(printf '%s' "${1:2}" | tr '\\' '/')
      printf '%s\n' "/mnt/$drive$rest"
      ;;
  esac
}

first_existing() {
  local p
  while IFS= read -r p; do
    [ -e "$p" ] && { printf '%s\n' "$p"; return 0; }
  done < <(path_variants "$1")
  return 1
}

# qt_kit_probe <display name> <kit root> <relative path> <consequence if missing>
# A Qt6 kit being "installed" doesn't mean it's "usable": when the toolchain / QPA plugin is missing, both the build
# and the runtime fail very late (configure exits outright, or "QPA plugin not found" after installing on the device); this moves the check earlier.
qt_kit_probe() {
  local label="$1" base="$2" rel="$3" consequence="$4" required="${5:-fail}"
  if [ -z "$base" ]; then
    check "$label" "skip" "Not configured"
  elif first_existing "$base/$rel" >/dev/null; then
    check "$label" "pass" "$rel"
  else
    check "$label" "$required" "Missing $rel -- $consequence"
  fi
}

DEVECO_PATH=$(read_env "DEVECO_PATH")
QT5_12_SRC=$(read_env "QT5_12_SRC")
QT5_15_SRC=$(read_env "QT5_15_SRC")
QT_BUILD_ROOT=$(read_env "QT_BUILD_ROOT")
QT5_12_OHOS_SDK=$(read_env "QT5_12_OHOS_SDK")
QT5_15_OHOS_SDK=$(read_env "QT5_15_OHOS_SDK")
QT6_OHOS_SDK=$(read_env "QT6_OHOS_SDK")
QT6_HOST_SDK=$(read_env "QT6_HOST_SDK")
OHOS_SDK_NATIVE=$(read_env "OHOS_SDK_NATIVE")
OHOS_TEMPLATE_SRC=$(read_env "OHOS_TEMPLATE_SRC")

# 3. DevEco Studio
if [ -n "$DEVECO_PATH" ] && path_exists "$DEVECO_PATH"; then
  check "DevEco Studio path" "pass" "$DEVECO_PATH"
elif [ -n "$DEVECO_PATH" ]; then
  check "DevEco Studio path" "fail" "Path does not exist: $DEVECO_PATH"
else
  check "DevEco Studio path" "fail" "Not configured"
fi

# 4. OHOS SDK native
if [ -n "$OHOS_SDK_NATIVE" ] && path_exists "$OHOS_SDK_NATIVE"; then
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
if [ -n "$QT5_12_OHOS_SDK" ] && path_exists "$QT5_12_OHOS_SDK"; then
  check "Qt 5.12 OHOS SDK" "pass" "$QT5_12_OHOS_SDK"
  QT_SDK_COUNT=$((QT_SDK_COUNT + 1))
elif [ -n "$QT5_12_OHOS_SDK" ]; then
  check "Qt 5.12 OHOS SDK" "fail" "Path does not exist: $QT5_12_OHOS_SDK"
else
  check "Qt 5.12 OHOS SDK" "skip" "Not configured"
fi

if [ -n "$QT5_15_OHOS_SDK" ] && path_exists "$QT5_15_OHOS_SDK"; then
  check "Qt 5.15 OHOS SDK" "pass" "$QT5_15_OHOS_SDK"
  QT_SDK_COUNT=$((QT_SDK_COUNT + 1))
elif [ -n "$QT5_15_OHOS_SDK" ]; then
  check "Qt 5.15 OHOS SDK" "fail" "Path does not exist: $QT5_15_OHOS_SDK"
else
  check "Qt 5.15 OHOS SDK" "skip" "Not configured"
fi

if [ -n "$QT6_OHOS_SDK" ] && path_exists "$QT6_OHOS_SDK"; then
  check "Qt 6 OHOS SDK" "pass" "$QT6_OHOS_SDK"
  QT_SDK_COUNT=$((QT_SDK_COUNT + 1))
  qt_kit_probe "Qt 6 kit lib directory" "$QT6_OHOS_SDK" "lib" "probably not a complete kit"
  qt_kit_probe "Qt 6 kit toolchain" "$QT6_OHOS_SDK" \
    "lib/cmake/Qt6/qt.toolchain.cmake" "cross-configuration can't start (CMAKE_TOOLCHAIN_FILE has nothing to point to)"
  qt_kit_probe "Qt 6 kit QPA plugin" "$QT6_OHOS_SDK" \
    "plugins/platforms/libqohos.so" "QPA plugin not found after installing on the device"
  qt_kit_probe "Qt 6 kit Qt6Config" "$QT6_OHOS_SDK" \
    "lib/cmake/Qt6/Qt6Config.cmake" "find_package(Qt6) can't resolve it"
  qt_kit_probe "Qt 6 kit mkspec" "$QT6_OHOS_SDK" \
    "mkspecs/ohos-clang/qmake.conf" "the qmake path is unusable (qt-cmake still works)" "skip"
elif [ -n "$QT6_OHOS_SDK" ]; then
  check "Qt 6 OHOS SDK" "fail" "Path does not exist: $QT6_OHOS_SDK"
else
  check "Qt 6 OHOS SDK" "skip" "Not configured"
fi

if [ -n "$QT6_HOST_SDK" ] && path_exists "$QT6_HOST_SDK"; then
  check "Qt 6 host toolchain" "pass" "$QT6_HOST_SDK"
  # Pointing QT_HOST_PATH at the right directory isn't enough: missing any of moc/rcc/uic/harmonydeployqt6 means you can't build/package
  for tool in moc rcc uic harmonydeployqt6; do
    if first_existing "$QT6_HOST_SDK/bin/$tool.exe" >/dev/null || \
       first_existing "$QT6_HOST_SDK/bin/$tool" >/dev/null; then
      check "Qt 6 host $tool" "pass"
    else
      check "Qt 6 host $tool" "fail" "The host kit is missing bin/$tool -- a correct QT_HOST_PATH doesn't help"
    fi
  done
elif [ -n "$QT6_HOST_SDK" ]; then
  check "Qt 6 host toolchain" "fail" "Path does not exist: $QT6_HOST_SDK"
else
  check "Qt 6 host toolchain" "skip" "Not configured"
fi

if [ "$QT_SDK_COUNT" -eq 0 ]; then
  check "Qt OHOS SDK (at least one version)" "fail" "No Qt OHOS SDK is configured"
fi

# 5b. Shell-project template availability (used for automatic generation by qt-ohos-run migrate)
if { [ -n "$OHOS_TEMPLATE_SRC" ] && path_exists "$OHOS_TEMPLATE_SRC"; } || \
   [ -d "$KB_ROOT/templates/qt-ohos-app/entry" ]; then
  check "Shell-project template" "pass" "${OHOS_TEMPLATE_SRC:-built-in KB templates/qt-ohos-app}"
else
  check "Shell-project template" "skip" "Not configured (migrate will fall back to assisted mode; you can run download-template.sh)"
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

if command -v devecocli &>/dev/null; then
  check "devecocli" "pass"
else
  check "devecocli" "skip" "Not on PATH (install it with install-deveco-cli.sh; prefer devecocli for building/installing on the device)"
fi

if command -v gitleaks &>/dev/null; then
  check "gitleaks (8.30.1)" "pass" "$(gitleaks version 2>/dev/null | head -1)"
else
  check "gitleaks (8.30.1)" "skip" "Not installed (the release gate's secrets scan depends on it; skip for personal use)"
fi

# 7. Qt source (optional; only needed when building the framework)
if [ -n "$QT5_12_SRC" ] && path_exists "$QT5_12_SRC"; then
  check "Qt 5.12 source" "pass" "$QT5_12_SRC"
elif [ -n "$QT5_12_SRC" ]; then
  check "Qt 5.12 source" "fail" "Path does not exist: $QT5_12_SRC"
else
  check "Qt 5.12 source" "skip" "Not configured (only needed when building the Qt framework)"
fi

if [ -n "$QT5_15_SRC" ] && path_exists "$QT5_15_SRC"; then
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
