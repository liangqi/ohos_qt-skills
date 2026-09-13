#!/bin/bash
# install-deps-linux.sh — Linux dependency check and installation guidance
# Also works in a Windows Git Bash environment
#
# Usage: bash skills/kb-init/scripts/install-deps-linux.sh [INSTALL_BASE]
# Output: check results
# Exit codes: 0=everything ready, 1=user must install something manually

set -uo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1${2:+ -- $2}"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN: $1${2:+ -- $2}"; WARN=$((WARN + 1)); }

# Detect whether this is Windows Git Bash
IS_WINDOWS="false"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) IS_WINDOWS="true";;
esac

if [ "$IS_WINDOWS" = "true" ]; then
  echo "--- Windows (Git Bash) dependency check ---"
else
  echo "--- Linux dependency check ---"
fi
echo ""

# 1. git
if command -v git &>/dev/null; then
  ok "git ($(git --version 2>/dev/null))"
  GIT_NAME=$(git config --global user.name 2>/dev/null || true)
  GIT_EMAIL=$(git config --global user.email 2>/dev/null || true)
  if [ -z "$GIT_NAME" ]; then
    warn "git user.name is not configured" "Run: git config --global user.name \"Your Name\""
  fi
  if [ -z "$GIT_EMAIL" ]; then
    warn "git user.email is not configured" "Run: git config --global user.email \"your@email\""
  fi
else
  if [ "$IS_WINDOWS" = "true" ]; then
    fail "git is not installed" "Download Git for Windows from https://git-scm.com/download/win"
  else
    fail "git is not installed" "Run: sudo apt install git, or sudo yum install git"
  fi
fi

# 2. curl / wget
if command -v curl &>/dev/null; then
  ok "curl"
elif command -v wget &>/dev/null; then
  ok "wget"
else
  if [ "$IS_WINDOWS" = "true" ]; then
    fail "neither curl nor wget is installed" "Git for Windows usually bundles curl"
  else
    fail "neither curl nor wget is installed" "Run: sudo apt install curl"
  fi
fi

# 3. unzip (needed to extract the SDK)
if command -v unzip &>/dev/null; then
  ok "unzip"
else
  if [ "$IS_WINDOWS" = "true" ]; then
    warn "unzip is not installed" "Git Bash may not bundle unzip; 7-Zip works as an alternative"
  else
    fail "unzip is not installed" "Run: sudo apt install unzip"
  fi
fi

# 4. Node.js
if command -v node &>/dev/null; then
  ok "Node.js ($(node --version 2>/dev/null))"
else
  warn "Node.js is not installed" "The DevEco toolchain bundles Node.js; ignore this if it's already installed"
fi

# 5. Java/JDK
if command -v java &>/dev/null; then
  ok "Java ($(java -version 2>&1 | head -1))"
else
  warn "Java is not installed" "The DevEco toolchain bundles a JDK; ignore this if it's already installed"
fi

# 6. cmake (required for building Qt and projects; referenced 189 times in the knowledge base)
if command -v cmake &>/dev/null; then
  ok "cmake ($(cmake --version 2>/dev/null | head -1))"
else
  if [ "$IS_WINDOWS" = "true" ]; then
    fail "cmake is not installed" "Download the Windows build from https://cmake.org/download/"
  else
    fail "cmake is not installed" "Run: sudo apt install cmake, or sudo yum install cmake"
  fi
fi

# 7. DevEco Studio / command line tools
DEVECO_FOUND="false"
DEVECO_PATH=""
if [ "$IS_WINDOWS" = "true" ]; then
  # Windows: check the common installation paths
  for p in "/c/Program Files/Huawei/DevEco Studio" "/c/Program Files (x86)/Huawei/DevEco Studio" \
           "$LOCALAPPDATA/Programs/DevEco Studio" "/d/DevEco Studio"; do
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
else
  # Linux: check for the command line tools
  for p in "$HOME/deveco-studio" "/opt/deveco-studio" "$HOME/DevEco-Studio" "$HOME/dev/deveco-studio"; do
    if [ -d "$p" ]; then
      DEVECO_FOUND="true"
      DEVECO_PATH="$p"
      ok "DevEco toolchain ($p)"
      break
    fi
  done
  if [ "$DEVECO_FOUND" = "false" ]; then
    fail "The DevEco command line tools are not installed" "Run: bash skills/kb-init/scripts/download-cmdline-tools.sh --dest=\$HOME/commandline-tools --url=<download link> to install automatically, or download manually from https://developer.huawei.com/consumer/cn/download/"
  fi
fi

# 8. hdc
if command -v hdc &>/dev/null; then
  ok "hdc (on PATH)"
else
  warn "hdc is not on PATH" "It comes with DevEco; add the SDK toolchains directory to PATH"
fi

# 9. DevEco CLI (devecocli)
if command -v devecocli &>/dev/null; then
  ok "DevEco CLI (on PATH)"
elif [ "$DEVECO_FOUND" = "true" ]; then
  _cli="$DEVECO_PATH/tools/devecocli"
  if [ -f "$_cli" ]; then
    ok "DevEco CLI (bundled with DevEco, not on PATH)"
    warn "devecocli is not on PATH" "Consider adding $DEVECO_PATH/tools to PATH"
  else
    warn "DevEco CLI not found" "The DevEco toolchain should ship devecocli"
  fi
else
  if [ "$IS_WINDOWS" = "true" ]; then
    warn "DevEco CLI not found" "It comes with DevEco Studio"
  else
    warn "DevEco CLI not found" "It comes with the Command Line Tools"
  fi
fi

# 10. Windows only: PowerShell
if [ "$IS_WINDOWS" = "true" ]; then
  if command -v powershell.exe &>/dev/null; then
    ok "PowerShell (powershell.exe)"
  elif command -v pwsh &>/dev/null; then
    ok "PowerShell (pwsh)"
  else
    fail "PowerShell not found" "Windows should ship with PowerShell"
  fi
fi

# 11. Disk space
INSTALL_BASE="${1:-$HOME/dev}"
if [ -d "$(dirname "$INSTALL_BASE")" ]; then
  AVAIL_KB=$(df -k "$(dirname "$INSTALL_BASE")" 2>/dev/null | tail -1 | awk '{print $4}')
  if [ -n "$AVAIL_KB" ]; then
    AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
    if [ "$AVAIL_GB" -ge 5 ]; then
      ok "Disk space (${AVAIL_GB}GB available)"
    else
      warn "Not enough disk space (${AVAIL_GB}GB available; at least 5GB recommended)"
    fi
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
