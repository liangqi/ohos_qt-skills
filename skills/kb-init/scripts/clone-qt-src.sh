#!/bin/bash
# clone-qt-src.sh — clone the Qt HarmonyOS source
#
# Usage: bash skills/kb-init/scripts/clone-qt-src.sh \
#         --method=<commercial|opensource> \
#         --version=<5.12|5.15> \
#         --dest=<directory> \
#         [--user=<username>] [--pass=<password>]
# Output: QT5_12_SRC=<path> and/or QT5_15_SRC=<path>
# Exit codes: 0=success, 1=failure

set -uo pipefail

METHOD=""
VERSION="5.12"
DEST=""
QT_USER=""
QT_PASS=""

for arg in "$@"; do
  case "$arg" in
    --method=*) METHOD="${arg#*=}";;
    --version=*) VERSION="${arg#*=}";;
    --dest=*) DEST="${arg#*=}";;
    --user=*) QT_USER="${arg#*=}";;
    --pass=*) QT_PASS="${arg#*=}";;
    *) echo "Unknown option: $arg" >&2; exit 2;;
  esac
done

if [ -z "$METHOD" ] || [ -z "$DEST" ]; then
  echo "Usage: bash clone-qt-src.sh --method=<commercial|opensource> --version=<5.12|5.15> --dest=<directory> [--user=<username>] [--pass=<password>]"
  exit 2
fi

echo "--- Qt source clone ---"
echo "  Method: $METHOD"
echo "  Version: $VERSION"
echo "  Target: $DEST"
echo ""

mkdir -p "$DEST"

# Check for git
if ! command -v git &>/dev/null; then
  echo "FAIL: git is not installed"
  exit 1
fi

# Check the git configuration
GIT_NAME=$(git config --global user.name 2>/dev/null || true)
GIT_EMAIL=$(git config --global user.email 2>/dev/null || true)
if [ -z "$GIT_NAME" ] || [ -z "$GIT_EMAIL" ]; then
  echo "FAIL: git user.name or user.email is not configured"
  echo "  git config --global user.name \"Your Name\""
  echo "  git config --global user.email \"your@email\""
  exit 1
fi

clone_repo() {
  local url="$1" branch="$2" target="$3" label="$4"

  if [ -d "$target/qtbase" ]; then
    echo "  Already exists: $target (skipping)"
    return 0
  fi

  echo "  Cloning $label ..."
  # Hide any credentials in the URL
  local _safe_url
  _safe_url=$(echo "$url" | sed 's|://[^@]*@|://***@|')
  echo "  URL: $_safe_url"
  echo "  Branch: $branch"
  echo ""

  git clone --branch "$branch" --single-branch "$url" "$target" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then
    echo "FAIL: clone failed (exit $rc)"
    return 1
  fi

  echo ""
  echo "  Initializing submodules..."
  (cd "$target" && git submodule update --init --recursive 2>&1)
  rc=$?
  [ $rc -ne 0 ] && echo "WARN: submodule initialization failed (exit $rc)"

  echo "  Clone complete: $target"
  return 0
}

# Determine the URL and branch
case "$METHOD" in
  commercial)
    if [ -n "$QT_USER" ] && [ -n "$QT_PASS" ]; then
      REPO_URL="https://${QT_USER}:${QT_PASS}@codereview.qt-project.org/qt/tqtc-qt5"
    else
      REPO_URL="https://codereview.qt-project.org/qt/tqtc-qt5"
    fi
    BRANCH_512="tqtc/harmonyos-5.12.12"
    BRANCH_515="tqtc/harmonyos-5.15.16"
    ;;
  opensource)
    REPO_URL="https://gitcode.com/ohos-qt/qt-harmonyos-src.git"
    BRANCH_512="5.12.12"
    BRANCH_515="5.15.16"
    ;;
  *)
    echo "FAIL: unsupported acquisition method: $METHOD"
    exit 1
    ;;
esac

QT5_12_SRC=""
QT5_15_SRC=""

case "$VERSION" in
  5.12)
    clone_repo "$REPO_URL" "$BRANCH_512" "$DEST/qt5.12" "Qt 5.12.12" || exit 1
    QT5_12_SRC="$DEST/qt5.12"
    ;;
  5.15)
    clone_repo "$REPO_URL" "$BRANCH_515" "$DEST/qt5.15" "Qt 5.15.16" || exit 1
    QT5_15_SRC="$DEST/qt5.15"
    ;;
  both)
    clone_repo "$REPO_URL" "$BRANCH_512" "$DEST/qt5.12" "Qt 5.12.12" || exit 1
    QT5_12_SRC="$DEST/qt5.12"
    clone_repo "$REPO_URL" "$BRANCH_515" "$DEST/qt5.15" "Qt 5.15.16" || exit 1
    QT5_15_SRC="$DEST/qt5.15"
    ;;
  *)
    echo "FAIL: unsupported version: $VERSION"
    exit 1
    ;;
esac

echo ""
echo "--- Results ---"
[ -n "$QT5_12_SRC" ] && echo "QT5_12_SRC=$QT5_12_SRC"
[ -n "$QT5_15_SRC" ] && echo "QT5_15_SRC=$QT5_15_SRC"
echo ""
echo "Source clone complete."
