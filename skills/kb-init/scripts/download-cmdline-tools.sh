#!/bin/bash
# download-cmdline-tools.sh — automatically download and install the HarmonyOS Command Line Tools
#
# Usage:
#   bash download-cmdline-tools.sh --dest=<install directory> [--url=<custom download URL>]
#
# Supported platforms: macOS, Windows (Git Bash), Linux
# HarmonyOS: automatic download is not supported; the script prints application instructions
#
# Exit codes: 0=success, 1=bad arguments, 2=download failed, 3=unsupported platform

set -uo pipefail

DEST=""
CUSTOM_URL=""

for arg in "$@"; do
  case "$arg" in
    --dest=*) DEST="${arg#*=}" ;;
    --url=*)  CUSTOM_URL="${arg#*=}" ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

if [ -z "$DEST" ]; then
  echo "ERROR: --dest=<install directory> is required"
  echo "Usage: bash download-cmdline-tools.sh --dest=<install directory> [--url=<download URL>]"
  exit 1
fi

detect_os() {
  if [ -d "/storage/Users/currentUser/.harmonybrew" ] || { command -v brew &>/dev/null && brew --prefix 2>/dev/null | grep -q harmonybrew; }; then
    echo "harmonyos"; return
  fi
  case "$(uname -s)" in
    Darwin*) echo "macos" ;;
    Linux*)
      if [ -f "/etc/ohos-release" ] || [ -f "/etc/openharmony-release" ] || grep -qi "openharmony\|harmonyos" /etc/os-release 2>/dev/null; then
        echo "harmonyos"
      else
        echo "linux"
      fi ;;
    MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
    *) echo "unknown" ;;
  esac
}

OS=$(detect_os)
ARCH=$(uname -m)

echo "--- Command Line Tools for HarmonyOS download ---"
echo "  Platform: $OS ($ARCH)"
echo "  Target: $DEST"
echo ""

if [ "$OS" = "harmonyos" ]; then
  echo "STATUS=unsupported"
  echo ""
  echo "Automatic download of the Command Line Tools is not currently supported on HarmonyOS."
  echo ""
  echo "How to obtain them:"
  echo "  1. Go to the HarmonyOS developer site's unified ticket platform: https://developer.huawei.com/consumer/cn/"
  echo "  2. File a ticket requesting the telemetry build of Command Line Tools for HarmonyOS"
  echo "  3. Once you have the download link, re-run this script with the --url argument:"
  echo "     bash download-cmdline-tools.sh --dest=$DEST --url=<download link>"
  echo ""
  echo "You can also download it manually and extract it into: $DEST"
  exit 3
fi

DOWNLOAD_URL=""
ARCHIVE_NAME=""

if [ -n "$CUSTOM_URL" ]; then
  DOWNLOAD_URL="$CUSTOM_URL"
  ARCHIVE_NAME=$(basename "$CUSTOM_URL")
else
  DOWNLOAD_PAGE="https://developer.huawei.com/consumer/cn/download/"
  case "$OS" in
    macos)
      if [ "$ARCH" = "arm64" ]; then
        ARCHIVE_NAME="commandline-tools-mac-arm64.tar.gz"
      else
        ARCHIVE_NAME="commandline-tools-mac-x64.tar.gz"
      fi ;;
    windows)
      ARCHIVE_NAME="commandline-tools-windows-x64.zip" ;;
    linux)
      ARCHIVE_NAME="commandline-tools-linux-x64.tar.gz" ;;
  esac
  echo "STATUS=need-manual"
  echo ""
  echo "Could not determine the download link automatically. Please follow these steps:"
  echo "  1. Go to $DOWNLOAD_PAGE"
  echo "  2. Find Command Line Tools for HarmonyOS"
  echo "  3. Download the $(echo "$ARCHIVE_NAME" | sed 's/-/ /g') build"
  echo "  4. Pass the downloaded file's path to this script:"
  echo "     bash download-cmdline-tools.sh --dest=$DEST --url=file:///path/to/$ARCHIVE_NAME"
  echo ""
  echo "Or specify the download link directly with the --url argument:"
  echo "  bash download-cmdline-tools.sh --dest=$DEST --url=<download link>"
  exit 2
fi

mkdir -p "$DEST"

echo "Downloading: $DOWNLOAD_URL"
TMPFILE=$(mktemp)
if curl -fSL --progress-bar -o "$TMPFILE" "$DOWNLOAD_URL"; then
  echo "Download complete"
else
  echo "ERROR: download failed: $DOWNLOAD_URL"
  rm -f "$TMPFILE"
  exit 2
fi

echo "Extracting..."
case "$ARCHIVE_NAME" in
  *.tar.gz|*.tgz)
    tar xzf "$TMPFILE" -C "$DEST" ;;
  *.zip)
    unzip -q -o "$TMPFILE" -d "$DEST" ;;
  *)
    echo "ERROR: unknown archive format: $ARCHIVE_NAME"
    rm -f "$TMPFILE"
    exit 1 ;;
esac
rm -f "$TMPFILE"

echo "Extraction complete: $DEST"

SDK_NATIVE=""
TOOLCHAINS=""
CLI_PATH=""

for d in "$DEST" "$DEST"/*; do
  [ -d "$d/sdk/default/openharmony/native" ] && SDK_NATIVE="$d/sdk/default/openharmony/native"
  [ -d "$d/sdk/default/openharmony/toolchains" ] && TOOLCHAINS="$d/sdk/default/openharmony/toolchains"
  { [ -f "$d/tools/devecocli" ] || [ -f "$d/tools/devecocli.bat" ]; } && CLI_PATH="$d/tools"
done

echo ""
echo "STATUS=installed"
echo "CLT_ROOT=$DEST"
[ -n "$SDK_NATIVE" ] && echo "OHOS_SDK_NATIVE=$SDK_NATIVE"
[ -n "$TOOLCHAINS" ] && echo "TOOLCHAINS=$TOOLCHAINS"
[ -n "$CLI_PATH" ] && echo "DEVECO_CLI_DIR=$CLI_PATH"

echo ""
echo "Consider adding the following paths to PATH:"
[ -n "$TOOLCHAINS" ] && echo "  export PATH=\"$TOOLCHAINS:\$PATH\""
[ -n "$CLI_PATH" ] && echo "  export PATH=\"$CLI_PATH:\$PATH\""
[ -n "$SDK_NATIVE" ] && echo "  export OHOS_SDK_NATIVE=\"$SDK_NATIVE\""
