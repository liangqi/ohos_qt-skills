#!/bin/bash
# install-deveco-cli.sh — install devecocli automatically (npm package @deveco/deveco-cli)
#
# devecocli: an integrated HarmonyOS application development toolset (build/run/signature/log/emulator)
# Repository: https://gitcode.com/openharmony-sig/deveco-cli
#
# Installation methods:
#   1. Global npm install (recommended; requires Node.js)
#   2. git clone + npm install (fallback)
#
# Usage:
#   bash install-deveco-cli.sh [--method=npm|git] [--dest=<git clone directory>]
#
# Exit codes: 0=success, 1=failure

set -uo pipefail

METHOD="npm"
DEST=""

for arg in "$@"; do
  case "$arg" in
    --method=*) METHOD="${arg#*=}" ;;
    --dest=*)   DEST="${arg#*=}" ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

echo "--- devecocli installation (@deveco/deveco-cli) ---"
echo "  Method: $METHOD"
echo ""

if command -v devecocli &>/dev/null; then
  CURRENT_VER=$(devecocli --version 2>/dev/null || echo "unknown")
  echo "STATUS=already-installed"
  echo "DEVECO_CLI_VERSION=$CURRENT_VER"
  echo "devecocli is already installed: $CURRENT_VER"
  exit 0
fi

install_via_npm() {
  echo "Method 1: global npm install"
  echo ""

  if ! command -v npm &>/dev/null; then
    echo "ERROR: npm is not installed"
    echo "Install Node.js (>= 18) first: https://nodejs.org/"
    return 1
  fi

  NODE_VER=$(node --version 2>/dev/null | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
  if [ "$NODE_MAJOR" -lt 18 ] 2>/dev/null; then
    echo "WARN: Node.js version too old ($NODE_VER); devecocli requires >= 18"
    echo "Please upgrade Node.js: https://nodejs.org/"
    return 1
  fi

  echo "Node.js: $NODE_VER"
  echo "Running: npm install -g @deveco/deveco-cli"
  echo ""

  if npm install -g @deveco/deveco-cli 2>&1; then
    if command -v devecocli &>/dev/null; then
      echo ""
      echo "STATUS=installed"
      echo "DEVECO_CLI_VERSION=$(devecocli --version 2>/dev/null || echo 'unknown')"
      echo "DEVECO_CLI_PATH=$(command -v devecocli)"
      return 0
    fi
  fi

  echo "npm installation failed"
  return 1
}

install_via_git() {
  echo "Method 2: git clone + npm install"
  echo ""

  if ! command -v git &>/dev/null; then
    echo "ERROR: git is not installed"
    return 1
  fi

  if ! command -v npm &>/dev/null; then
    echo "ERROR: npm is not installed"
    return 1
  fi

  CLONE_DIR="${DEST:-$HOME/dev/deveco-cli}"
  mkdir -p "$(dirname "$CLONE_DIR")"

  if [ -d "$CLONE_DIR/.git" ]; then
    echo "Directory already exists, updating: $CLONE_DIR"
    git -C "$CLONE_DIR" pull 2>&1
  else
    echo "Cloning repository: https://gitcode.com/openharmony-sig/deveco-cli.git"
    git clone https://gitcode.com/openharmony-sig/deveco-cli.git "$CLONE_DIR" 2>&1
  fi

  if [ ! -d "$CLONE_DIR" ]; then
    echo "ERROR: clone failed"
    return 1
  fi

  echo "Installing dependencies..."
  (cd "$CLONE_DIR" && npm install 2>&1)

  if [ -f "$CLONE_DIR/package.json" ]; then
    BIN_CMD=$(cd "$CLONE_DIR" && node -e "try{console.log(require('./package.json').bin&&Object.keys(require('./package.json').bin)[0]||'')}catch(e){}" 2>/dev/null)
    if [ -n "$BIN_CMD" ] && [ -f "$CLONE_DIR/node_modules/.bin/$BIN_CMD" ]; then
      echo ""
      echo "STATUS=installed-local"
      echo "DEVECO_CLI_DIR=$CLONE_DIR"
      echo "DEVECO_CLI_BIN=$CLONE_DIR/node_modules/.bin/$BIN_CMD"
      echo ""
      echo "Consider creating a global link:"
      echo "  cd $CLONE_DIR && npm link"
      return 0
    fi
  fi

  echo ""
  echo "STATUS=cloned"
  echo "DEVECO_CLI_DIR=$CLONE_DIR"
  echo ""
  echo "The repository was cloned to $CLONE_DIR; see its README for the remaining installation steps."
  return 0
}

case "$METHOD" in
  npm)
    if install_via_npm; then
      exit 0
    fi
    echo ""
    echo "The npm method failed; trying the git method..."
    echo ""
    if install_via_git; then
      exit 0
    fi
    ;;
  git)
    if install_via_git; then
      exit 0
    fi
    ;;
  *)
    echo "ERROR: unknown installation method: $METHOD (valid: npm, git)"
    exit 1
    ;;
esac

echo ""
echo "STATUS=failed"
echo ""
echo "Automatic installation failed. Please install manually:"
echo "  Method 1: npm install -g @deveco/deveco-cli"
echo "  Method 2: git clone https://gitcode.com/openharmony-sig/deveco-cli.git && cd deveco-cli && npm install"
exit 1
