#!/bin/bash
# detect-env.sh — 确定性环境检测
# 扫描已安装的工具、SDK、Qt 源码，输出结构化结果（key=value 格式）
#
# 用法: bash skills/kb-init/scripts/detect-env.sh
# 输出: key=value 格式，每行一个检测结果
# 退出码: 0=成功

set -uo pipefail

KB_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# 操作系统检测
detect_os() {
  case "$(uname -s)" in
    Darwin*) echo "macos";;
    Linux*)  echo "linux";;
    MINGW*|MSYS*|CYGWIN*) echo "windows";;
    *) echo "unknown";;
  esac
}

# 命令是否可用
cmd_exists() { command -v "$1" &>/dev/null && echo "true" || echo "false"; }

# 路径是否存在且为目录
dir_exists() { [ -d "$1" ] && echo "true" || echo "false"; }

# 在常见路径中查找工具
find_tool() {
  local name="$1"
  shift
  local path
  for path in "$@"; do
    if [ -d "$path" ]; then
      echo "$path"
      return 0
    fi
  done
  echo ""
  return 1
}

OS=$(detect_os)
echo "OS=$OS"

# DevEco Studio 检测
DEVECO_PATH=""
DEVECO_FOUND="false"
if [ "$OS" = "macos" ]; then
  if [ -d "/Applications/DevEco-Studio.app" ]; then
    DEVECO_PATH="/Applications/DevEco-Studio.app"
    DEVECO_FOUND="true"
  fi
elif [ "$OS" = "windows" ]; then
  for p in "/c/Program Files/Huawei/DevEco Studio" "/c/Program Files (x86)/Huawei/DevEco Studio" "$LOCALAPPDATA/Programs/DevEco Studio"; do
    if [ -d "$p" ]; then DEVECO_PATH="$p"; DEVECO_FOUND="true"; break; fi
  done
elif [ "$OS" = "linux" ]; then
  for p in "$HOME/deveco-studio" "/opt/deveco-studio" "$HOME/DevEco-Studio"; do
    if [ -d "$p" ]; then DEVECO_PATH="$p"; DEVECO_FOUND="true"; break; fi
  done
fi
echo "DEVECO_FOUND=$DEVECO_FOUND"
echo "DEVECO_PATH=$DEVECO_PATH"

# hdc 检测
HDC_FOUND=$(cmd_exists hdc)
echo "HDC_FOUND=$HDC_FOUND"

# git 检测
GIT_FOUND=$(cmd_exists git)
echo "GIT_FOUND=$GIT_FOUND"

# cmake 检测
CMAKE_FOUND=$(cmd_exists cmake)
echo "CMAKE_FOUND=$CMAKE_FOUND"

# MinGW 检测（仅 Windows）
MINGW_FOUND="false"
MINGW_PATH=""
if [ "$OS" = "windows" ]; then
  MINGW_FOUND=$(cmd_exists mingw32-make)
  if [ "$MINGW_FOUND" = "true" ]; then
    MINGW_PATH="$(dirname "$(command -v mingw32-make)")"
  fi
fi
echo "MINGW_FOUND=$MINGW_FOUND"
echo "MINGW_PATH=$MINGW_PATH"

# Strawberry Perl 检测（仅 Windows）
PERL_FOUND="false"
PERL_PATH=""
if [ "$OS" = "windows" ]; then
  for p in "/c/Strawberry" "C:/Strawberry"; do
    if [ -d "$p" ]; then PERL_FOUND="true"; PERL_PATH="$p"; break; fi
  done
  if [ "$PERL_FOUND" = "false" ]; then
    PERL_FOUND=$(cmd_exists perl)
    if [ "$PERL_FOUND" = "true" ]; then
      PERL_PATH="$(dirname "$(dirname "$(command -v perl)")")"
    fi
  fi
fi
echo "PERL_FOUND=$PERL_FOUND"
echo "PERL_PATH=$PERL_PATH"

# Qt 源码检测
QT5_12_SRC_FOUND="false"
QT5_12_SRC_PATH=""
QT5_15_SRC_FOUND="false"
QT5_15_SRC_PATH=""

# 在常见路径中查找 Qt 源码
for base in "$KB_ROOT/workspace/qt-src" "$HOME/qt-src" "$HOME/qt" "/opt/qt-src"; do
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

# Qt OHOS SDK 检测
QT5_12_SDK_FOUND="false"
QT5_12_OHOS_SDK_PATH=""
QT5_15_SDK_FOUND="false"
QT5_15_OHOS_SDK_PATH=""

for base in "$KB_ROOT/workspace/qt-sdk" "$HOME/qt-sdk" "/opt/qt-sdk"; do
  if [ -d "$base/Qt5.12.12-arm64-v8a" ]; then
    QT5_12_SDK_FOUND="true"
    QT5_12_OHOS_SDK_PATH="$base/Qt5.12.12-arm64-v8a"
  fi
  if [ -d "$base/Qt5.15.16-arm64-v8a" ]; then
    QT5_15_SDK_FOUND="true"
    QT5_15_OHOS_SDK_PATH="$base/Qt5.15.16-arm64-v8a"
  fi
done
echo "QT5_12_SDK_FOUND=$QT5_12_SDK_FOUND"
echo "QT5_12_OHOS_SDK_PATH=$QT5_12_OHOS_SDK_PATH"
echo "QT5_15_SDK_FOUND=$QT5_15_SDK_FOUND"
echo "QT5_15_OHOS_SDK_PATH=$QT5_15_OHOS_SDK_PATH"

# OHOS SDK native 检测
OHOS_SDK_NATIVE_FOUND="false"
OHOS_SDK_NATIVE_PATH=""
if [ "$DEVECO_FOUND" = "true" ]; then
  if [ "$OS" = "macos" ]; then
    _native="$DEVECO_PATH/Contents/sdk/default/openharmony/native"
  else
    _native="$DEVECO_PATH/sdk/default/openharmony/native"
  fi
  if [ -d "$_native" ]; then
    OHOS_SDK_NATIVE_FOUND="true"
    OHOS_SDK_NATIVE_PATH="$_native"
  fi
fi
echo "OHOS_SDK_NATIVE_FOUND=$OHOS_SDK_NATIVE_FOUND"
echo "OHOS_SDK_NATIVE_PATH=$OHOS_SDK_NATIVE_PATH"

# ENV.local.md 检测
ENV_LOCAL_EXISTS="false"
[ -f "$KB_ROOT/ENV.local.md" ] && ENV_LOCAL_EXISTS="true"
echo "ENV_LOCAL_EXISTS=$ENV_LOCAL_EXISTS"
