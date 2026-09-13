#!/bin/bash
# clone-kb.sh — download the ohos_qt-skills knowledge base
#
# Usage: bash skills/kb-init/scripts/clone-kb.sh --dest=<parent-directory>
# Output: KB_ROOT=<knowledge base path>
# Exit codes: 0=success, 1=failure

set -uo pipefail

DEST=""
for arg in "$@"; do
  case "$arg" in
    --dest=*) DEST="${arg#*=}";;
    *) echo "Unknown option: $arg" >&2; exit 2;;
  esac
done

if [ -z "$DEST" ]; then
  echo "Usage: bash clone-kb.sh --dest=<parent-directory>"
  echo "  The knowledge base will be cloned to <parent-directory>/ohos_qt-skills/"
  exit 2
fi

KB_URL="https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git"
KB_DIR="$DEST/ohos_qt-skills"

echo "--- Downloading knowledge base ---"
echo "  URL: $KB_URL"
echo "  Target: $KB_DIR"
echo ""

if [ -d "$KB_DIR" ]; then
  echo "Knowledge base directory already exists: $KB_DIR"
  echo "KB_ROOT=$KB_DIR"
  exit 0
fi

mkdir -p "$DEST"

if ! command -v git &>/dev/null; then
  echo "FAIL: git is not installed"
  echo "  macOS: xcode-select --install"
  echo "  Windows: https://git-scm.com/download/win"
  echo "  Linux: sudo apt install git"
  exit 1
fi

echo "Cloning..."
git clone "$KB_URL" "$KB_DIR" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  echo ""
  echo "FAIL: clone failed (exit $rc)"
  echo "  Check your network connection, or run manually:"
  echo "  git clone $KB_URL $KB_DIR"
  exit 1
fi

echo ""
echo "KB_ROOT=$KB_DIR"
echo "Knowledge base download complete: $KB_DIR"
