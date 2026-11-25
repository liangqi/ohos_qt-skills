---
name: qt-community-to-official
description: Guides the user through migrating a Qt for OpenHarmony application from the community edition (qtohextras/QtOhExtras) to the official edition (qtohosextras/QtOhosExtras). Triggered when the user mentions the community edition, the official edition, QtOhExtras, QOhAppContext, qtohextras, ohextras, migrating Qt OHOS code, fixing Qt OHOS build errors, generating migration patches, building a signed hap package, or testing that a Qt application launches. Covers code migration, patch generation, build fixes, signed hap builds, and testing.
---

# Qt for OpenHarmony migration: community edition → official edition

This skill migrates a Qt for OpenHarmony (OHOS) application from the **community edition** (module `qtohextras` / `QtOhExtras`)
to the **official edition** (module `qtohosextras` / `QtOhosExtras`).

The authoritative reference documents for all API differences live in this skill's `docs/` directory:

> **`docs/`** (relative to this skill's base directory)

**You must read every document under `docs/` before migrating** — they contain the complete API mapping tables, code examples, and a migration cheat sheet.
New migration reference documents may be added to this directory at any time; always scan the whole directory rather than reading a single file.

```bash
ls docs/    # from this skill's base directory
```

## When to use

- The project uses the community-edition Qt OHOS APIs (`QtOhExtras`, `QOhAppContext`, `QOhFunctions`,
  `QOhFileShare`, `namespace QtOh`, `QT += ohextras`, `-platform openharmony`).
- The user needs to migrate to the official edition (`QtOhosExtras`, `QOhosAbilityContext`, `QT += ohosextras`,
  `-platform ohos`).
- The user needs to fix build errors after migration.
- The user needs to build a signed `.hap` package and verify that the application launches without crashing.

## Step 1: Identify community-edition code and migrate it to the official edition

First **select the Qt version** (§1.0), then read the version-specific documents and the root documents to get the complete API mapping.
Next, obtain the project path and the official SDK path, replace the Qt .so files, scan the project for every community-edition API use,
and replace each one with its official-edition equivalent.

### 1.0 Select the Qt version

**This is the first step** — before entering the project path. Detect the available versions from the `docs/` subdirectories
(e.g. `docs/qt5.12.12/`, `docs/qt5.15.16/`).

```bash
ls -d docs/qt*/ 2>/dev/null
```

Prompt the user:

> Select the Qt version (enter a number or version string; press Enter to choose the default, the highest version)

| Version | Root documents (common) | Version documents (specific) |
|---------|-------------------------|------------------------------|
| Qt 5.12.12 | `docs/*.md` | `docs/qt5.12.12/Qt-Ohos-5.12.12-Diff.md`, `docs/qt5.12.12/qt_base.md` |
| Qt 5.15.16 | `docs/*.md` | `docs/qt5.15.16/Qt-Ohos-5.15.16-Diff.md` |

> **Default**: if the user just presses Enter, the highest version is selected automatically. Migration uses both the root documents (common fixes)
> and the diff documents of the selected version (version-specific API differences).

### 1.0a Obtain paths and create the official-edition project

Prompt the user for **two paths** (the template is read automatically from `templates/`):

> 1. Enter the path of the Qt community-edition project to migrate
> 2. Enter the official-edition Qt SDK install path (the directory containing lib/ and include/)

```bash
# --- 1. Original project path (source of the glue code) ---
ORIG_DIR="<user input>"
if [ "$ORIG_DIR" = "." ]; then ORIG_DIR="$(pwd)"; fi
[ -d "$ORIG_DIR" ] || { echo "Error: original project directory does not exist" >&2; exit 1; }

ORIG_NAME="$(basename "$ORIG_DIR")"
NEW_NAME="${ORIG_NAME}-official"

# --- 2. Template project (automatic: uses templates/ in the same directory as SKILL.md) ---
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TEMPLATE_DIR="$SCRIPT_DIR/templates"
[ -d "$TEMPLATE_DIR" ] || { echo "Error: template project directory does not exist: $TEMPLATE_DIR" >&2; exit 1; }

# --- 3. Official-edition SDK install path ---
SDK_DIR="<user input>"
[ -d "$SDK_DIR" ] || { echo "Error: SDK directory does not exist" >&2; exit 1; }

# --- 4. Create the new project next to the skill script ---
NEW_PROJECT_DIR="$SCRIPT_DIR/$NEW_NAME"
rm -rf "$NEW_PROJECT_DIR"
cp -r "$TEMPLATE_DIR" "$NEW_PROJECT_DIR"

# Delete the template's libentry.so-related files (they clash with the library name in the imported CMakeLists.txt)
rm -f "$NEW_PROJECT_DIR/entry/src/main/cpp/hello.cpp"
rm -rf "$NEW_PROJECT_DIR/entry/src/main/cpp/types"
rm -f "$NEW_PROJECT_DIR/entry/oh_modules/@types/libentry.so"

cd "$NEW_PROJECT_DIR"
```

### 1.0b Import the glue code (merge, keeping template-only files)

**Glue code** is the C++ application code written by the developer — the actual business logic, not the Qt SDK or the ArkTS shell.

```bash
ORIG_CPP="$ORIG_DIR/entry/src/main/cpp"
NEW_CPP="$NEW_PROJECT_DIR/entry/src/main/cpp"

# Template-only files/directories — do not overwrite (already deleted in the previous step)
TEMPLATE_ONLY="types libentry hello.cpp"

mkdir -p "$NEW_CPP"
for item in "$ORIG_CPP"/*; do
    name=$(basename "$item")
    skip=false
    for t in $TEMPLATE_ONLY; do
        [ "$name" = "$t" ] && skip=true && break
    done
    if [ "$skip" = "true" ]; then continue; fi
    rm -rf "$NEW_CPP/$name"
    cp -r "$item" "$NEW_CPP/$name"
done
```

**Import resource files** (merge; do not overwrite the template's configuration files):

```bash
# Template configuration files — keep, do not overwrite:
#   base/profile/main_pages.json   — page routing
#   base/element/string.json        — string resources
#   base/element/color.json         — color resources
TEMPLATE_CONFIGS="base/profile/main_pages.json base/element/string.json base/element/color.json"
```

**Merge configuration files** (extract specific fields only; do not overwrite the template wholesale):

| File | Kept from template | Merged from original project |
|------|--------------------|------------------------------|
| `build-profile.json5` | `buildModeSet`, `modules`, etc. | `signingConfigs`, `products` |
| `module.json5` | The whole file | Only `requestPermissions` |
| `AppScope/app.json5` | Template configuration | `bundleName`, `vendor`, `versionCode`, `versionName`, `icon`, `label` |
| `entry/build-profile.json5` | — | Remove `x86_64`, keep only `arm64-v8a` |
| `QtAppConstants.ets` | — | `APP_LIBRARY_NAME` extracted from CMake `add_library(NAME SHARED)` |

### 1.0c Import the SDK .so files

**Only replace .so files that already exist (by name) in the original project** — walk the SDK directory and copy only the .so files present in the original project:

1. Walk every .so file in the original project and build a `file name → [directory paths]` index
2. For each .so in the original project:
   - The SDK has a file with the same name → replace in place
   - A file renamed in the community edition → delete the old name and put the official-edition file in the same directory
   - The SDK has no file with that name → skip
3. Make sure `libqohos.so` exists in every `platforms/` directory
4. Make sure `libqohosstyle.so` exists in every `styles/` directory

**Community edition → official edition .so rename mapping**:

| Community-edition .so | Official-edition .so | Type |
|---|---|---|
| `libQt5OhExtras.so` | `libQt5OhosExtras.so` | Library |
| `libqopenharmony.so` | `libqohos.so` | Platform plugin |
| `libplugins_platforms_qopenharmony.so` | `libqohos.so` | Platform plugin |
| `libplugins_platforms_qohos.so` | `libqohos.so` | Platform plugin |
| `libplugins_styles_qharmonystyle.so` | `libqohosstyle.so` | Style plugin |
| `libplugins_styles_qohosstyle.so` | `libqohosstyle.so` | Style plugin |

**Also import**: headers → `third_party/qt-ohos-dev/include/`, mkspecs → `third_party/qt-ohos-dev/mkspecs/`

All subsequent steps (§1.1–§4.6) operate in the **new official-edition project** directory (`<skill_dir>/<original name>-official/`).

### 1.1 Scan for community-edition API markers

```bash
rg -n 'QtOhExtras|QOhAppContext|QOhFunctions|QOhFileShare|namespace QtOh|QT \+= ohextras|CONFIG \+= openharmony|libqopenharmony|platform openharmony|QOpenHarmony' --type cpp --type cmake
```

### 1.2 Apply the migration mappings

The migration is guided by **the documents of the selected Qt version**:

1. **Read the version-specific documents** (`docs/qt<version>/*.md`)
2. **Read the root documents** (`docs/*.md`) — common fixes
3. **Apply the common mappings** (community edition → official edition)

#### Headers (§9.1)

| Community edition | Official edition |
|---|---|
| `#include <QtOhExtras/QOhAppContext>` | `#include <QtOhosExtras/QOhosAbilityContext>` |
| `#include <QtOhExtras/QOhFunctions>` | `#include <QtOhosExtras/QOhosAppPermissions>` |
| `#include <QtOhExtras/QOhFileShare>` | `#include <QtOhosExtras/QOhosShareKit>` |

#### Class names and namespaces (§9.2)

| Community edition | Official edition | Notes |
|---|---|---|
| `QOhAppContext` | `QOhosAbilityContext` | Substantially enhanced API |
| `namespace QtOh` | `namespace QtOhosExtras` | Namespace change |
| `QtOh::PermissionResult` | `AppPermissions::PermissionResult` | Enum moved |
| `QtOh::checkPermission()` | `QOhosAbilityContext::requestPermissionFromUserIfNeeded()` | Check → request, sync → async |
| `QOhFileShare::shareFile()` | `QOhosAbilityContext::shareDataWithShareKit()` | API completely rewritten |
| `QOhAppContext::setColorMode()` | `QOhosPlatformIntegration::setDarkThemeEnabled()` | Theme API moved |

#### Build configuration (§4, §9.3)

| Setting | Community edition | Official edition |
|---|---|---|
| Qt module | `QT += ohextras` | `QT += ohosextras` |
| Platform config | `CONFIG += openharmony` | `CONFIG += ohos` |
| Platform plugin | `libqopenharmony.so` | `libqohos.so` |
| Runtime platform argument | `-platform openharmony` | `-platform ohos` |
| Deployment prf | `openharmony.prf` | `ohos_deployment.prf` |

#### Permission API (§2.3, §10.1) — sync → async migration

```cpp
// Community edition: synchronous, blocking
QtOh::PermissionResult result = QtOh::checkPermission("ohos.permission.CAMERA");

// Official edition: asynchronous signals and slots
auto ctx = QOhosAbilityContext::instance();
QObject::connect(ctx, &QOhosAbilityContext::namedPermissionRequestResponseReceived,
    [](QString permName, AppPermissions::PermissionResult result) { /* handle the result */ });
ctx->requestPermissionFromUserIfNeeded("ohos.permission.CAMERA");
```

#### File sharing API (§2.4, §10.2) — completely rewritten

```cpp
// Community edition
QOhFileShare::shareFile(QUrl("file:///data/image.png"), "title");

// Official edition
auto ctx = QOhosAbilityContext::getDefaultInstance();
auto record = QSharedPointer<ShareKit::QOhosSharedRecord>::create();
record->setTitle("title");
record->addImage(QUrl("file:///data/image.png"));
auto options = QSharedPointer<ShareKit::QOhosShareControllerOptions>::create();
ctx->shareDataWithShareKit({record}, options);
```

### 1.3 Window property APIs (§3)

The standard Qt window APIs need no changes. For OHOS-specific window features (rounded corners/privacy mode/brightness), use the APIs added in the official edition:

```cpp
#include <QtOhosExtras/QOhosWindowUtils>
QOhosPlatformWindow::setWindowCornerRadius(window, 20.0);
QOhosPlatformWindow::setWindowPrivacyMode(window, true);
```

### 1.4 Verify that no community-edition markers remain

```bash
rg -n 'QtOhExtras|QOhAppContext|QOhFunctions|QOhFileShare|namespace QtOh[^o]|QT \+= ohextras\b|CONFIG \+= openharmony\b|platform openharmony\b' --type cpp --type cmake
# Expected: zero matches in application code
```

## Step 2: Generate migration patch files

Compare the migrated official-edition project with the original project and generate patch files per directory.

### 2.1 Confirm the patch output directory

```bash
mkdir -p project-patches/<original project name>/
```

### 2.2 Generate patches per directory

**Comparison baseline**: original project ←→ official-edition project
**Output directory**: `project-patches/<original project name>/`
**Format**: `git diff --no-index` (compatible with `git apply`)

```
project-patches/QtBugDemo/
├── root.patch                     # top-level files
├── AppScope.patch                 # AppScope/ directory
├── entry.patch                    # entry/ directory
├── entry_src_main_cpp.patch       # entry/src/main/cpp/ directory
└── ...
```

**Rules**:
- All patches are stored flat under `project-patches/<original project name>/`
- File names follow the directory path (`/` → `_`, root directory → `root`)
- Filter out `.so` and `.py` files
- Exclude `.git`, `build`, `.hvigor`, `oh_modules`, `.cxx`, `.idea`, `third_party`
- Generate patches only for directories with changes — no empty patches

### 2.3 Verify the patches

```bash
for patch in project-patches/<original project name>/*.patch; do
    file_count=$(rg -c '^diff --git' "$patch" 2>/dev/null || echo 0)
    echo "$(basename "$patch"): ${file_count} files changed"
done
```

### 2.4 Patch rollback/replay

```bash
cd <project_root>
for patch in project-patches/<original project name>/*.patch; do
    git apply --check "$patch"   # dry-run check
    git apply "$patch"           # apply
done
```

### 2.5 Print the path and explain

> **Migration patch files generated**
>
> **Count**: N
> **Directory**: `project-patches/<original project name>/`
>
> **Purpose**: records the Step 1 migration changes, split by directory
> **Uses**: rollback / replay / review / archiving / selective application

## Step 3: Fix build problems and complete the build

### 3.0 Prepare the build environment

```bash
# Kill leftover hvigor daemons
pkill -f 'daemon-process-boot-script'
pkill -f 'hvigor-java-daemon'

# Set the SDK environment variables
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
```

> **DevEco Studio warning**: if DevEco Studio is running, it may **revert external file edits**.
> Quit DevEco Studio before applying fixes: `osascript -e 'quit app "DevEco-Studio"'`

### 3.1 Build the project

```bash
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

### 3.2 Automatically fix build errors

When the build fails, **automatically** read the `fix-build-error/` documents, match the errors, apply the fixes, and rebuild — **without prompting the user**.

**Three escalating layers**:

```
Build fails
  ↓
Layer 1: automatic fixes from fix-build-error/ documents
  ↓ fix succeeded → rebuild (back to the top)
  ↓ fix failed
Layer 2: built-in common-error reference
  ↓ matched → prompt the user to fix manually → rebuild (back to the top)
  ↓ not matched
Layer 3: print the full build error report + project path
  ↓ user fixes manually → rebuild (back to the top, starting from Layer 1)
  ↓ user skips → end
```

**Whenever a rebuild still fails, always retry starting from Layer 1 (the fix-build-error/ documents).**

**Auto-fix format of fix-build-error/ documents**:

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

**Supported action types**:

| Type | Fields | Description |
|------|--------|-------------|
| `replace` | `from`, `to` | String replacement |
| `replace_regex` | `from` (regex), `to` | Regex replacement |
| `remove_include` | `include` | Remove an `#include` line |
| `add_include` | `include` | Add after the last `#include` |
| `remove_line` | `pattern` | Remove lines containing the pattern |
| `rewrite_cmake` | `target`, `qt_dev_dir` | Replace the whole CMakeLists.txt |

#### Layer 2: built-in common-error reference

| Error | Cause | Fix |
|-------|-------|-----|
| `fatal error: 'QtOhExtras/xxx.h' file not found` | Old header path | Replace with `QtOhosExtras/xxx.h` |
| `QOhAppContext was not declared` | Class renamed | Replace with `QOhosAbilityContext` |
| `requestPermissionsSync` | Synchronous API removed | Switch to asynchronous signals and slots |
| `cannot find -lQt5OhExtras` | Old module name | Use `QT += ohosextras` |
| `EPERM: operation not permitted, uv_cwd` | hvigor daemon | Kill leftover daemons |
| `00303217 Configuration Error` | `DEVECO_SDK_HOME` not set | Set the environment variable |
| `00308018 Unknown Error` | CMake execution failed | Check `find_package`/SDK layout |

#### Layer 3: full error report

Printed after all fix attempts fail:
1. The filtered error lines (at most 20)
2. The build command and project path
3. A prompt to open the project in DevEco Studio and fix it manually

### 3.3 CMake / qmake configuration

**Trimmed SDK** (no `lib/cmake/`, no `bin/`) — link by direct path:

```cmake
set(CMAKE_AUTOMOC OFF)
set(QT_OHOS_DEV_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../../third_party/qt-ohos-dev)
target_include_directories(myapp PRIVATE ${QT_OHOS_DEV_DIR}/include/QtCore ...)
target_link_libraries(myapp PRIVATE ${QT_OHOS_DEV_DIR}/lib/libQt5Core.so ...)
```

**Full SDK** (has `lib/cmake/` and `bin/`) — use `find_package`:

```cmake
find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core Gui Widgets Network OhosExtras)
target_link_libraries(myapp PRIVATE Qt5::Core Qt5::OhosExtras)
```

### 3.4 Iterate until there are zero errors

Rebuild after every fix. The migration is complete when `hvigorw assembleHap` succeeds with zero errors.

### 3.5 Refresh the build-fix documents

After the build completes, **refresh the** `build-fix-*.md` **documents that were used** (do not create new timestamped files):

1. Collect the error lines from all build attempts
2. Match them against the existing `build-fix-*.md` documents
3. Covered → refresh (update the date and status, append the latest error output)
4. Not covered → report it in the output summary (do not create a new file)
5. Print the paths of the refreshed documents and prompt the user to upload them

## Step 4: Build a signed hap and test launch

### 4.1 Confirm the signing configuration

Signing is configured in `app.signingConfigs` of `build-profile.json5` (machine-bound automatic signing).

> When building on a different machine, regenerate the signature in DevEco Studio.

### 4.2 Build the signed hap

```bash
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

Output path of the signed `.hap` file:
```
entry/build/default/outputs/default/entry-default-signed.hap
```

### 4.3 Install and launch

```bash
# Check the device connection
hdc list targets

# Install
hdc install entry/build/default/outputs/default/entry-default-signed.hap

# Launch (the ability name is read from module.json5, not hard-coded)
hdc shell aa start -a <ability_name> -b <bundle_name>
```

> **Ability name**: read it from `entry/src/main/module.json5` → `"abilities"[0]."name"`;
> do not hard-code `EntryAbility`.

### 4.4 Verify that launch does not crash

```bash
# Check that the process is alive (with retries)
sleep 2
hdc shell ps -ef | grep <bundle_name>

# Check hilog for crash logs
hdc shell hilog | grep -i "<bundle_name\|FATAL\|crash\|SIGSEGV"

# Check faultlog (only entries new in this run)
hdc shell ls /data/log/faultlog/temp/
```

**Common launch crashes**:

| Crash symptom | Cause | Fix |
|---------------|-------|-----|
| `dlopen failed: libQt5OhExtras.so not found` | The old community-edition library is still referenced | Make sure `libQt5OhosExtras.so` is present |
| `dlopen failed: libqopenharmony.so not found` | QPA plugin name mismatch | Replace with `libqohos.so` |
| `SIGSEGV in QOhosAbilityContext::instance()` | Context not initialized | Defer access until after `QGuiApplication` is constructed |
| `platform "ohos" not available` | QPA plugin missing | Confirm `libqohos.so` is in the platforms directory |

### 4.5 Crash handling

**faultlog timestamp check**: record the existing faultlogs before launch, and after launch check only the new ones.

If a **new faultlog** is detected (a crash in this run):
1. Show the crash log contents
2. Show the table of common crash causes
3. Print: `The application crashed on launch and needs a manual fix by the user. Skipping the crash-handling step.`
4. **Skip this step** — do not enter a fix loop
5. After fixing manually, the user reruns the script to verify

> **No fix loop**: the script does not automatically rebuild and retest after a crash. Crashes usually need manual diagnosis
> (library replacement, plugin path correction, code changes). The script notifies the user and moves on to the next step.

### 4.6 Functional smoke test

Verify that the core migrated features work:

1. **Permission request** — trigger a permission action and confirm the system dialog appears (without blocking the UI)
2. **File sharing** — trigger a share action and confirm the system share panel appears
3. **Window rendering** — confirm the main window displays correctly (QHarmonyStyle)
4. **Theme switching** — if dark mode is used, confirm `setDarkThemeEnabled()` takes effect

## Output directories

| Directory | Purpose | Used in step |
|-----------|---------|--------------|
| `docs/` | Migration reference documents (API differences) | Step 1 — read all documents before migrating |
| `fix-build-error/` | Build-fix documents (error → fix guides) | Step 3 — read and matched automatically when the build fails |
| `project-patches/` | Generated patch files (per directory) | Step 2 (migration) + Step 3.5 (build fixes) |
| `templates/` | Official-edition template project | Step 1.0b — copied automatically to create the new project |

### `docs/` — migration reference

**Root documents** (`docs/*.md`) — common to all Qt versions:
- `SP_DialogSaveAllButton.md` — SP_DialogSaveAllButton API fix
- `delete_include.md` — removal of unused includes
- `screen.md` — QWidget::screen() API fix

**Version-specific documents** (`docs/qt<version>/*.md`) — selected in §1.0:

| Version directory | Documents |
|-------------------|-----------|
| `docs/qt5.12.12/` | `Qt-Ohos-5.12.12-Diff.md` (version differences), `qt_base.md` (basic guide) |
| `docs/qt5.15.16/` | `Qt-Ohos-5.15.16-Diff.md` (version differences) |

> To add a new version: create a `docs/qt<version>/` directory and put the diff document in it.
> To add a root document: just put an `.md` file under `docs/`.

### `fix-build-error/` — build-fix guides

When the build fails, every `.md` file under `fix-build-error/` is read **automatically**, the errors are matched, and the fixes are applied.

Each `build-fix-*.md` contains a **`## Auto-fix`** YAML block that specifies:
- `match`: a regex matching the error
- `files`: the list of source files to modify
- `actions`: the list of fix actions

Current build-fix documents:

| Document | Error | Automatic fix action |
|----------|-------|----------------------|
| `build-fix-04` | CMake `find_package` falls back to the system Qt6 | `rewrite_cmake` |
| `build-fix-05` | QtOhosExtras forwarding header missing | `remove_include` |
| `build-fix-06` | `QWidget::screen()` Qt 5.14+ API | `add_include` + `replace_regex` |
| `build-fix-07` | `SP_DialogSaveAllButton` Qt 5.15+ API | `replace` |
| `build-fix-08` | `compatibleSdkVersion` mismatch | `replace` |
| `build-fix-09` | ohpm `types/libentry` missing | `remove_line` |
| `build-fix-10` | `EPERM: uv_cwd` leftover daemon | Kill daemons (built-in) |
| `build-fix-11` | DevEco Studio reverts edits | Warning (built-in) |
| `build-fix-12` | `DEVECO_SDK_HOME` not set | Set the environment variable automatically (built-in) |

> To add a new fix document: put an `.md` file containing a `## Auto-fix` YAML block under `fix-build-error/`.

### `project-patches/` — generated patch files

- `<original project name>/root.patch` — top-level files
- `<original project name>/<directory path>.patch` — migration patches split by directory

### `templates/` — official-edition template project

An empty official-edition Qt for OpenHarmony project template with the correct build configuration, ArkTS shell, and signing configuration.
Step 1.0b copies this directory automatically to create the new project.
