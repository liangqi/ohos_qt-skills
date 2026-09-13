# Environment variables and local paths (developer edition)

> **How to use this**: running the `skills/kb-init/` initialization skill generates `ENV.local.md` automatically. Alternatively, replace the `<PLACEHOLDER_*>` values in the tables below with the actual paths on your machine before using this as a reference.
> Knowledge pages refer to paths by variable name so you can substitute your own environment.
>
> This is the trimmed developer-edition template — the original's supply-chain delivery directories (irrelevant to external developers) have been removed, leaving only the path variables needed for porting.

---

## 🔧 Qt source paths

> The QtOhosExtras module (`qtohosextras/`) is a subdirectory inside the Qt source tree, not a separate repository.

### Ways to obtain the source

Pick a path depending on whether you have a Qt commercial license:

| Scenario | How to obtain | Notes |
|----------|---------------|-------|
| **Have a Qt commercial license** | `git clone https://codereview.qt-project.org/qt/tqtc-qt5` | Requires a Qt commercial license; gives you the latest patches and full history |
| **No license (open source)** | The open-source code published in the GitCode public repository | Maintained by the OpenHarmonyPCDeveloper organization; provides open-source code and prebuilt artifacts |
| **Only need the prebuilt SDK** | The prebuilt artifacts published in the GitCode public repository | Suitable for application developers who don't need to modify the Qt source |

**Open-source steps** (no-license scenario):
1. Clone the source: `git clone https://gitcode.com/ohos-qt/qt-harmonyos-src <target-path>`
2. Switch branches: `cd <target-path> && git checkout tqtc/harmonyos-5.12.12` (or `tqtc/harmonyos-5.15.16`)

**Getting the prebuilt SDK** (prebuilt-SDK-only scenario):

Download from the releases page: https://gitcode.com/ohos-qt/qt-harmonyos-src/releases

| Platform | Rendering backend | Notes |
|----------|-------------------|-------|
| Windows | Desktop GL | Windows development, Desktop GL rendering |
| Windows | GLES | Windows development, GLES rendering |
| macOS | Desktop GL | macOS development, Desktop GL rendering |
| macOS | GLES | macOS development, GLES rendering |
| HarmonyOS | GLES | Runs on HarmonyOS devices, GLES rendering |

**Commercial steps** (license scenario):
1. Go to https://codereview.qt-project.org and sign in
2. Settings → HTTP Credentials → GENERATE NEW PASSWORD
3. `git clone https://codereview.qt-project.org/qt/tqtc-qt5`
4. Switch branches: `git checkout tqtc/harmonyos-5.12.12` or `tqtc/harmonyos-5.15.16`
5. `git submodule update --init --recursive`

### Path variables

| Variable | Your value | Description |
|----------|------------|-------------|
| `QT5_12_SRC` | `<QT5_12_SRC_PATH>` | Source for the primary Qt 5.12.x LTS HarmonyOS branch (tqtc/harmonyos-5.12.12) |
| `QT5_15_SRC` | `<QT5_15_SRC_PATH>` | Source for the Qt 5.15.x HarmonyOS branch (tqtc/harmonyos-5.15.16) |
| `QT6_DEV_SRC` | `<QT6_DEV_SRC_PATH>` | Qt 6 dev trunk source (HarmonyOS porting in progress, qtbase only) |

## 📦 Build artifacts and SDKs

| Variable | Your value | Description |
|----------|------------|-------------|
| `QT_BUILD_ROOT` | `<QT_BUILD_ROOT_PATH>` | Qt build output root directory |
| `QT5_12_OHOS_SDK` | `<QT5_12_OHOS_SDK_PATH>` | CMake `CMAKE_PREFIX_PATH` (Qt 5.12 default) |
| `QT5_15_OHOS_SDK` | `<QT5_15_OHOS_SDK_PATH>` | CMake `CMAKE_PREFIX_PATH` (Qt 5.15) |

## 📚 Embedded general HarmonyOS platform knowledge

This knowledge base embeds the `ohos-common-kb-public/` directory, containing general HarmonyOS platform knowledge (ArkTS, ArkUI, NAPI, the Stage model, the DevEco toolchain, and so on). When a task concerns platform mechanics rather than Qt-specific problems, consult that directory first.

| Variable | Your value | Description |
|----------|------------|-------------|
| `OHOS_COMMON_KB_PUBLIC` | `ohos-common-kb-public/` | The embedded general HarmonyOS platform knowledge base (a relative path) |

## 📋 Templates

| Variable | Your value | Description |
|----------|------------|-------------|
| `OHOS_TEMPLATE_SRC` | `<QT_SRC>/qtbase/src/harmonyos/templates` | ★ Recommended: the glue template bundled in the Qt source (present in both the 5.15 and 5.12 source trees) |

> Newer Qt HarmonyOS branches bundle the glue template in `qtbase/src/harmonyos/templates`, so you no longer need to download an external ZIP.

## 🔨 Build toolchain

| Variable | Your value | Description |
|----------|------------|-------------|
| `MINGW_ROOT` | `<MINGW_ROOT_PATH>` | The MinGW toolchain (includes mingw32-make; used to build Qt on Windows) |
| `PERL_ROOT` | `<PERL_ROOT_PATH>` | Strawberry Perl installation path (a Qt build system dependency) |
| `OHOS_SDK_NATIVE` | `<DEVECO>/sdk/default/openharmony/native` | OHOS SDK native toolchain (clang/clang++) |

### Build commands

```powershell
# Build and install Qt 5.12.x for OHOS (must be run from PowerShell, not bash/git-bash)
cd <QT_BUILD_ROOT_PATH>
mingw32-make.exe -j64 install
```

> **⚠️ Must be run from PowerShell** — mingw32-make invokes `/usr/bin/sh` internally, which swallows backslashes in paths.

### Windows build environment variables

```bat
SET NATIVE_OHOS_SDK=<DEVECO>/sdk/default/openharmony/native
SET OHOS_SDK_SYSROOT=%NATIVE_OHOS_SDK%/sysroot
SET LLVM_INSTALL_DIR=%NATIVE_OHOS_SDK%/llvm
SET QT5_ROOT_DIR=<QT5_12_SRC_PATH>
```

## 🖥️ IDE and tool paths

| Variable | Your value | Description |
|----------|------------|-------------|
| `DEVECO_PATH` | `<DEVECO_PATH>` | DevEco Studio installation path |

### MCP configuration file locations

| IDE | Configuration file path |
|-----|-------------------------|
| Trae CN / international | `<project-root>/.trae/mcp.json` |
| Cursor | `<project-root>/.cursor/mcp.json` |
| VS Code | `<project-root>/.vscode/mcp.json` |
| Claude Desktop (Windows) | `%APPDATA%/Claude/claude_desktop_config.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Gemini CLI | `~/.gemini/settings.json` |
| OpenCode | `<project-root>/.opencode/config.json` |

## 📌 Qt framework versions (validation baseline)

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |
