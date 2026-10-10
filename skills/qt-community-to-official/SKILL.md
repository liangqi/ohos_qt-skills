---
name: qt-community-to-official
description: Guide users through migrating a Qt for OpenHarmony application from the community version (社区版, qtohextras/QtOhExtras) to the commercial version (商业版, qtohosextras/QtOhosExtras). Use when the user mentions 社区版, 商业版, QtOhExtras, QOhAppContext, qtohextras, ohextras, migrating Qt OHOS code, fixing Qt OHOS compilation errors, generating migration patches, generating signed hap packages, or testing Qt app startup on HarmonyOS. Covers code migration, patch generation, compilation fixing, and signed hap build/test.
---

# Migrating Qt for OpenHarmony: Community Version → Commercial Version

This skill migrates a Qt for OpenHarmony (OHOS) application from the
**community version** (社区版, module `qtohextras` / `QtOhExtras`) to the
**commercial version** (商业版, module `qtohosextras` / `QtOhosExtras`).

The authoritative reference for all API differences is the documentation
directory bundled with this skill:

> **`docs/`** (relative to this skill's base directory)

**Read ALL documents under `docs/` before starting** — they contain the full
API mapping tables, code examples, and migration cheat sheets. New migration
reference documents may be added to this directory at any time; always scan
the full directory, not just one file. The steps below reference these
documents. To enumerate the available documents:

```bash
ls docs/    # from this skill's base directory
```

## When to use

- The project uses community-version Qt OHOS APIs (`QtOhExtras`, `QOhAppContext`,
  `QOhFunctions`, `QOhFileShare`, `namespace QtOh`, `QT += ohextras`,
  `-platform openharmony`).
- The user wants to migrate to the commercial version (`QtOhosExtras`,
  `QOhosAbilityContext`, `QT += ohosextras`, `-platform ohos`).
- The user needs to fix compilation errors after migration.
- The user needs to generate a signed `.hap` package and verify the app starts
  without crashing.

## Step 1: Identify community-version code and migrate to official version

First, **select the Qt version** (§1.0), then **read the version-specific
docs + root docs** under `docs/` for the full API mapping. Then get the
project path and official SDK path, replace Qt .so files, scan the project
for all community-version API usage and replace each occurrence with the
official-version equivalent.

### 1.0 Select Qt version

**This is the first step** — before entering project paths. Select the Qt
version for version-specific migration documentation. Available versions
are detected from subdirectories under `docs/` (e.g., `docs/qt5.12.12/`,
`docs/qt5.15.16/`).

```bash
# List available Qt versions from docs/ subdirectories
ls -d docs/qt*/ 2>/dev/null
# Example output:
#   docs/qt5.12.12/
#   docs/qt5.15.16/
```

Prompt the user:

> 请选择 Qt 版本 (输入序号或版本号，直接 Enter 选择默认最高版本)

```bash
# Default: highest version number
# User can input: "1" (first), "5.12.12" (version string), or Enter (default)

# Selected version determines which docs are used for migration:
# 1. Root docs (docs/*.md) — common to all versions
# 2. Version-specific docs (docs/qt<version>/*.md) — version-specific API diffs
```

| Version | Root docs (common) | Version docs (specific) |
|---------|-------------------|------------------------|
| Qt 5.12.12 | `docs/*.md` | `docs/qt5.12.12/Qt-Ohos-5.12.12-Diff.md`, `docs/qt5.12.12/qt_base.md` |
| Qt 5.15.16 | `docs/*.md` | `docs/qt5.15.16/Qt-Ohos-5.15.16-Diff.md` |

> **Default**: If the user presses Enter without input, the highest version
> number is selected automatically. The migration uses both root docs
> (common fixes like `screen()`, `SP_DialogSaveAllButton`, `delete_include`)
> and the selected version's diff document for version-specific API
> differences.

### 1.0a Get paths and create official project

Prompt the user for **two paths** (template is auto-resolved from `templates/`):

> 1. 请输入需要迁移的qt社区版工程路径
> 2. 请输入官方版 Qt SDK install 路径（含 lib/ 和 include/ 的目录）

```bash
# --- 1. Original project path (source of glue code) ---
ORIG_DIR="<user_input>"
if [ "$ORIG_DIR" = "." ]; then ORIG_DIR="$(pwd)"; fi
[ -d "$ORIG_DIR" ] || { echo "错误: 原始工程目录不存在" >&2; exit 1; }

# Determine original project name and new project name
ORIG_NAME="$(basename "$ORIG_DIR")"
NEW_NAME="${ORIG_NAME}-official"

# --- 2. Template project (auto: use templates/ in same dir as SKILL.md) ---
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"  # same dir as migrate.py / SKILL.md
TEMPLATE_DIR="$SCRIPT_DIR/templates"
[ -d "$TEMPLATE_DIR" ] || { echo "错误: 模版工程目录不存在: $TEMPLATE_DIR" >&2; exit 1; }
echo "模版工程: $TEMPLATE_DIR (自动)"

# --- 3. Official SDK install path ---
SDK_DIR="<user_input>"
[ -d "$SDK_DIR" ] || { echo "错误: SDK 目录不存在" >&2; exit 1; }

# --- 4. Create new project at skill script's directory level ---
NEW_PROJECT_DIR="$SCRIPT_DIR/$NEW_NAME"

# Remove if already exists, then create from template
rm -rf "$NEW_PROJECT_DIR"
cp -r "$TEMPLATE_DIR" "$NEW_PROJECT_DIR"
echo "新工程已创建: $NEW_PROJECT_DIR"

cd "$NEW_PROJECT_DIR"
```

### 1.0b Copy glue code from original project → new project

The **glue code** is the C++ application code written by the developer —
the actual business logic, not the Qt SDK or ArkTS shell. Copy it from the
original project into the new official project:

```bash
# Glue code location in original project
ORIG_CPP="$ORIG_DIR/entry/src/main/cpp"
# Target location in new project (merge — do NOT overwrite template-only files)
NEW_CPP="$NEW_PROJECT_DIR/entry/src/main/cpp"

# Directories/files that exist only in the template — never overwrite
TEMPLATE_ONLY="types libentry hello.cpp"

# 1. Merge C++ source code (glue code) into template's cpp/ directory
#    Copy each file/dir from original, but skip template-only paths
mkdir -p "$NEW_CPP"
for item in "$ORIG_CPP"/*; do
    name=$(basename "$item")
    # Skip if this is a template-only path (keep template's version)
    skip=false
    for t in $TEMPLATE_ONLY; do
        [ "$name" = "$t" ] && skip=true && break
    done
    if [ "$skip" = "true" ]; then
        echo "保留模版独有: $name/"
        continue
    fi
    # Overwrite individual files/dirs from original
    rm -rf "$NEW_CPP/$name"
    cp -r "$item" "$NEW_CPP/$name"
    echo "导入: $name"
done
echo "已导入胶水代码 (保留模版独有: $TEMPLATE_ONLY)"

# 2. Copy resource files — merge, do NOT overwrite template config files
#    Template config files to preserve (relative to resources/):
#      base/profile/main_pages.json   — page routing
#      base/element/string.json        — string resources
#      base/element/color.json         — color resources
TEMPLATE_CONFIGS="base/profile/main_pages.json base/element/string.json base/element/color.json"
ORIG_RES="$ORIG_DIR/entry/src/main/resources"
NEW_RES="$NEW_PROJECT_DIR/entry/src/main/resources"
if [ -d "$ORIG_RES" ]; then
    mkdir -p "$NEW_RES"
    # Copy each file from original, skip template config files
    cd "$ORIG_RES"
    find . -type f | while read -r f; do
        rel="${f#./}"
        skip=false
        for tc in $TEMPLATE_CONFIGS; do
            [ "$rel" = "$tc" ] && skip=true && break
        done
        if [ "$skip" = "true" ]; then
            echo "保留模版配置: $rel"
            continue
        fi
        mkdir -p "$NEW_RES/$(dirname "$rel")"
        cp -f "$ORIG_RES/$rel" "$NEW_RES/$rel"
    done
    echo "已导入资源文件 (保留模版配置: $TEMPLATE_CONFIGS)"
fi

# 3. Merge signingConfigs & products from original → template build-profile.json5
#    These carry machine-bound signing certs and product config.
ORIG_BP="$ORIG_DIR/build-profile.json5"
NEW_BP="$NEW_PROJECT_DIR/build-profile.json5"
if [ -f "$ORIG_BP" ] && [ -f "$NEW_BP" ]; then
    python3 -c "
import re
orig = open('$ORIG_BP', encoding='utf-8', errors='replace').read()
tpl = open('$NEW_BP', encoding='utf-8', errors='replace').read()
for tag in ('signingConfigs', 'products'):
    m = re.search(r'\"' + tag + r'\"\s*:\s*\[', orig)
    if not m: continue
    s = m.end() - 1; d = 0; e = s
    for i in range(s, len(orig)):
        if orig[i] == '[': d += 1
        elif orig[i] == ']':
            d -= 1
            if d == 0: e = i + 1; break
    arr = orig[s:e]
    tm = re.search(r'\"' + tag + r'\"\s*:\s*\[', tpl)
    if tm:
        ts = tm.end() - 1; td = 0; te = ts
        for i in range(ts, len(tpl)):
            if tpl[i] == '[': td += 1
            elif tpl[i] == ']':
                td -= 1
                if td == 0: te = i + 1; break
        tpl = tpl[:ts] + arr + tpl[te:]
        print(f'merged {tag}')
open('$NEW_BP', 'w', encoding='utf-8').write(tpl)
"
    echo "已合并 signingConfigs & products → 模版 build-profile.json5"
fi

# 3b. Fix entry/build-profile.json5: remove x86_64 from abiFilters, keep arm64-v8a only
ENTRY_BP="$NEW_PROJECT_DIR/entry/build-profile.json5"
if [ -f "$ENTRY_BP" ]; then
    # Replace "x86_64" with "arm64-v8a" in abiFilters array
    sed -i 's/"x86_64"/"arm64-v8a"/g' "$ENTRY_BP"
    echo "已移除 entry/build-profile.json5 中的 x86_64，仅保留 arm64-v8a"
fi

# 3c. Update QtAppConstants.ets: set APP_LIBRARY_NAME from CMake target
#     Template default (e.g. 'libwidgettest.so') must match actual CMake
#     add_library(NAME SHARED ...) → 'libNAME.so'
CMAKE_FILE="$NEW_PROJECT_DIR/entry/src/main/cpp/CMakeLists.txt"
QT_CONSTANTS="$NEW_PROJECT_DIR/entry/src/main/ets/common/QtAppConstants.ets"
if [ -f "$CMAKE_FILE" ] && [ -f "$QT_CONSTANTS" ]; then
    # Extract library name from: add_library(NAME SHARED ...)
    LIB_TARGET=$(grep -oP 'add_library\s*\(\s*\K\w+(?=\s+SHARED)' "$CMAKE_FILE" | head -1)
    if [ -n "$LIB_TARGET" ]; then
        LIB_NAME="lib${LIB_TARGET}.so"
        sed -i "s|APP_LIBRARY_NAME\s*=\s*'[^']*'|APP_LIBRARY_NAME = '${LIB_NAME}'|g" "$QT_CONSTANTS"
        echo "已更新 APP_LIBRARY_NAME = '${LIB_NAME}' (from CMake add_library(${LIB_TARGET} SHARED))"
    else
        echo "⚠ 未在 CMakeLists.txt 中找到 add_library(NAME SHARED ...)"
    fi
fi

# 4. Merge requestPermissions from original → template module.json5
#    Do NOT copy AppScope or overwrite entire module.json5 — keep template's config.
#    Only extract requestPermissions array and merge into template's module.json5.
ORIG_MODULE="$ORIG_DIR/entry/src/main/module.json5"
NEW_MODULE="$NEW_PROJECT_DIR/entry/src/main/module.json5"
if [ -f "$ORIG_MODULE" ] && [ -f "$NEW_MODULE" ]; then
    # Extract requestPermissions array from original (using Python for bracket matching)
    python3 -c "
import re, sys
orig = open('$ORIG_MODULE', encoding='utf-8', errors='replace').read()
tpl = open('$NEW_MODULE', encoding='utf-8', errors='replace').read()

# Find requestPermissions array in original
m = re.search(r'\"requestPermissions\"\s*:\s*\[', orig)
if not m:
    print('no requestPermissions in original', file=sys.stderr); sys.exit(0)

start = m.end() - 1; depth = 0; end = start
for i in range(start, len(orig)):
    if orig[i] == '[': depth += 1
    elif orig[i] == ']':
        depth -= 1
        if depth == 0: end = i + 1; break
perms = orig[start:end]

# Replace in template
tm = re.search(r'\"requestPermissions\"\s*:\s*\[', tpl)
if tm:
    ts = tm.end() - 1; td = 0; te = ts
    for i in range(ts, len(tpl)):
        if tpl[i] == '[': td += 1
        elif tpl[i] == ']':
            td -= 1
            if td == 0: te = i + 1; break
    tpl = tpl[:ts] + perms + tpl[te:]
else:
    # Insert before last closing brace
    tpl = tpl.rstrip()[:-1] + '\n    \"requestPermissions\": ' + perms + ',\n}'

open('$NEW_MODULE', 'w', encoding='utf-8').write(tpl)
print('merged requestPermissions')
"
    echo "已合并 requestPermissions → 模版 module.json5"
fi
```

> **Important**: Do NOT overwrite the template's `build-profile.json5` /
> `module.json5` / `app.json5` entirely. The template has correct
> official-version build config and signing. Only merge specific fields:
> - `bundleName`, `vendor`, `versionCode`, `versionName`, `icon`, `label`
>   from original's `AppScope/app.json5` → template's
> - `requestPermissions` array from original's `module.json5` → template's
> - `AppScope/resources/` from original → template (preserves original
>   `app_name` in `string.json`, app icon in `media/`, etc.)

### 1.0c Import .so libraries from official SDK → new project

Copy all `.so` files, headers, and mkspecs from the official SDK into the
new official project:

```bash
SDK_LIB="$SDK_DIR/lib"
SDK_PLUGINS="$SDK_DIR/plugins/platforms"
SDK_INCLUDE="$SDK_DIR/include"
SDK_MKSPECS="$SDK_DIR/mkspecs"

# ── CRITICAL: Find libqohos.so (QPA plugin) ──
# The official QPA plugin may be named libqohos.so or libplugins_platforms_qohos.so
# Search entire SDK if not found in the standard plugins/platforms/ directory.
QOHOS_SO=""
for candidate in "$SDK_PLUGINS"/libqohos.so "$SDK_PLUGINS"/libplugins_platforms_qohos.so; do
    [ -f "$candidate" ] && QOHOS_SO="$candidate" && break
done
if [ -z "$QOHOS_SO" ]; then
    # Search entire SDK for *qohos*.so
    QOHOS_SO=$(find "$SDK_DIR" -name "*qohos*.so" -type f 2>/dev/null | head -1)
fi
if [ -n "$QOHOS_SO" ]; then
    echo "找到 QPA 插件: $(basename "$QOHOS_SO") → $QOHOS_SO"
else
    echo "⚠ 警告: 未在 SDK 中找到 libqohos.so，应用将无法启动！"
    echo "请手动指定 libqohos.so 路径："
    read -r QOHOS_SO
fi

# ── 1. Runtime libs (entry/libs/<arch>/) ──
HAP_LIBS="$NEW_PROJECT_DIR/entry/libs/arm64-v8a"
mkdir -p "$HAP_LIBS/plugins/platforms"
for so in "$SDK_LIB"/*.so; do
    [ -f "$so" ] || continue
    cp -f "$so" "$HAP_LIBS/"
done
for so in "$SDK_PLUGINS"/*.so; do
    [ -f "$so" ] || continue
    cp -f "$so" "$HAP_LIBS/plugins/platforms/"
done
# Ensure libqohos.so exists (copy with canonical name)
if [ -n "$QOHOS_SO" ]; then
    cp -f "$QOHOS_SO" "$HAP_LIBS/plugins/platforms/libqohos.so"
    echo "✓ 已导入 libqohos.so → entry/libs/arm64-v8a/plugins/platforms/"
fi

# ── 2. Dev libs (third_party/qt-ohos-dev/lib/) ──
DEV_LIB="$NEW_PROJECT_DIR/third_party/qt-ohos-dev/lib"
mkdir -p "$DEV_LIB"
for so in "$SDK_LIB"/*.so; do
    [ -f "$so" ] || continue
    cp -f "$so" "$DEV_LIB/"
done

# ── 3. Dev plugins (third_party/qt-ohos-dev/plugins/platforms/) ──
DEV_PLUGINS="$NEW_PROJECT_DIR/third_party/qt-ohos-dev/plugins/platforms"
mkdir -p "$DEV_PLUGINS"
for so in "$SDK_PLUGINS"/*.so; do
    [ -f "$so" ] || continue
    cp -f "$so" "$DEV_PLUGINS/"
done
# Ensure libqohos.so in dev plugins too
if [ -n "$QOHOS_SO" ]; then
    cp -f "$QOHOS_SO" "$DEV_PLUGINS/libqohos.so"
    echo "✓ 已导入 libqohos.so → third_party/qt-ohos-dev/plugins/platforms/"
fi

# ── 4. Dev headers (third_party/qt-ohos-dev/include/) ──
DEV_INCLUDE="$NEW_PROJECT_DIR/third_party/qt-ohos-dev/include"
mkdir -p "$DEV_INCLUDE"
if [ -d "$SDK_INCLUDE" ]; then
    cp -rf "$SDK_INCLUDE/"* "$DEV_INCLUDE/"
fi

# ── 5. Dev mkspecs (third_party/qt-ohos-dev/mkspecs/) ──
DEV_MKSPECS="$NEW_PROJECT_DIR/third_party/qt-ohos-dev/mkspecs"
if [ -d "$SDK_MKSPECS" ]; then
    mkdir -p "$(dirname "$DEV_MKSPECS")"
    cp -rf "$SDK_MKSPECS" "$DEV_MKSPECS"
fi

echo "=== SDK 导入汇总 ==="
echo "运行库 .so: $(ls "$HAP_LIBS"/*.so 2>/dev/null | wc -l)"
echo "开发库 .so: $(ls "$DEV_LIB"/*.so 2>/dev/null | wc -l)"
echo "头文件目录: $(ls -d "$DEV_INCLUDE"/Qt*/ 2>/dev/null | wc -l)"
echo "mkspecs: $([ -d "$DEV_MKSPECS" ] && echo '✓' || echo '✗')"
```

| 导入内容 | 来源 (官方 SDK) | 目标 (新工程) |
|---|---|---|
| 运行库 .so | `SDK/lib/*.so` | `entry/libs/arm64-v8a/` |
| 平台插件 .so | `SDK/plugins/platforms/*.so` | `entry/libs/arm64-v8a/plugins/platforms/` |
| 开发库 .so | `SDK/lib/*.so` | `third_party/qt-ohos-dev/lib/` |
| 开发插件 .so | `SDK/plugins/platforms/*.so` | `third_party/qt-ohos-dev/plugins/platforms/` |
| 开发头文件 | `SDK/include/` | `third_party/qt-ohos-dev/include/` |
| mkspecs | `SDK/mkspecs/` | `third_party/qt-ohos-dev/mkspecs/` |

All subsequent steps (§1.1–§4.6) operate from the **new official project**
directory (`<skill_dir>/<original_name>-official/`) as the project root.

### 1.1 Scan for community-version patterns

Before scanning, display the selected Qt version's reference docs that will
guide this migration (from §1.0).

Search the project's C++ source (`.cpp`, `.h`) and build files (`.pro`,
`CMakeLists.txt`, `qmake.conf`) for these community-version markers:

```bash
# Community-version API markers to search for
rg -n 'QtOhExtras|QOhAppContext|QOhFunctions|QOhFileShare|namespace QtOh|QT \+= ohextras|CONFIG \+= openharmony|libqopenharmony|platform openharmony|QOpenHarmony' --type cpp --type cmake
```

### 1.2 Apply the migration mappings

The migration is guided by the **selected Qt version's documents** (from §1.0):

1. **Read version-specific docs** (`docs/qt<version>/*.md`) — the version diff
   document covers API differences between community and commercial versions
   for the selected Qt version.
2. **Read root docs** (`docs/*.md`) — common version-specific fixes:
   - `screen.md` — `QWidget::screen()` fix (applies when SDK is Qt 5.12)
   - `SP_DialogSaveAllButton.md` — `SP_DialogSaveAllButton` fix (Qt 5.15+ API)
   - `delete_include.md` — unused include removal
3. **Apply common mappings** (community → commercial, summarized below).
4. **Cross-check** against the full version-specific docs for API signatures
   and behavior differences.

> **Version-dependent migration**: Different Qt versions have different API
> differences. The selected version's diff document (e.g.,
> `docs/qt5.12.12/Qt-Ohos-5.12.12-Diff.md`) is the authoritative reference.
> Root docs provide version-specific code fixes that apply based on the
> SDK version in use.

#### Header includes (§9.1)

| Community version | Commercial version |
|---|---|
| `#include <QtOhExtras/QOhAppContext>` | `#include <QtOhosExtras/QOhosAbilityContext>` |
| `#include <QtOhExtras/QOhFunctions>` | `#include <QtOhosExtras/QOhosAppPermissions>` |
| `#include <QtOhExtras/QOhFileShare>` | `#include <QtOhosExtras/QOhosShareKit>` |

#### Class & namespace names (§9.2)

| Community version | Commercial version | Note |
|---|---|---|
| `QOhAppContext` | `QOhosAbilityContext` | Major API enhancement; see §2.2 |
| `namespace QtOh` | `namespace QtOhosExtras` | Namespace change |
| `QtOh::PermissionResult` | `AppPermissions::PermissionResult` | Enum relocated |
| `QtOh::checkPermission()` | `QOhosAbilityContext::requestPermissionFromUserIfNeeded()` | Check→request, sync→async |
| `QOhFileShare::shareFile()` | `QOhosAbilityContext::shareDataWithShareKit()` | API completely rewritten; see §2.4 |
| `QOhAppContext::setColorMode()` | `QOhosPlatformIntegration::setDarkThemeEnabled()` | Theme API moved; see §10.3 |

#### Build configuration (§4, §9.3)

| Config item | Community version | Commercial version |
|---|---|---|
| Qt module | `QT += ohextras` | `QT += ohosextras` |
| Platform config (qmake) | `CONFIG += openharmony` | `CONFIG += ohos` |
| Platform plugin | `libqopenharmony.so` (auto-loaded) | `libqohos.so` (auto-loaded) |
| Runtime platform arg | `-platform openharmony` | `-platform ohos` |
| Deployment prf | `openharmony.prf` | `ohos_deployment.prf` |
| Auto-deploy flag | — | `OHOS_DEPLOYMENT = 1` |

#### Permission API (§2.3, §10.1) — sync → async migration

Community version uses **synchronous** permission calls that block the UI.
Commercial version uses **asynchronous** signal-slot. This is the most
error-prone migration — rewrite the call site entirely:

```cpp
// BEFORE (community): blocking sync call
QtOh::PermissionResult result = QtOh::checkPermission("ohos.permission.CAMERA");
QtOh::PermissionRequestResult req = QtOh::requestPermissionsSync({"ohos.permission.CAMERA"});

// AFTER (commercial): async signal-slot
auto ctx = QOhosAbilityContext::instance();
QObject::connect(ctx, &QOhosAbilityContext::namedPermissionRequestResponseReceived,
    [](QString permName, AppPermissions::PermissionResult result) {
        // handle result here
    });
ctx->requestPermissionFromUserIfNeeded("ohos.permission.CAMERA");
```

#### File share API (§2.4, §10.2) — full rewrite

```cpp
// BEFORE (community)
QOhFileShare::shareFile(QUrl("file:///data/image.png"), "title");

// AFTER (commercial)
auto ctx = QOhosAbilityContext::getDefaultInstance();
auto record = QSharedPointer<ShareKit::QOhosSharedRecord>::create();
record->setTitle("title");
record->addImage(QUrl("file:///data/image.png"));
auto options = QSharedPointer<ShareKit::QOhosShareControllerOptions>::create();
options->setTitle("title");
QObject::connect(ctx.data(), &QOhosAbilityContext::shareKitCompleted,
    [](QByteArray, QSharedPointer<ShareKit::QOhosShareOperationResult> result) {
        // handle completion
    });
ctx->shareDataWithShareKit({record}, options);
```

### 1.3 Window property API (§3) — commercial version adds new APIs

If the project uses standard Qt window API, no change is needed. If it needs
OHOS-specific window features (rounded corners, privacy mode, screen
brightness), use the new commercial-only APIs:

```cpp
#include <QtOhosExtras/QOhosWindowUtils>
QOhosPlatformWindow::setWindowCornerRadius(window, 20.0);
QOhosPlatformWindow::setWindowPrivacyMode(window, true);
QOhosPlatformWindow::setWindowKeepScreenOn(window, true);
```

### 1.4 Verify no community-version markers remain

```bash
rg -n 'QtOhExtras|QOhAppContext|QOhFunctions|QOhFileShare|namespace QtOh[^o]|QT \+= ohextras\b|CONFIG \+= openharmony\b|platform openharmony\b' --type cpp --type cmake
# Expected: zero matches in application source
```

> **Note**: Community-version markers inside the Qt SDK source itself
> (e.g., `qt-harmonyos-sig/qtohextras/`) are expected to remain — only
> application-level code should be migrated.

## Step 2: Generate migration patch file

After completing the code migration in Step 1, generate a patch file
capturing **all file modifications** in the project and save it to the
dedicated `patches/` directory in this skill's base directory.

### 2.1 Create the patch output directory

The `patches/` directory exists under this skill's base directory. Verify it
exists (create if missing):

```bash
# From this skill's base directory
mkdir -p patches/
```

### 2.2 Generate per-directory patch files

**Source**: original project (user input from §1.0).
**Target**: official project (`<orig_name>-official/`).
**Format**: `git diff --no-index` (git-apply compatible).
**Output**: all patches are flat in `patches/<orig_name>/`, named by
directory path (no timestamp, no subdirectories).

```
patches/QtBugDemo/
├── root.patch                              # top-level files
├── AppScope.patch                          # AppScope/ direct files
├── entry.patch                             # entry/ direct files
├── entry_src_main_cpp.patch                # entry/src/main/cpp/ direct files
├── entry_src_main_cpp_pages.patch          # entry/src/main/cpp/pages/ files
├── entry_src_main_ets.patch                # entry/src/main/ets/ files
├── entry_src_main_resources.patch          # entry/src/main/resources/ files
└── ...
```

**Bottom-up traversal**: walk from deepest directories to root. For each
directory, compare only files **directly in that directory** (not
subdirectories). **Only generate a patch if the directory has actual file
changes** — no empty patches. Step 3.5 regenerates the same files (overwrites
with final state after compilation fixes).

> **Key rules**:
> - **Flat output** — all patches in `patches/<orig_name>/`, no subdirectories
> - **No timestamp** — patch named by directory path (`/` → `_`), root → `root`
> - **git diff --no-index** format (git-apply compatible)
> - Compare files **in** each directory only (not subdirectories)
> - Only generate patch if there are changes — **no empty patches**
> - New files: `git diff --no-index /dev/null <clone_file>`
> - Deleted files: `git diff --no-index <orig_file> /dev/null`
> - Exclude: `.git`, `build`, `.hvigor`, `oh_modules`, `.cxx`, `.idea`,
>   `third_party`, `hvigor`, `__pycache__`

### 2.3 Verify the patches

Check each patch captures the expected migration changes:

```bash
# Review a patch — should show community → official API replacements
# Key patterns that should appear in the patches:
#   - QtOhExtras → QtOhosExtras
#   - QOhAppContext → QOhosAbilityContext
#   - ohextras → ohosextras
#   - openharmony → ohos (in platform/config contexts)

for patch in "<skill_base_dir>/patches/migration-"*"-${TIMESTAMP}.patch"; do
    file_count=$(rg -c '^diff --git' "$patch" 2>/dev/null || echo 0)
    echo "$(basename "$patch"): ${file_count} files changed"
done

# Preview any specific patch in detail
head -100 "<skill_base_dir>/patches/migration-<dir_name>-${TIMESTAMP}.patch"
```

### 2.4 Apply the patches (for verification or rollback)

The patches can be applied to restore the migration state on a clean tree.
Apply all patches in sequence:

```bash
# Apply all migration patches to a fresh checkout of the project
cd <project_root>
for patch in "<skill_base_dir>/patches/migration-"*"-${TIMESTAMP}.patch"; do
    echo "Applying: $(basename "$patch")"
    git apply --check "$patch"   # dry-run
    git apply "$patch"           # apply
done
```

> **Purpose**: The patch files serve as a migration checkpoint — they record
> exactly which files and lines changed during the community→official
> migration, organized by directory, separate from any subsequent compilation
> fixes (Step 3) or build/packaging changes (Step 4).

### 2.5 Output patch paths and explain to user

After all patches are generated and verified, **output the full absolute
paths** of all patch files and **explain their purpose to the user**:

```bash
# Output the absolute path of each generated patch file
echo "=== 生成的 patch 文件路径 ==="
for patch in "<skill_base_dir>/patches/migration-"*"-${TIMESTAMP}.patch"; do
    realpath "$patch"
done

# Summary: total patch count and total size
echo "patch 文件数量: $(ls "<skill_base_dir>/patches/migration-"*"-${TIMESTAMP}.patch" 2>/dev/null | wc -l)"
echo "总大小: $(du -sh "<skill_base_dir>/patches/migration-"*"-${TIMESTAMP}.patch" 2>/dev/null | tail -1 | awk '{print $1}')"
```

Present the following information to the user:

> **迁移 patch 文件已生成**
>
> **生成数量**: `<patch_count>` 个 patch 文件
>
> **文件列表**:
> ```
> <list of absolute paths, one per line>
> ```
>
> **作用说明**:
> - 这些 patch 文件记录了 Step 1 代码迁移阶段对工程的所有修改（社区版
>   API → 官方版 API 的替换），按**项目目录**拆分为独立文件。
> - 每个目录对应一个 patch 文件，文件名格式为
>   `migration-<目录路径>-<时间戳>.patch`（目录路径中的 `/` 替换为 `_`，
>   根目录记为 `root`）。
> - 可用于：
>   1. **回滚** — 在干净的工作树上撤销迁移，恢复到社区版代码状态。
>   2. **重放** — 在另一个分支或另一份代码副本上重新应用相同的迁移。
>   3. **审查** — 按目录逐个审查迁移内容，定位具体模块的改动。
>   4. **归档** — 作为迁移记录留档，便于后续追溯每次迁移的具体改动。
>   5. **选择性应用** — 可只应用某个目录的 patch，而非全部迁移。
> - 这些 patch **仅包含 Step 1 迁移的改动**，不包含后续编译修复
>   （Step 3）和打包测试（Step 4）产生的改动，确保迁移内容可独立
>   审查和回放。

## Step 3: Fix compilation errors and complete the build

After migrating the code, build the project and fix errors iteratively.
The workflow **automatically** applies fixes from `build/` documents and
built-in functions — no user prompts. Manual fallback (Layer 3/4) only
activates when no auto-fix matches.

### 3.0 Kill stale hvigor daemons + set up build environment

Before building:

1. **Kill stale hvigor daemons** (build-fix-10, build-fix-11):

```bash
pkill -f 'daemon-process-boot-script'
pkill -f 'hvigor-java-daemon'
ps aux | grep -iE 'hvigor.*daemon' | grep -v grep | awk '{print $2}' | xargs kill -9
```

2. **Set DEVECO_SDK_HOME + JAVA_HOME** (build-fix-12): DevEco Studio sets
   these internally; command-line scripts must set them too, otherwise hvigor
   reports `00303217 Configuration Error: Invalid value of 'DEVECO_SDK_HOME'`:

```bash
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
```

> The migrate.py script auto-detects these via `_setup_build_env()` —
> no manual setup needed when running the script.

> **DevEco Studio warning (build-fix-11)**: If DevEco Studio is running, it
> may **revert external file edits** (overwrite disk files with its in-memory
> buffer, delete `.git`, wipe build output). Before applying fixes via
> opencode or command line, quit DevEco Studio:
> `osascript -e 'quit app "DevEco-Studio"'`

### 3.1 Build with the commercial Qt SDK

```bash
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

> The `--no-daemon` flag prevents hvigor from spawning/reusing daemon
> processes, avoiding the EPERM: uv_cwd issue (build-fix-10).

### 3.2 Fix compilation errors automatically

When compilation fails, **automatically** fix errors by reading `build/`
documents, matching errors, applying documented fixes, and rebuilding —
**without prompting the user**. Iterate until zero errors or no more
fixes match.

```bash
# List available build fix documents
ls build/    # from this skill's base directory
```

**Auto-fix workflow** (each iteration):

1. **Combine stdout + stderr** from build output into a single text stream.
   hvigor puts summary lines in stderr and detailed CMake/compiler errors in
   stdout — both must be collected.
2. **Collect all diagnostic lines** (not just `error:`). Filter for lines
   containing any of these keywords (case-insensitive):
   `error:`, `fatal error`, `failed`, `not found`, `could not find`,
   `wrapopengl`, `find_package`, `configuring incomplete`, `build failed`,
   `component missing`, `file not found`, `EPERM`, `uv_cwd`,
   `DEVECO_SDK_HOME`, `invalid value`,
   `00303168`, `00303217`, `00308018`, `00617301`.
3. Read **ALL** `.md` files in `build/`.
4. For each error line, find the matching `build-fix-*.md` document
   (match by error keyword appearing in the document).
5. Read the document's **`## Auto-fix`** section (structured YAML block).
6. **Apply the fix to the source code automatically**:
   - `replace`: find string → replace with new string in specified files
   - `replace_regex`: regex find → replace in specified files
   - `remove_include`: remove the `#include <...>` line from the file
   - `add_include`: add `#include <...>` after the last existing `#include`
   - `remove_line`: remove all lines containing a pattern string
   - `rewrite_cmake`: replace entire `CMakeLists.txt` with direct path linking
7. After applying **all** matched fixes, **rebuild immediately**.
8. Repeat from step 1 until `BUILD SUCCESSFUL` or no new fixes match.

> **Do NOT display docs and ask user to fix manually.** Apply fixes
> automatically and rebuild. Only escalate to manual (Layer 3/4 below)
> if no `build/` document matches the error.

**Auto-fix section format** (in each `build-fix-*.md`):

```markdown
## Auto-fix

```yaml
match: "no member named 'SP_DialogSaveAllButton'"
files:
  - entry/src/main/cpp/pages/f19_qtoolbar.cpp
actions:
  - type: replace
    from: "QStyle::SP_DialogSaveAllButton"
    to: "QStyle::SP_DialogSaveButton"
```
```

Action types:

| Type | Fields | Description |
|------|--------|-------------|
| `replace` | `from`, `to` | Simple string replacement in each `files` entry |
| `replace_regex` | `from` (regex), `to` | Regex replacement in each `files` entry |
| `remove_include` | `include` | Remove `#include <...>` line from each `files` entry |
| `add_include` | `include` | Add `#include <...>` after last `#include` in each `files` entry |
| `remove_line` | `pattern` | Remove all lines containing `pattern` from each `files` entry |
| `rewrite_cmake` | `target`, `qt_dev_dir` | Replace entire `CMakeLists.txt` with direct path linking template |

#### Layer 3: Built-in error reference (fallback)

If **no `build/` document matched** the error, display the built-in error
reference table for manual fixing:

| Error | Cause | Fix |
|---|---|---|
| `fatal error: 'QtOhExtras/xxx.h' file not found` | Old include path still in source | Replace with `QtOhosExtras/xxx.h` per §9.1 |
| `QOhAppContext was not declared` | Class renamed | Replace with `QOhosAbilityContext` per §9.2 |
| `no member named 'requestPermissionsSync'` | Sync API removed | Rewrite as async signal-slot per §2.3 |
| `no member named 'shareFile' in QOhosAbilityContext` | File share API rewritten | Use `shareDataWithShareKit()` per §2.4 |
| `undefined reference to QtOh::checkPermission` | Namespace/symbol removed | Use `QOhosAbilityContext` methods |
| `cannot find -lQt5OhExtras` | Old module name in link step | Use `Qt5OhosExtras` (via `QT += ohosextras`) |
| `'QOhosPlatformIntegration' was not declared` | Missing include | `#include <QtOhosExtras/QOhosPlatformIntegration>` |
| `QOhosWant / QOhosStartOptions not found` | New classes needed | `#include <QtOhosExtras/QOhosWant>` etc. |
| `EPERM: operation not permitted, uv_cwd` | hvigor daemon cwd invalid | Kill stale daemons (build-fix-10) |
| `SDK component missing` (00303168) | Version mismatch or wrong SDK path | Fix `compatibleSdkVersion` (build-fix-08) or `DEVECO_SDK_HOME` (build-fix-03) |
| `00303217 Configuration Error` | `DEVECO_SDK_HOME` not set/invalid, or ohpm config error | Set `DEVECO_SDK_HOME` (build-fix-12); check `oh-package.json5` (build-fix-09) |
| `00308018 Unknown Error` | CMake execution failed | Check `find_package`/SDK structure (build-fix-04) |
| `00617301 Fetch Source Code Failed` | ohpm local package missing | Remove `@types/libentry.so` from `oh-package.json5` (build-fix-09) |

#### Layer 4: Full error report (last resort)

If all layers failed, output:
1. Filtered error lines (up to 20)
2. **Full build output** (last 60 lines of combined stdout+stderr) — shows
   the actual error details, not just the hvigor summary
3. Build command, project path
4. DevEco Studio reversion warning

> **Why full output**: hvigor's stderr may only show a summary like
> `00303217 Configuration Error` while the actual cause (e.g., ohpm
> `Fetch Source Code Failed` or CMake `find_package` failure) is buried
> in stdout. Showing the full output helps diagnose mismatches between
> DevEco Studio and script error reporting.

> **Adding new auto-fix documents**: Place `.md` files under `build/` with a
> `## Auto-fix` YAML section. The script will automatically parse, match, and
> apply the fix on the next compilation failure — no code changes needed.

### 3.3 Fix CMake / qmake configuration

**Check if the SDK is stripped or full** before choosing the CMake approach:

```bash
# Stripped SDK: no lib/cmake/ and no bin/
ls third_party/qt-ohos-dev/lib/cmake/ 2>/dev/null || echo "NO lib/cmake (stripped)"
ls third_party/qt-ohos-dev/bin/ 2>/dev/null || echo "NO bin/ (no host tools)"
```

**Stripped SDK** (no `lib/cmake/`, no `bin/`) — use direct path linking
(build-fix-04):

```cmake
set(CMAKE_AUTOMOC OFF)   # no moc host tool
set(CMAKE_AUTOUIC OFF)
set(CMAKE_AUTORCC OFF)

set(QT_OHOS_DEV_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../../third_party/qt-ohos-dev)
set(QT_INCLUDE_DIR ${QT_OHOS_DEV_DIR}/include)
set(QT_LIB_DIR ${QT_OHOS_DEV_DIR}/lib)

target_include_directories(myapp PRIVATE
    ${QT_INCLUDE_DIR}/QtCore
    ${QT_INCLUDE_DIR}/QtGui
    ${QT_INCLUDE_DIR}/QtWidgets
    ${QT_INCLUDE_DIR}/QtNetwork
    ${QT_INCLUDE_DIR}
)

target_link_libraries(myapp PRIVATE
    ${QT_LIB_DIR}/libQt5Core.so
    ${QT_LIB_DIR}/libQt5Gui.so
    ${QT_LIB_DIR}/libQt5Widgets.so
    ${QT_LIB_DIR}/libQt5Network.so
)
```

**Full SDK** (has `lib/cmake/` and `bin/`) — use `find_package`:

```cmake
find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core Gui Widgets Network OhosExtras)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Core Gui Widgets Network OhosExtras)

target_link_libraries(myapp PRIVATE
    Qt${QT_VERSION_MAJOR}::Core
    Qt${QT_VERSION_MAJOR}::Gui
    Qt${QT_VERSION_MAJOR}::Widgets
    Qt${QT_VERSION_MAJOR}::OhosExtras
)
```

For **qmake** projects (`.pro`):

```qmake
QT += ohosextras core gui widgets
CONFIG += ohos
```

### 3.4 Iterate until clean build

After each fix, rebuild and check for the next error. The migration is complete
when `hvigorw assembleHap` (or `qmake && make`) succeeds with **zero errors**.
Warnings about deprecated `QString` constructors are acceptable (pre-existing
in the community SDK source).

### 3.5 Generate compilation-fix documentation

After the build completes, **refresh existing** `build-fix-*.md` documents
that were used during Step 3. No new timestamped files are created —
only existing docs are updated with the latest error output and status.

**Workflow**:

1. Collect all unique error lines from all build attempts during Step 3.
2. For each error line, check if it matches any existing `build-fix-*.md`
   document (by keyword matching).
3. If covered → **refresh** the existing doc:
   - Update date to today
   - Update status (已修复 if build succeeded)
   - Append latest error output if not already present
4. If **not covered** → report the error in the output summary (no new file).
5. Output refreshed doc paths and prompt user to upload.

**Output example**:

```
已使用并刷新现有修复文档 (3 个):
  ✓ build/build-fix-04-findpackage-qt6-fallback.md
  ✓ build/build-fix-06-qwidget-screen-api-mismatch.md
  ✓ build/build-fix-07-sp-dialogsaveallbutton-api-mismatch.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  编译修复文档已刷新
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  文档路径:
    build/build-fix-04-findpackage-qt6-fallback.md
    build/build-fix-06-qwidget-screen-api-mismatch.md
    build/build-fix-07-sp-dialogsaveallbutton-api-mismatch.md

  说明:
  以上文档已根据本次构建的最新报错更新。
  请检查文档内容是否完整后，上传更新到 skill。

  温馨提示:
  上传更新后的文档可以帮助完善 skill，使自动修复功能更加智能。
  下次遇到相同错误时，skill 将自动匹配并修复。
  路径: <skill_base_dir>/build/
```

> **No timestamped files**: This step only **refreshes** existing docs.
> Uncovered errors are reported in the output but no new file is created —
> the user manually creates new `build-fix-<NN>-<name>.md` docs as needed.

**Patch regeneration**: After documentation, the script **regenerates the
Step 2 patches** to reflect the final state (original → official with all
migration + compilation fixes applied).

## Step 4: Generate signed hap package and test app startup

### 4.1 Ensure signing is configured

Signing is configured in `build-profile.json5` under `app.signingConfigs`.
This project uses **machine-bound automatic signing** from DevEco Studio:

```json5
{
  "app": {
    "signingConfigs": [{
      "name": "default",
      "type": "HarmonyOS",
      "material": {
        "certpath": "...cer",
        "keyAlias": "debugKey",
        "profile": "...p7b",
        "signAlg": "SHA256withECDSA",
        "storeFile": "...p12"
      }
    }]
  }
}
```

> **If building on a different machine**: re-run automatic signing in DevEco
> Studio (**File > Project Structure > Signing Configs > Automatically
> generate signature**) to regenerate machine-bound `.cer`/`.p7b`/`.p12`
> files. The existing key passwords will not work on a new machine.

### 4.2 Build the signed hap

> **Environment (build-fix-12)**: Command-line builds must set
> `DEVECO_SDK_HOME` and `JAVA_HOME` first (see §3.0). The migrate.py script
> handles this automatically via `run_build()`.

```bash
# Debug build (faster, includes debug symbols)
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon

# Release build
hvigorw assembleHap --mode module -p module=entry@default -p product=default -p buildMode=release --no-daemon
```

The signed `.hap` file is generated under:
```
entry/build/default/outputs/default/entry-default-signed.hap
```

Verify the hap is signed:

```bash
# The filename should contain "-signed"
ls -la entry/build/default/outputs/default/*-signed.hap
```

### 4.3 Install and test app startup

> **hdc environment (build-fix-12)**: `hdc` (HarmonyOS Device Connector) needs
> `DEVECO_SDK_HOME` to find connected devices — same as `hvigorw`. The
> migrate.py script handles this automatically via `run_hdc()`. For manual
> commands, ensure `DEVECO_SDK_HOME` is set (see §3.0).

**Check device connectivity** before installing:

```bash
hdc list targets
# Should show a device ID, not "[Empty]"
```

Install the hap on a connected HarmonyOS device or emulator:

```bash
# Install via hdc (HarmonyOS Device Connector)
hdc install entry/build/default/outputs/default/entry-default-signed.hap

# If already installed, use -r to reinstall
hdc install -r entry/build/default/outputs/default/entry-default-signed.hap

# Launch the app — ability name is read from module.json5 (first entry
# in "abilities" array), NOT hardcoded as "EntryAbility"
hdc shell aa start -a <ability_name> -b <bundle_name>
# ability_name: from entry/src/main/module.json5 → "abilities"[0]."name"
#   e.g., "QAbility", "EntryAbility", "MainAbility"
# bundle_name: from AppScope/app.json5 → "bundleName"
#   e.g., com.demo.qt.bug
```

> **Ability name**: Different projects use different ability names. The
> migrate.py script reads the ability name from `module.json5` automatically.
> Hardcoding `EntryAbility` causes launch failure if the actual name is
> different (e.g., `QAbility`).

### 4.4 Verify no crash on startup

Check the app is running with **retry logic** (app may take time to start).
The script retries at 2s, 3s, 5s intervals:

```bash
# Check if the app process is alive (retry with delays)
sleep 2
hdc shell ps -ef | grep <bundle_name>
# If not found, wait and retry:
sleep 3
hdc shell ps -ef | grep <bundle_name>
# Also try the short name (last segment of bundle name):
hdc shell ps -ef | grep <bundle_short_name>

# Capture hilog output for the app (filter by bundle name or PID)
hdc shell hilog | grep -i "<bundle_name\|FATAL\|crash\|SIGSEGV"

# If the app crashed, get the crash log
hdc shell ls /data/log/faultlog/ 2>/dev/null
hdc shell cat /data/log/faultlog/temp/cppcrash-* 2>/dev/null
```

**Pass criteria**: The app process stays alive after launch, the main window
renders, and no `FATAL` / `SIGSEGV` / `cppcrash` entries appear in hilog.

**Common startup crashes after migration**:

| Crash symptom | Likely cause | Fix |
|---|---|---|
| `dlopen failed: libQt5OhExtras.so not found` | Old community lib still referenced | Ensure `entry/libs/` contains commercial `libQt5OhosExtras.so`, not `libQt5OhExtras.so` |
| `dlopen failed: libqopenharmony.so not found` | QPA plugin name mismatch | Replace `libqopenharmony.so` with `libqohos.so` in `entry/libs/arm64-v8a/plugins/platforms/` |
| `SIGSEGV` in `QOhosAbilityContext::instance()` | Context not yet initialized at call site | Defer context access to after `QGuiApplication` is constructed |
| `platform "ohos" not available` | Commercial QPA plugin missing | Verify `libqohos.so` is in the platforms plugin directory |
| `no Qt platform plugin initialized` | Plugin path wrong | Check `QT_PLUGIN_PATH` or app's plugin directory layout |

### 4.5 Handle startup crash (if any)

**Faultlog timestamp check**: Before app launch, record existing faultlog
files. After launch, check for **new** faultlog files only — old faultlogs
from previous runs are ignored.

```bash
# Before launch: record existing faultlogs
hdc shell ls /data/log/faultlog/temp/  # → faultlog_before

# Launch app
hdc shell aa start -a EntryAbility -b <bundle_name>

# After launch: check for NEW faultlogs
hdc shell ls /data/log/faultlog/temp/  # → faultlog_after

# New crashes = faultlog_after - faultlog_before
# If new faultlogs exist → app crashed in THIS run
# If no new faultlogs → old faultlogs ignored, no crash
```

**If new faultlogs are detected** (app crashed in this run):

1. Display the crash log content.
2. Display common crash causes table (see §4.4).
3. Print: `应用启动崩溃，需要用户手动修复。跳过崩溃处理步骤。`
4. **Skip this step** — do not enter a repair loop.
5. User fixes manually, then re-runs the script to verify.

> **No repair loop**: The script does NOT automatically rebuild and re-test
> after a crash. Crashes often require manual diagnosis (library replacement,
> plugin path correction, code changes). The script notifies the user and
> skips to the next step.

**If no new faultlogs** and process is alive:
- `启动正常，无崩溃` — proceed to functional smoke test (§4.6).

**If process died but no new faultlogs** (hilog has crash keywords):
- Notify user: `应用启动崩溃，需要用户手动修复。跳过崩溃处理步骤。`
- Skip to §4.6.

### 4.6 Functional smoke test

Beyond not crashing, verify core migrated features work:

1. **Permission request**: trigger a permission-gated action; confirm the
   system permission dialog appears (commercial version is async — the dialog
   should not block the UI thread).
2. **File share**: trigger a share action; confirm the system share panel
   appears and the share completes (connect `shareKitCompleted` signal).
3. **Window rendering**: confirm the main window displays with correct
   styling (QHarmonyStyle).
4. **Theme**: if dark mode is used, confirm `setDarkThemeEnabled()` takes
   effect.

## Output directories

| Directory | Purpose | Used in |
|---|---|---|
| `docs/` | Migration reference documents (API differences) | Step 1 — read all before migrating |
| `build/` | Compilation fix documents (error→fix guides) | Step 3 — read on compilation failure |
| `patches/` | Generated patch files (per-directory) | Step 2 (migration) + Step 3.5 (compile-fix) |

### `docs/` — migration reference

The `docs/` directory contains two types of documents:

1. **Root docs** (`docs/*.md`) — common to all Qt versions:
   - `SP_DialogSaveAllButton.md` — SP_DialogSaveAllButton API fix
   - `delete_include.md` — unused include removal
   - `screen.md` — QWidget::screen() API fix

2. **Version-specific docs** (`docs/qt<version>/*.md`) — selected in §1.0a:

| Version directory | Documents |
|---|---|
| `docs/qt5.12.12/` | `Qt-Ohos-5.12.12-Diff.md` (version diff), `qt_base.md` (base guide) |
| `docs/qt5.15.16/` | `Qt-Ohos-5.15.16-Diff.md` (version diff) |

Read **root docs + selected version docs** before migrating. The version-specific
diff document covers API differences between the community and commercial
versions for that Qt version.

> **Adding new versions**: Create `docs/qt<version>/` with a diff document.
> The script will auto-detect it in §1.0a.
>
> **Adding new root docs**: Place `.md` files under `docs/` — no SKILL.md
> update needed.

### `build/` — compilation fix guides

When compilation fails (Step 3), the workflow **automatically** reads all
`build/` `.md` files, matches errors, and applies fixes — without prompting
the user (see §3.2). Each build-fix document contains a **`## Auto-fix`**
section with structured YAML that specifies:

- `match`: regex pattern to match the error
- `files`: list of source files to modify
- `actions`: list of fix actions (`replace`, `replace_regex`,
  `remove_include`, `add_include`, `remove_line`, `rewrite_cmake`)

The agent/script reads the `## Auto-fix` YAML, applies the actions to the
source code, rebuilds, and iterates until zero errors. Only if no `build/`
document matches does it fall back to the built-in error reference table
(Layer 3) and full error report (Layer 4).

Current build-fix documents:

| Document | Error | Auto-fix action |
|---|---|---|
| `build-fix-04` | CMake `find_package` falls back to system Qt6 (`00308018`) | `rewrite_cmake` |
| `build-fix-05` | QtOhosExtras forwarding header missing | `remove_include` |
| `build-fix-06` | `QWidget::screen()` Qt 5.14+ API | `add_include` + `replace_regex` |
| `build-fix-07` | `SP_DialogSaveAllButton` Qt 5.15+ API | `replace` |
| `build-fix-08` | `compatibleSdkVersion` mismatch (`00303168`/`00303217`) | `replace` |
| `build-fix-09` | ohpm `types/libentry` missing (`00617301`) | `remove_line` |
| `build-fix-10` | `EPERM: uv_cwd` stale daemon | Kill daemons (built-in) |
| `build-fix-11` | DevEco Studio reverts edits | Warning (built-in) |
| `build-fix-12` | `DEVECO_SDK_HOME` not set (`00303217`) | Auto-set env vars (built-in) |

> **Adding new fix documents**: Place `.md` files under `build/` — the script
> will automatically read and match them on the next compilation failure
> (Layer 2). For complex multi-step fixes, add a built-in auto-fix function
> in `migrate.py` (Layer 1).

### `patches/` — generated patch files

- `migration-<dir>-<timestamp>.patch` — Step 2 migration patches (per directory)
