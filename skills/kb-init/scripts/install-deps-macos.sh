#!/bin/bash
# install-deps-macos.sh — macOS dependency check and installation guidance
#
# Usage: bash skills/kb-init/scripts/install-deps-macos.sh
# Output: check results in key=value format
# Exit codes: 0=everything ready, 1=user must install something manually

set -uo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1${2:+ -- $2}"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN: $1${2:+ -- $2}"; WARN=$((WARN + 1)); }

echo "--- macOS dependency check ---"
echo ""

# 1. Homebrew
if command -v brew &>/dev/null; then
  ok "Homebrew ($(brew --version 2>/dev/null | head -1))"
else
  fail "Homebrew is not installed" "See https://brew.sh to install, or run: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
fi

# 2. Xcode Command Line Tools
if xcode-select -p &>/dev/null; then
  ok "Xcode Command Line Tools ($(xcode-select -p))"
else
  fail "Xcode Command Line Tools are not installed" "Run: xcode-select --install"
fi

# 3. git
if command -v git &>/dev/null; then
  ok "git ($(git --version 2>/dev/null))"
  # Check the git configuration
  GIT_NAME=$(git config --global user.name 2>/dev/null || true)
  GIT_EMAIL=$(git config --global user.email 2>/dev/null || true)
  if [ -z "$GIT_NAME" ]; then
    warn "git user.name is not configured" "Run: git config --global user.name \"Your Name\""
  fi
  if [ -z "$GIT_EMAIL" ]; then
    warn "git user.email is not configured" "Run: git config --global user.email \"your@email\""
  fi
else
  fail "git is not installed" "It comes with the Xcode Command Line Tools"
fi

# 4. curl
if command -v curl &>/dev/null; then
  ok "curl"
else
  fail "curl is not installed" "macOS should ship with curl"
fi

# 5. Node.js (required by the hvigor build)
if command -v node &>/dev/null; then
  ok "Node.js ($(node --version 2>/dev/null))"
else
  warn "Node.js is not installed" "DevEco Studio bundles Node.js; ignore this if DevEco is installed"
fi

# 6. Java/JDK (required by the hvigor build)
if command -v java &>/dev/null; then
  ok "Java ($(java -version 2>&1 | head -1))"
else
  warn "Java is not installed" "DevEco Studio bundles a JDK; ignore this if DevEco is installed"
fi

# 7. cmake (required for building Qt and projects; referenced 189 times in the knowledge base)
if command -v cmake &>/dev/null; then
  ok "cmake ($(cmake --version 2>/dev/null | head -1))"
else
  fail "cmake is not installed" "Run: brew install cmake, or see https://cmake.org/download/"
fi

# 8. DevEco Studio
DEVECO_FOUND="false"
DEVECO_PATH=""
for p in "/Applications/DevEco-Studio.app" "$HOME/Applications/DevEco-Studio.app"; do
  if [ -d "$p" ]; then
    DEVECO_FOUND="true"
    DEVECO_PATH="$p"
    ok "DevEco Studio ($p)"
    break
  fi
done
if [ "$DEVECO_FOUND" = "false" ]; then
  fail "DevEco Studio is not installed" "Run: bash skills/kb-init/scripts/download-cmdline-tools.sh --dest=\$HOME/dev/deveco-installer to download the installer automatically, or download it manually from https://developer.huawei.com/consumer/cn/deveco-studio/"
fi

# 9. hdc (HarmonyOS Device Connector)
if command -v hdc &>/dev/null; then
  ok "hdc (on PATH)"
elif [ "$DEVECO_FOUND" = "true" ]; then
  _hdc="$DEVECO_PATH/Contents/sdk/default/openharmony/toolchains/hdc"
  if [ -f "$_hdc" ]; then
    ok "hdc (bundled with the DevEco SDK)"
  else
    warn "hdc not found" "The DevEco SDK should include hdc"
  fi
else
  warn "hdc not found" "It comes with DevEco Studio"
fi

# 10. DevEco CLI (devecocli)
DEVECO_CLI_FOUND="false"
if command -v devecocli &>/dev/null; then
  DEVECO_CLI_FOUND="true"
  ok "DevEco CLI (on PATH)"
elif [ "$DEVECO_FOUND" = "true" ]; then
  _cli="$DEVECO_PATH/Contents/tools/devecocli"
  if [ -f "$_cli" ]; then
    DEVECO_CLI_FOUND="true"
    ok "DevEco CLI (bundled with DevEco Studio, not on PATH)"
    warn "devecocli is not on PATH" "Consider running: echo 'export PATH=\"$DEVECO_PATH/Contents/tools:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
  else
    warn "DevEco CLI not found" "DevEco Studio should ship devecocli"
  fi
else
  warn "DevEco CLI not found" "It comes with DevEco Studio"
fi

# 11. Disk space
INSTALL_BASE="${1:-$HOME/dev}"
if [ -d "$(dirname "$INSTALL_BASE")" ]; then
  AVAIL_KB=$(df -k "$(dirname "$INSTALL_BASE")" 2>/dev/null | tail -1 | awk '{print $4}')
  AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
  if [ "$AVAIL_GB" -ge 5 ]; then
    ok "Disk space (${AVAIL_GB}GB available)"
  else
    warn "Not enough disk space (${AVAIL_GB}GB available; at least 5GB recommended)"
  fi
fi

echo ""
echo "--- Results ---"
echo "  PASS: $PASS  FAIL: $FAIL  WARN: $WARN"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "STATUS=not-ready"
  echo "Please fix the FAIL items above and run again."
  exit 1
else
  echo "STATUS=ready"
  exit 0
fi
