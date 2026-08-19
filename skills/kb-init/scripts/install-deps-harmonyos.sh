#!/bin/bash
# install-deps-harmonyos.sh — 鸿蒙平台依赖检查与安装引导
# 使用 HarmonyBrew (https://gitcode.com/Harmonybrew) 作为包管理器
#
# 用法: bash skills/kb-init/scripts/install-deps-harmonyos.sh
# 输出: 检查结果
# 退出码: 0=全部就绪, 1=需要用户手动安装

set -uo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1${2:+ -- $2}"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN: $1${2:+ -- $2}"; WARN=$((WARN + 1)); }

echo "--- 鸿蒙平台依赖检查 ---"
echo ""

# 1. HarmonyBrew
if command -v brew &>/dev/null; then
  BREW_PREFIX=$(brew --prefix 2>/dev/null || echo "")
  if echo "$BREW_PREFIX" | grep -q "harmonybrew"; then
    ok "HarmonyBrew ($(brew --version 2>/dev/null | head -1))"
  else
    warn "检测到 Homebrew 而非 HarmonyBrew" "鸿蒙平台建议使用 HarmonyBrew: zsh -c \"\$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)\""
  fi
else
  fail "HarmonyBrew 未安装" "运行: zsh -c \"\$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)\""
fi

# 2. git
if command -v git &>/dev/null; then
  ok "git ($(git --version 2>/dev/null))"
  # 检查 git 配置
  GIT_NAME=$(git config --global user.name 2>/dev/null || true)
  GIT_EMAIL=$(git config --global user.email 2>/dev/null || true)
  if [ -z "$GIT_NAME" ]; then
    warn "git user.name 未配置" "运行: git config --global user.name \"你的名字\""
  fi
  if [ -z "$GIT_EMAIL" ]; then
    warn "git user.email 未配置" "运行: git config --global user.email \"你的邮箱\""
  fi
else
  if command -v brew &>/dev/null; then
    fail "git 未安装" "运行: brew install git"
  else
    fail "git 未安装" "请先安装 HarmonyBrew，然后运行: brew install git"
  fi
fi

# 3. curl
if command -v curl &>/dev/null; then
  ok "curl"
else
  if command -v brew &>/dev/null; then
    fail "curl 未安装" "运行: brew install curl"
  else
    fail "curl 未安装" "请先安装 HarmonyBrew，然后运行: brew install curl"
  fi
fi

# 4. Node.js（hvigor 构建依赖）
if command -v node &>/dev/null; then
  ok "Node.js ($(node --version 2>/dev/null))"
else
  warn "Node.js 未安装" "DevEco Studio 自带 Node.js，如已安装 DevEco 可忽略。否则运行: brew install node"
fi

# 5. Java/JDK（hvigor 构建依赖）
if command -v java &>/dev/null; then
  ok "Java ($(java -version 2>&1 | head -1))"
else
  warn "Java 未安装" "DevEco Studio 自带 JDK，如已安装 DevEco 可忽略。否则运行: brew install openjdk"
fi

# 6. cmake（Qt 编译和项目构建必需）
if command -v cmake &>/dev/null; then
  ok "cmake ($(cmake --version 2>/dev/null | head -1))"
else
  if command -v brew &>/dev/null; then
    fail "cmake 未安装" "运行: brew install cmake"
  else
    fail "cmake 未安装" "请先安装 HarmonyBrew，然后运行: brew install cmake"
  fi
fi

# 7. DevEco Studio / 命令行工具
DEVECO_FOUND="false"
DEVECO_PATH=""
# 鸿蒙 PC 上 DevEco Studio 的安装路径（待确认，先检查常见路径）
for p in "/opt/deveco-studio" "$HOME/deveco-studio" "/usr/local/deveco-studio" "$HOME/DevEco-Studio"; do
  if [ -d "$p" ]; then
    DEVECO_FOUND="true"
    DEVECO_PATH="$p"
    ok "DevEco Studio/CLI ($p)"
    break
  fi
done
if [ "$DEVECO_FOUND" = "false" ]; then
  # 检查 devecocli 是否在 PATH 中
  if command -v devecocli &>/dev/null; then
    DEVECO_FOUND="true"
    DEVECO_PATH=$(dirname "$(command -v devecocli)")
    ok "DevEco CLI (PATH: $DEVECO_PATH)"
  else
    fail "DevEco Studio/CLI 未安装" "请访问 https://developer.huawei.com/consumer/en/download/ 下载 Command Line Tools for HarmonyOS"
  fi
fi

# 8. hdc（HarmonyOS Device Connector）
if command -v hdc &>/dev/null; then
  ok "hdc (PATH)"
elif [ "$DEVECO_FOUND" = "true" ] && [ -n "$DEVECO_PATH" ]; then
  _hdc="$DEVECO_PATH/sdk/default/openharmony/toolchains/hdc"
  if [ -f "$_hdc" ]; then
    ok "hdc (DevEco SDK 内置)"
  else
    warn "hdc 未找到" "DevEco SDK 中应包含 hdc"
  fi
else
  warn "hdc 未找到" "安装 DevEco Studio/CLI 后自带"
fi

# 9. DevEco CLI (devecocli)
DEVECO_CLI_FOUND="false"
if command -v devecocli &>/dev/null; then
  DEVECO_CLI_FOUND="true"
  ok "DevEco CLI (PATH)"
elif [ "$DEVECO_FOUND" = "true" ] && [ -n "$DEVECO_PATH" ]; then
  _cli="$DEVECO_PATH/tools/devecocli"
  if [ -f "$_cli" ]; then
    DEVECO_CLI_FOUND="true"
    ok "DevEco CLI (DevEco 内置，未加入 PATH)"
    warn "devecocli 未加入 PATH" "建议将 $DEVECO_PATH/tools 加入 PATH"
  else
    warn "DevEco CLI 未找到" "DevEco 工具链应自带 devecocli"
  fi
else
  warn "DevEco CLI 未找到" "安装 DevEco Studio/CLI 后自带"
fi

# 10. 磁盘空间
INSTALL_BASE="${1:-$HOME/dev}"
if [ -d "$(dirname "$INSTALL_BASE")" ]; then
  AVAIL_KB=$(df -k "$(dirname "$INSTALL_BASE")" 2>/dev/null | tail -1 | awk '{print $4}')
  if [ -n "$AVAIL_KB" ]; then
    AVAIL_GB=$((AVAIL_KB / 1024 / 1024))
    if [ "$AVAIL_GB" -ge 5 ]; then
      ok "磁盘空间 (${AVAIL_GB}GB 可用)"
    else
      warn "磁盘空间不足 (${AVAIL_GB}GB 可用，建议至少 5GB)"
    fi
  fi
fi

echo ""
echo "--- 结果 ---"
echo "  PASS: $PASS  FAIL: $FAIL  WARN: $WARN"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "STATUS=not-ready"
  echo "请修复上述 FAIL 项后重新运行。"
  exit 1
else
  echo "STATUS=ready"
  exit 0
fi
