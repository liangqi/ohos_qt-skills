# ENV.md variable reference

This file explains what each variable in `ENV.local.md` means and what it's for.

## IDE and tool paths

| Variable | Meaning | Example value |
|----------|---------|---------------|
| `DEVECO_PATH` | DevEco Studio installation path | macOS: `/Applications/DevEco-Studio.app`<br>Windows: `C:\Program Files\Huawei\DevEco Studio` |
| `DEVECO_CLI` | Absolute path of the devecocli executable (kb-init resolves it via PATH → npm global → DevEco bundle and writes it here) | Windows: `C:\Users\<u>\AppData\Roaming\npm\devecocli.ps1` |
| `OHOS_SDK_NATIVE` | OHOS SDK native toolchain path (contains clang/sysroot) | macOS: `/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native` |

## Tools bundled with DevEco

The tools below are installed with DevEco Studio; you don't need to install them separately. They live in subdirectories under `DEVECO_PATH`.

> **macOS note**: in macOS's `.app` bundle structure, the tools are under the `Contents/` subdirectory.
> The paths in the table below are based on Windows/Linux; macOS users should add `/Contents` after `DEVECO_PATH`.

| Tool | Windows/Linux path | macOS path | Purpose | References |
|------|--------------------|------------|---------|------------|
| **devecocli** | npm global (`npm prefix -g`) `devecocli{,.cmd,.ps1}`; or `<DEVECO>/tools/devecocli.bat` (bundled with some versions) | `<DEVECO>/Contents/tools/devecocli` (bundled with some versions) | The DevEco command-line tool (build, install, logs); install with `npm i -g @deveco/deveco-cli` | 13× |
| **hvigorw** | `<DEVECO>/tools/hvigor/bin/hvigorw.js` | `<DEVECO>/Contents/tools/hvigor/bin/hvigorw.js` | The HarmonyOS project build tool (similar to Gradle) | 41× |
| **ohpm** | `<DEVECO>/sdk/default/openharmony/ohpm/bin/ohpm` | `<DEVECO>/Contents/sdk/default/openharmony/ohpm/bin/ohpm` | The HarmonyOS package manager (installing dependencies) | 3× |
| **hdc** | `<DEVECO>/sdk/default/openharmony/toolchains/hdc.exe` | `<DEVECO>/Contents/sdk/default/openharmony/toolchains/hdc` | The device connector (installing apps, logs, debugging) | 95× |
| **clang/clang++** | `<DEVECO>/sdk/default/openharmony/native/llvm/bin/clang.exe` | `<DEVECO>/Contents/sdk/default/openharmony/native/llvm/bin/clang` | The cross-compiler (compiling C/C++ code) | 54+48× |

> **Tip**: consider adding the tool directories to your system PATH so you can use `devecocli`, `hdc`, and friends directly in a terminal.
> - macOS: `echo 'export PATH="/Applications/DevEco-Studio.app/Contents/tools:$PATH"' >> ~/.zshrc`
> - Windows: System settings → Environment variables → Path → add `C:\Program Files\Huawei\DevEco Studio\tools`

## Qt source paths

Only needed if you cloned the Qt source. Users of the prebuilt SDK don't need these.

| Variable | Meaning | Example value |
|----------|---------|---------------|
| `QT5_12_SRC` | Qt 5.12.12 source directory | `/Users/you/dev/qt-src/qt5.12` |
| `QT5_15_SRC` | Qt 5.15.16 source directory | `/Users/you/dev/qt-src/qt5.15` |
| `QT6_DEV_SRC` | Qt 6 dev trunk source (HarmonyOS porting in progress, qtbase only) | `/Users/you/dev/qt6-work/qt6-src` |

## Build artifacts and SDKs

| Variable | Meaning | Example value |
|----------|---------|---------------|
| `QT_BUILD_ROOT` | Qt build output directory (only needed when building the Qt framework) | `/Users/you/dev/qt-build` |
| `QT5_12_OHOS_SDK` | Qt 5.12 OHOS SDK path (CMake's CMAKE_PREFIX_PATH) | `/Users/you/dev/qt-sdk/Qt5.12.12-arm64-v8a` |
| `QT5_15_OHOS_SDK` | Qt 5.15 OHOS SDK path | `/Users/you/dev/qt-sdk/Qt5.15.16-arm64-v8a` |

## Templates

| Variable | Meaning | Example value |
|----------|---------|---------------|
| `OHOS_TEMPLATE_SRC` | Path to the Qt HarmonyOS glue template | With the source: `/Users/you/dev/qt-src/qt5.12/qtbase/src/harmonyos/templates`<br>Without the source: `workspace/templates` |
| `OHOS_TEMPLATE_STANDALONE` | Path to the standalone template archive (used when there's no Qt source; a documentation concept, not written into ENV.local.md) | `workspace/templates` (download `templates-0625.zip` from the GitCode releases) |

**When you have the Qt source**: the template is bundled in the source tree, and `generate-env-local.sh` derives it automatically from `QT5_15_SRC` or `QT5_12_SRC`.

**When you don't (prebuilt SDK only, or a HarmonyOS PC)**: download the standalone template archive `templates-0625.zip` from the GitCode releases page, extract it into `workspace/templates/`, and set `OHOS_TEMPLATE_SRC` manually.
- Download page: https://gitcode.com/ohos-qt/qt-harmonyos-src/releases
- Automatic download: `bash skills/kb-init/scripts/download-template.sh --dest=workspace/templates`

## Build toolchain (only needed when building the Qt framework on Windows)

| Variable | Meaning | Example value |
|----------|---------|---------------|
| `MINGW_ROOT` | MinGW toolchain path | `C:\mingw64` |
| `PERL_ROOT` | Strawberry Perl path | `C:\Strawberry` |

> Application developers don't need these variables.

## Content embedded in the knowledge base

| Variable | Meaning | Value |
|----------|---------|-------|
| `OHOS_COMMON_KB_PUBLIC` | The embedded general HarmonyOS platform knowledge base | `ohos-common-kb-public/` (a relative path; no configuration needed) |
