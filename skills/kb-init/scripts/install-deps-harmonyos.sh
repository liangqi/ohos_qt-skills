#!/bin/bash
# install-deps-harmonyos.sh — HarmonyOS dependency check and installation guidance
# Uses HarmonyBrew (https://gitcode.com/Harmonybrew) as the package manager
#
# HarmonyOS platform limitations:
#   - DevEco Studio has no HarmonyOS build and isn't listed in the app store
#   - The Command Line Tools telemetry build must be requested via the unified ticket platform
#   - devecocli (npm package @deveco/deveco-cli) can be tried via npm installation
#
# Status levels:
#   PASS    — ready
#   FAIL    — could be fixed automatically, but the attempt failed
#   PENDING — requires manual user action (filing a request, etc.)
#   WARN    — a non-blocking note
#
# Usage: bash skills/kb-init/scripts/install-deps-harmonyos.sh
# Exit codes: 0=everything ready or only PENDING items, 1=there are FAIL items

set -uo pipefail

PASS=0
FAIL=0
WARN=0
PENDING=0

ok()      { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail()    { echo "  FAIL: $1${2:+ -- $2}"; FAIL=$((FAIL + 1)); }
warn()    { echo "  WARN: $1${2:+ -- $2}"; WARN=$((WARN + 1)); }
pending() { echo "  PENDING: $1${2:+ -- $2}"; PENDING=$((PENDING + 1)); }

echo "--- HarmonyOS dependency check ---"
echo ""
echo "  Note: DevEco Studio / the Command Line Tools currently require a manual request on HarmonyOS."
echo "  Dependencies that can be installed automatically will be; the rest are marked PENDING."
echo ""

# 1. HarmonyBrew
if command -v brew &>/dev/null; then
  BREW_PREFIX=$(brew --prefix 2>/dev/null || echo "")
  if echo "$BREW_PREFIX" | grep -q "harmonybrew"; then
    ok "HarmonyBrew ($(brew --version 2>/dev/null | head -1))"
  else
    warn "Found Homebrew rather than HarmonyBrew" "On HarmonyOS, HarmonyBrew is recommended: zsh -c \"\$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)\""
  fi
else
  fail "HarmonyBrew is not installed" "Run: zsh -c \"\$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)\""
fi

# 2. git
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
  if command -v brew &>/dev/null; then
    fail "git is not installed" "Run: brew install git"
  else
    fail "git is not installed" "Install HarmonyBrew first, then run: brew install git"
  fi
fi

# 3. curl
if command -v curl &>/dev/null; then
  ok "curl"
else
  if command -v brew &>/dev/null; then
    fail "curl is not installed" "Run: brew install curl"
  else
    fail "curl is not installed" "Install HarmonyBrew first, then run: brew install curl"
  fi
fi

# 4. Node.js
if command -v node &>/dev/null; then
  ok "Node.js ($(node --version 2>/dev/null))"
else
  if command -v brew &>/dev/null; then
    fail "Node.js is not installed" "Run: brew install node (devecocli and hvigor depend on Node.js)"
  else
    fail "Node.js is not installed" "Install HarmonyBrew first, then run: brew install node"
  fi
fi

# 5. Java/JDK
if command -v java &>/dev/null; then
  ok "Java ($(java -version 2>&1 | head -1))"
else
  if command -v brew &>/dev/null; then
    warn "Java is not installed" "Run: brew install openjdk"
  else
    warn "Java is not installed" "Install HarmonyBrew first, then run: brew install openjdk"
  fi
fi

# 6. cmake
if command -v cmake &>/dev/null; then
  ok "cmake ($(cmake --version 2>/dev/null | head -1))"
else
  if command -v brew &>/dev/null; then
    fail "cmake is not installed" "Run: brew install cmake"
  else
    fail "cmake is not installed" "Install HarmonyBrew first, then run: brew install cmake"
  fi
fi

# 7. DevEco Studio / Command Line Tools
DEVECO_FOUND="false"
DEVECO_PATH=""
for p in "/opt/deveco-studio" "$HOME/deveco-studio" "$HOME/commandline-tools" "/usr/local/commandline-tools" "$HOME/dev/commandline-tools" "$HOME/DevEco-Studio"; do
  if [ -d "$p" ]; then
    DEVECO_FOUND="true"
    DEVECO_PATH="$p"
    ok "DevEco Studio/CLT ($p)"
    break
  fi
done
if [ "$DEVECO_FOUND" = "false" ]; then
  if command -v devecocli &>/dev/null; then
    DEVECO_FOUND="true"
    DEVECO_PATH=$(dirname "$(dirname "$(command -v devecocli)")")
    ok "DevEco CLI (PATH: $DEVECO_PATH)"
  else
    pending "DevEco Studio / Command Line Tools are not installed" "On HarmonyOS these must be requested manually: go to the unified ticket platform at https://developer.huawei.com/consumer/cn/ and request the telemetry build of Command Line Tools for HarmonyOS. Once you have it, run: bash skills/kb-init/scripts/download-cmdline-tools.sh --dest=\$HOME/commandline-tools --url=<download link>"
  fi
fi

# 8. hdc
if command -v hdc &>/dev/null; then
  ok "hdc (on PATH)"
elif [ "$DEVECO_FOUND" = "true" ] && [ -n "$DEVECO_PATH" ]; then
  _hdc="$DEVECO_PATH/sdk/default/openharmony/toolchains/hdc"
  if [ -f "$_hdc" ]; then
    ok "hdc (bundled with the SDK)"
  else
    warn "hdc not found" "The SDK should include hdc"
  fi
else
  pending "hdc not found" "It comes with the Command Line Tools"
fi

# 9. devecocli (bundled with DevEco)
DEVECO_CLI_FOUND="false"
if command -v devecocli &>/dev/null; then
  DEVECO_CLI_FOUND="true"
  ok "devecocli (on PATH)"
elif [ "$DEVECO_FOUND" = "true" ] && [ -n "$DEVECO_PATH" ]; then
  _cli="$DEVECO_PATH/tools/devecocli"
  if [ -f "$_cli" ]; then
    DEVECO_CLI_FOUND="true"
    ok "devecocli (bundled, not on PATH)"
    warn "devecocli is not on PATH" "Consider adding $DEVECO_PATH/tools to PATH"
  else
    pending "devecocli not found" "It comes with the Command Line Tools"
  fi
else
  pending "devecocli not found" "It comes with the Command Line Tools"
fi

# 10. devecocli (the open-source tool @deveco/deveco-cli)
DEVECO_CLI_OSS_FOUND="false"
if command -v devecocli &>/dev/null; then
  DEVECO_CLI_OSS_FOUND="true"
  ok "devecocli ($(devecocli --version 2>/dev/null || echo 'installed'))"
else
  if command -v npm &>/dev/null; then
    echo "  INFO: attempting to install devecocli automatically..."
    if npm install -g @deveco/deveco-cli &>/dev/null 2>&1; then
      if command -v devecocli &>/dev/null; then
        DEVECO_CLI_OSS_FOUND="true"
        ok "devecocli (installed automatically)"
      else
        warn "devecocli npm install completed but the command wasn't found" "You may need to open a new terminal"
      fi
    else
      warn "Automatic devecocli installation failed" "Install manually: npm install -g @deveco/deveco-cli, or git clone https://gitcode.com/openharmony-sig/deveco-cli.git"
    fi
  else
    warn "devecocli is not installed (npm unavailable)" "Install Node.js first, then run: npm install -g @deveco/deveco-cli"
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
echo "  PASS: $PASS  FAIL: $FAIL  PENDING: $PENDING  WARN: $WARN"
echo ""

if [ "$PENDING" -gt 0 ]; then
  echo "The PENDING items need manual action:"
  echo "  On HarmonyOS, DevEco Studio / the Command Line Tools must be requested through the unified ticket platform."
  echo "  Request them at: https://developer.huawei.com/consumer/cn/"
  echo "  Once you have the download link, run: bash skills/kb-init/scripts/download-cmdline-tools.sh --dest=<directory> --url=<link>"
  echo ""
fi

if [ "$FAIL" -gt 0 ]; then
  echo "STATUS=not-ready"
  echo "Please fix the FAIL items above and run again."
  exit 1
else
  echo "STATUS=ready"
  exit 0
fi
