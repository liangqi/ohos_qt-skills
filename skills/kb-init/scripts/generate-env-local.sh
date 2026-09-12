#!/bin/bash
# generate-env-local.sh — 确定性生成 ENV.local.md
#
# 用法: bash skills/kb-init/scripts/generate-env-local.sh [OPTIONS]
# 选项:
#   --deveco-path=PATH         DevEco Studio 路径
#   --qt5-12-src=PATH          Qt 5.12 源码路径
#   --qt5-15-src=PATH          Qt 5.15 源码路径
#   --qt-build-root=PATH       Qt 编译输出根目录
#   --qt5-12-ohos-sdk=PATH     Qt 5.12 OHOS SDK 路径
#   --qt5-15-ohos-sdk=PATH     Qt 5.15 OHOS SDK 路径
#   --qt6-ohos-sdk=PATH        Qt 6 鸿蒙 target SDK 路径（如 .../6.12.0/harmonyos_arm64_v8a）
#   --qt6-host=PATH            Qt 6 host 工具链路径（如 .../6.12.0/macos）
#   --ohos-sdk-native=PATH     OHOS SDK native 路径
#   --ohos-additional-packages=PATH  鸿蒙第三方预编译库根目录（additional-packages）
# 输出: 生成 ENV.local.md 到知识库根目录
# 退出码: 0=成功

set -uo pipefail

# 从 scripts/ 向上三级到 KB root
KB_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUTPUT="$KB_ROOT/ENV.local.md"

DEVECO_PATH=""
QT5_12_SRC=""
QT5_15_SRC=""
QT_BUILD_ROOT=""
QT5_12_OHOS_SDK=""
QT5_15_OHOS_SDK=""
QT6_OHOS_SDK=""
QT6_HOST=""
OHOS_SDK_NATIVE=""
OHOS_TEMPLATE_SRC=""
OHOS_ADDITIONAL_PACKAGES=""

for arg in "$@"; do
  case "$arg" in
    --deveco-path=*) DEVECO_PATH="${arg#*=}";;
    --qt5-12-src=*) QT5_12_SRC="${arg#*=}";;
    --qt5-15-src=*) QT5_15_SRC="${arg#*=}";;
    --qt-build-root=*) QT_BUILD_ROOT="${arg#*=}";;
    --qt5-12-ohos-sdk=*) QT5_12_OHOS_SDK="${arg#*=}";;
    --qt5-15-ohos-sdk=*) QT5_15_OHOS_SDK="${arg#*=}";;
    --qt6-ohos-sdk=*) QT6_OHOS_SDK="${arg#*=}";;
    --qt6-host=*) QT6_HOST="${arg#*=}";;
    --ohos-sdk-native=*) OHOS_SDK_NATIVE="${arg#*=}";;
    --ohos-template-src=*) OHOS_TEMPLATE_SRC="${arg#*=}";;
    --ohos-additional-packages=*) OHOS_ADDITIONAL_PACKAGES="${arg#*=}";;
    *) echo "未知选项: $arg" >&2; exit 2;;
  esac
done

cat > "$OUTPUT" << HEADER
# ENV.local.md — 本地路径配置

> 本文件由 \`skills/kb-init/\` 初始化 skill 生成。
> 知识页中以变量名引用路径，Agent 读取时以本文件中的值覆盖 \`ENV.md\` 的默认值。
> 本文件已 gitignore，不入库。
>
> 生成时间: $(date +%F)

---

HEADER

# IDE 与工具路径
echo "## IDE 与工具路径" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "| 变量名 | 你的值 |" >> "$OUTPUT"
echo "|--------|--------|" >> "$OUTPUT"
[ -n "$DEVECO_PATH" ] && echo "| \`DEVECO_PATH\` | \`$DEVECO_PATH\` |" >> "$OUTPUT"
[ -n "$OHOS_SDK_NATIVE" ] && echo "| \`OHOS_SDK_NATIVE\` | \`$OHOS_SDK_NATIVE\` |" >> "$OUTPUT"
echo "" >> "$OUTPUT"

# Qt 源码路径（如果有）
if [ -n "$QT5_12_SRC" ] || [ -n "$QT5_15_SRC" ]; then
  echo "## Qt 源码路径" >> "$OUTPUT"
  echo "" >> "$OUTPUT"
  echo "| 变量名 | 你的值 |" >> "$OUTPUT"
  echo "|--------|--------|" >> "$OUTPUT"
  [ -n "$QT5_12_SRC" ] && echo "| \`QT5_12_SRC\` | \`$QT5_12_SRC\` |" >> "$OUTPUT"
  [ -n "$QT5_15_SRC" ] && echo "| \`QT5_15_SRC\` | \`$QT5_15_SRC\` |" >> "$OUTPUT"
  echo "" >> "$OUTPUT"

  # 模板路径：显式指定 > 5.15 源码 > 5.12 源码
  _tpl_src=""
  if [ -n "$OHOS_TEMPLATE_SRC" ]; then
    _tpl_src="$OHOS_TEMPLATE_SRC"
  elif [ -n "$QT5_15_SRC" ]; then
    _tpl_src="$QT5_15_SRC/qtbase/src/harmonyos/templates"
  elif [ -n "$QT5_12_SRC" ]; then
    _tpl_src="$QT5_12_SRC/qtbase/src/harmonyos/templates"
  fi
  if [ -n "$_tpl_src" ]; then
    echo "## 模板" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    echo "| 变量名 | 你的值 |" >> "$OUTPUT"
    echo "|--------|--------|" >> "$OUTPUT"
    echo "| \`OHOS_TEMPLATE_SRC\` | \`$_tpl_src\` |" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
  fi
fi

# 独立模板（无源码时）
if [ -z "$QT5_12_SRC" ] && [ -z "$QT5_15_SRC" ] && [ -n "$OHOS_TEMPLATE_SRC" ]; then
  echo "## 模板" >> "$OUTPUT"
  echo "" >> "$OUTPUT"
  echo "| 变量名 | 你的值 |" >> "$OUTPUT"
  echo "|--------|--------|" >> "$OUTPUT"
  echo "| \`OHOS_TEMPLATE_SRC\` | \`$OHOS_TEMPLATE_SRC\` |" >> "$OUTPUT"
  echo "" >> "$OUTPUT"
fi

# 编译产物与 SDK
echo "## 编译产物与 SDK" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "| 变量名 | 你的值 |" >> "$OUTPUT"
echo "|--------|--------|" >> "$OUTPUT"
[ -n "$QT_BUILD_ROOT" ] && echo "| \`QT_BUILD_ROOT\` | \`$QT_BUILD_ROOT\` |" >> "$OUTPUT"
[ -n "$QT5_12_OHOS_SDK" ] && echo "| \`QT5_12_OHOS_SDK\` | \`$QT5_12_OHOS_SDK\` |" >> "$OUTPUT"
[ -n "$QT5_15_OHOS_SDK" ] && echo "| \`QT5_15_OHOS_SDK\` | \`$QT5_15_OHOS_SDK\` |" >> "$OUTPUT"
[ -n "$QT6_OHOS_SDK" ] && echo "| \`QT6_OHOS_SDK\` | \`$QT6_OHOS_SDK\` |" >> "$OUTPUT"
[ -n "$QT6_HOST" ] && echo "| \`QT6_HOST\` | \`$QT6_HOST\` |" >> "$OUTPUT"
[ -n "$OHOS_ADDITIONAL_PACKAGES" ] && echo "| \`OHOS_ADDITIONAL_PACKAGES\` | \`$OHOS_ADDITIONAL_PACKAGES\` |" >> "$OUTPUT"
echo "" >> "$OUTPUT"

# Qt 6 构建提示
if [ -n "$QT6_OHOS_SDK" ]; then
  {
    echo "### Qt 6 构建与部署"
    echo ""
    echo "\`\`\`bash"
    echo "# 配置（qt-cmake 已内置 toolchain 与 QT_HOST_PATH）"
    echo "$QT6_OHOS_SDK/bin/qt-cmake -S <项目源码目录> -B <构建目录> -DCMAKE_BUILD_TYPE=Release"
    echo "\`\`\`"
    echo ""
    if [ -n "$OHOS_ADDITIONAL_PACKAGES" ]; then
      echo "第三方预编译库（additional-packages）：\`$OHOS_ADDITIONAL_PACKAGES\`"
      echo ""
      echo "- 需要 find_package 找到 fontconfig/freetype/icu 等时追加："
      echo "  \`-DCMAKE_FIND_ROOT_PATH=$OHOS_ADDITIONAL_PACKAGES\`（预构建 kit 通常可省）"
      echo "- **打 HAP 前必须 stage 运行时 .so**：Qt6 预构建 kit 的 .so 带 HARD DT_NEEDED"
      echo "  指向 libicui18n/libicuuc/libicudata/libfontconfig/libfreetype/libpng16/"
      echo "  libbrotlidec/libbrotlicommon/libexpat，harmonydeployqt 不会自动拷贝。"
      echo "  从 \`$OHOS_ADDITIONAL_PACKAGES/lib/\` 拷到 \`hap/entry/libs/arm64-v8a/\` 后重新 assembleHap，"
      echo "  否则 HAP 装得上但启动即 dlopen 失败。"
      echo ""
    fi
    [ -n "$QT6_HOST" ] && echo "部署工具：\`$QT6_HOST/bin/harmonydeployqt\`"
    [ -n "$QT6_HOST" ] && echo ""
    echo "> Qt 6 不使用 qmake + mingw32-make 流程；\`QtOhosExtras\` 对应 \`Qt6::HarmonyExtrasPrivate\`（私有模块）。"
    echo ""
  } >> "$OUTPUT"
fi

echo "ENV.local.md 已生成: $OUTPUT"
