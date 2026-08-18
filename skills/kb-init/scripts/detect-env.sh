#!/bin/bash
# detect-env.sh — 确定性环境检测
# 扫描已安装的工具、SDK、Qt 源码，输出结构化结果（key=value 格式）
#
# 用法: bash skills/kb-init/scripts/detect-env.sh
# 输出: key=value 格式，每行一个检测结果
# 退出码: 0=成功

set -uo pipefail

# 从 scripts/ 向上三级到 KB root: scripts/ → kb-init/ → skills/ → KB root
KB_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════
detect_os() {
  case "$(uname -s)" in
    Darwin*) echo "macos";;
    Linux*)  echo "linux";;
    MINGW*|MSYS*|CYGWIN*) echo "windows";;
    *) echo "unknown";;
  esac
}

cmd_exists() { command -v "$1" &>/dev/null && echo "true" || echo "false"; }

cmd_version() {
  local cmd="$1"
  shift
  if command -v "$cmd" &>/dev/null; then
    "$cmd" "$@" 2>/dev/null | head -1
  else
    echo ""
  fi
}

# ═══════════════════════════════════════════════════════════
# 1. 操作系统
# ═══════════════════════════════════════════════════════════
OS=$(detect_os)
echo "OS=$OS"

# 架构
ARCH="$(uname -m)"
echo "ARCH=$ARCH"

# ═══════════════════════════════════════════════════════════
# 2. DevEco Studio + HarmonyOS SDK
# ═══════════════════════════════════════════════════════════
DEVECO_PATH=""
DEVECO_FOUND="false"
DEVECO_VERSION=""
OHOS_SDK_NATIVE_PATH=""
OHOS_SDK_NATIVE_FOUND="false"
HDC_PATH=""
HDC_FOUND="false"
OHPM_FOUND="false"
HVIGORW_FOUND="false"
NODE_FOUND=$(cmd_exists node)
NODE_VERSION=$(cmd_version node --version)
JDK_FOUND=$(cmd_exists java)
JDK_VERSION=""
if [ "$JDK_FOUND" = "true" ]; then
  JDK_VERSION=$(java -version 2>&1 | head -1)
fi

if [ "$OS" = "macos" ]; then
  for p in "/Applications/DevEco-Studio.app" "$HOME/Applications/DevEco-Studio.app"; do
    if [ -d "$p" ]; then DEVECO_PATH="$p"; DEVECO_FOUND="true"; break; fi
  done
  if [ "$DEVECO_FOUND" = "true" ]; then
    _native="$DEVECO_PATH/Contents/sdk/default/openharmony/native"
    [ -d "$_native" ] && OHOS_SDK_NATIVE_PATH="$_native" && OHOS_SDK_NATIVE_FOUND="true"
    _hdc="$DEVECO_PATH/Contents/sdk/default/openharmony/toolchains/hdc"
    [ -f "$_hdc" ] && HDC_PATH="$_hdc" && HDC_FOUND="true"
    _ohpm="$DEVECO_PATH/Contents/sdk/default/openharmony/ohpm/bin/ohpm"
    [ -f "$_ohpm" ] && OHPM_FOUND="true"
    _hvigor="$DEVECO_PATH/Contents/tools/hvigor/bin/hvigorw.js"
    [ -f "$_hvigor" ] && HVIGORW_FOUND="true"
    # 尝试读取 DevEco 版本
    _pkg="$DEVECO_PATH/Contents/Resources/app/package.json"
    [ -f "$_pkg" ] && DEVECO_VERSION=$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$_pkg" 2>/dev/null | head -1 | sed 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
  fi
elif [ "$OS" = "windows" ]; then
  for p in "/c/Program Files/Huawei/DevEco Studio" "/c/Program Files (x86)/Huawei/DevEco Studio" "$LOCALAPPDATA/Programs/DevEco Studio" "/d/DevEco Studio" "/e/DevEco Studio"; do
    if [ -d "$p" ]; then DEVECO_PATH="$p"; DEVECO_FOUND="true"; break; fi
  done
  if [ "$DEVECO_FOUND" = "true" ]; then
    _native="$DEVECO_PATH/sdk/default/openharmony/native"
    [ -d "$_native" ] && OHOS_SDK_NATIVE_PATH="$_native" && OHOS_SDK_NATIVE_FOUND="true"
    _hdc="$DEVECO_PATH/sdk/default/openharmony/toolchains/hdc.exe"
    [ -f "$_hdc" ] && HDC_PATH="$_hdc" && HDC_FOUND="true"
    _ohpm="$DEVECO_PATH/sdk/default/openharmony/ohpm/bin/ohpm"
    [ -f "$_ohpm" ] && OHPM_FOUND="true"
    _hvigor="$DEVECO_PATH/tools/hvigor/bin/hvigorw.js"
    [ -f "$_hvigor" ] && HVIGORW_FOUND="true"
  fi
elif [ "$OS" = "linux" ]; then
  for p in "$HOME/deveco-studio" "/opt/deveco-studio" "$HOME/DevEco-Studio" "$HOME/dev/deveco-studio"; do
    if [ -d "$p" ]; then DEVECO_PATH="$p"; DEVECO_FOUND="true"; break; fi
  done
  if [ "$DEVECO_FOUND" = "true" ]; then
    _native="$DEVECO_PATH/sdk/default/openharmony/native"
    [ -d "$_native" ] && OHOS_SDK_NATIVE_PATH="$_native" && OHOS_SDK_NATIVE_FOUND="true"
  fi
fi

# hdc 也可能在 PATH 中
if [ "$HDC_FOUND" = "false" ]; then
  HDC_FOUND=$(cmd_exists hdc)
  [ "$HDC_FOUND" = "true" ] && HDC_PATH="$(command -v hdc)"
fi

echo "DEVECO_FOUND=$DEVECO_FOUND"
echo "DEVECO_PATH=$DEVECO_PATH"
echo "DEVECO_VERSION=$DEVECO_VERSION"
echo "OHOS_SDK_NATIVE_FOUND=$OHOS_SDK_NATIVE_FOUND"
echo "OHOS_SDK_NATIVE_PATH=$OHOS_SDK_NATIVE_PATH"
echo "HDC_FOUND=$HDC_FOUND"
echo "HDC_PATH=$HDC_PATH"
echo "OHPM_FOUND=$OHPM_FOUND"
echo "HVIGORW_FOUND=$HVIGORW_FOUND"
echo "NODE_FOUND=$NODE_FOUND"
echo "NODE_VERSION=$NODE_VERSION"
echo "JDK_FOUND=$JDK_FOUND"
echo "JDK_VERSION=$JDK_VERSION"

# ═══════════════════════════════════════════════════════════
# 3. 基础工具链
# ═══════════════════════════════════════════════════════════
GIT_FOUND=$(cmd_exists git)
GIT_VERSION=$(cmd_version git --version)
CMAKE_FOUND=$(cmd_exists cmake)
CMAKE_VERSION=$(cmd_version cmake --version)

echo "GIT_FOUND=$GIT_FOUND"
echo "GIT_VERSION=$GIT_VERSION"
echo "CMAKE_FOUND=$CMAKE_FOUND"
echo "CMAKE_VERSION=$CMAKE_VERSION"

# ═══════════════════════════════════════════════════════════
# 4. 平台特定工具
# ═══════════════════════════════════════════════════════════
# Windows: MinGW + Strawberry Perl + PowerShell
MINGW_FOUND="false"
MINGW_PATH=""
PERL_FOUND="false"
PERL_PATH=""
POWERSHELL_FOUND="false"
XCODE_CLT_FOUND="false"

if [ "$OS" = "windows" ]; then
  MINGW_FOUND=$(cmd_exists mingw32-make)
  [ "$MINGW_FOUND" = "true" ] && MINGW_PATH="$(dirname "$(command -v mingw32-make)")"
  # Strawberry Perl
  for p in "/c/Strawberry" "C:/Strawberry"; do
    if [ -d "$p" ]; then PERL_FOUND="true"; PERL_PATH="$p"; break; fi
  done
  if [ "$PERL_FOUND" = "false" ]; then
    PERL_FOUND=$(cmd_exists perl)
    [ "$PERL_FOUND" = "true" ] && PERL_PATH="$(dirname "$(dirname "$(command -v perl)")")"
  fi
  # PowerShell
  POWERSHELL_FOUND=$(cmd_exists powershell.exe 2>/dev/null || cmd_exists pwsh 2>/dev/null || echo "false")
elif [ "$OS" = "macos" ]; then
  # Xcode Command Line Tools
  if xcode-select -p &>/dev/null; then
    XCODE_CLT_FOUND="true"
  fi
fi

echo "MINGW_FOUND=$MINGW_FOUND"
echo "MINGW_PATH=$MINGW_PATH"
echo "PERL_FOUND=$PERL_FOUND"
echo "PERL_PATH=$PERL_PATH"
echo "POWERSHELL_FOUND=$POWERSHELL_FOUND"
echo "XCODE_CLT_FOUND=$XCODE_CLT_FOUND"

# ═══════════════════════════════════════════════════════════
# 5. Qt 源码检测
# ═══════════════════════════════════════════════════════════
QT5_12_SRC_FOUND="false"
QT5_12_SRC_PATH=""
QT5_15_SRC_FOUND="false"
QT5_15_SRC_PATH=""

for base in "$KB_ROOT/workspace/qt-src" "$HOME/qt-src" "$HOME/qt" "$HOME/dev/qt" "/opt/qt-src" "/d/qt-src" "/e/qt-src"; do
  if [ -d "$base/qt5.12/qtbase" ]; then
    QT5_12_SRC_FOUND="true"
    QT5_12_SRC_PATH="$base/qt5.12"
  fi
  if [ -d "$base/qt5.15/qtbase" ]; then
    QT5_15_SRC_FOUND="true"
    QT5_15_SRC_PATH="$base/qt5.15"
  fi
done
echo "QT5_12_SRC_FOUND=$QT5_12_SRC_FOUND"
echo "QT5_12_SRC_PATH=$QT5_12_SRC_PATH"
echo "QT5_15_SRC_FOUND=$QT5_15_SRC_FOUND"
echo "QT5_15_SRC_PATH=$QT5_15_SRC_PATH"

# ═══════════════════════════════════════════════════════════
# 6. Qt OHOS SDK 检测
# ═══════════════════════════════════════════════════════════
QT5_12_SDK_FOUND="false"
QT5_12_OHOS_SDK_PATH=""
QT5_15_SDK_FOUND="false"
QT5_15_OHOS_SDK_PATH=""

for base in "$KB_ROOT/workspace/qt-sdk" "$HOME/qt-sdk" "$HOME/dev/qt-sdk" "/opt/qt-sdk" "/d/qt-sdk" "/e/qt-sdk"; do
  for d in "$base"/Qt5.12*; do
    if [ -d "$d" ]; then QT5_12_SDK_FOUND="true"; QT5_12_OHOS_SDK_PATH="$d"; break; fi
  done
  for d in "$base"/Qt5.15*; do
    if [ -d "$d" ]; then QT5_15_SDK_FOUND="true"; QT5_15_OHOS_SDK_PATH="$d"; break; fi
  done
done
echo "QT5_12_SDK_FOUND=$QT5_12_SDK_FOUND"
echo "QT5_12_OHOS_SDK_PATH=$QT5_12_OHOS_SDK_PATH"
echo "QT5_15_SDK_FOUND=$QT5_15_SDK_FOUND"
echo "QT5_15_OHOS_SDK_PATH=$QT5_15_OHOS_SDK_PATH"

# ═══════════════════════════════════════════════════════════
# 7. ENV.local.md 状态
# ═══════════════════════════════════════════════════════════
ENV_LOCAL_EXISTS="false"
[ -f "$KB_ROOT/ENV.local.md" ] && ENV_LOCAL_EXISTS="true"
echo "ENV_LOCAL_EXISTS=$ENV_LOCAL_EXISTS"

# ═══════════════════════════════════════════════════════════
# 8. 就绪度快速判断（供 Agent 参考）
# ═══════════════════════════════════════════════════════════
# 应用开发者最低要求：DevEco + OHOS SDK native + 至少一个 Qt SDK
APP_READY="true"
[ "$DEVECO_FOUND" = "false" ] && APP_READY="false"
[ "$OHOS_SDK_NATIVE_FOUND" = "false" ] && APP_READY="false"
[ "$QT5_12_SDK_FOUND" = "false" ] && [ "$QT5_15_SDK_FOUND" = "false" ] && APP_READY="false"
echo "APP_DEVELOPER_READY=$APP_READY"

# 框架开发者最低要求：上述 + Qt 源码 + cmake + (Windows: MinGW + Perl)
FW_READY="$APP_READY"
[ "$QT5_12_SRC_FOUND" = "false" ] && [ "$QT5_15_SRC_FOUND" = "false" ] && FW_READY="false"
[ "$CMAKE_FOUND" = "false" ] && FW_READY="false"
if [ "$OS" = "windows" ]; then
  [ "$MINGW_FOUND" = "false" ] && FW_READY="false"
  [ "$PERL_FOUND" = "false" ] && FW_READY="false"
fi
echo "FRAMEWORK_DEVELOPER_READY=$FW_READY"
