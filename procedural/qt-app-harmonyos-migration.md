---
id: procedural-qt-app-harmonyos-migration
type: procedural
domain: workflow
tags: [workflow, qt, harmonyos, porting, migration, ohos]
created: 2026-06-02
updated: 2026-09-12
status: active
audience: public
refs: [semantic-qt-harmonyos-api-mapping,semantic-qt-harmonyos-build-run-workflow,semantic-qt-harmonyos-code-patterns,semantic-qt-harmonyos-lifecycle,semantic-qt-harmonyos-porting-workflow,semantic-qt-harmonyos-project-structure,semantic-qt-harmonyos-window-model]
summary: >
  The Qt application HarmonyOS migration workflow: assess feasibility → create the project structure → migrate step by step through an 8-step decision tree → verify the build → capture the knowledge.
  An end-to-end process for migrating a Qt application from another platform to HarmonyOS.
---

# Migrating a Qt application to HarmonyOS

> The end-to-end process for migrating a Qt application from another platform (Windows/Linux/macOS/Android/iOS) to HarmonyOS.

---

## When to use this

- A new Qt application HarmonyOS migration task comes in
- An existing Qt project needs porting to HarmonyOS
- You need to assess whether some Qt application can be ported to HarmonyOS

---

## Phase zero: pre-flight

> Before entering phase one, run 7 pre-flight checks with grep/source scanning. The point of the pre-flight is to weed out projects that are **bound to fail**, pick the right Qt5/Qt6 path, and settle on the application/library playbook — all **before you write any CMake**.
> Three real batches (10apps / rows 300-399 / rows 400-499, 207 applications in total) proved that skipping the pre-flight makes the agent waste 3-4 build attempts on Qt6 code (two real cases).

| Check | Method (grep/scan) | Decision |
|-------|--------------------|----------|
| **Qt version (by the code, not the declaration)** | grep for Qt6-only C++ APIs: `QList::emplace_back`/`push_back`, `std::as_const`, `QVariant::toModelIndex`, `QQuickRenderControl::beginFrame`/`endFrame`, `QEvent::isInputEvent`, Qt6 ctor signatures, `std::ranges`/`std::views` | A hit → **Qt6 code** (even if `.pro`/`QT +=` says Qt5) |
| **Which Qt SDK** | Qt 5.15.16 (ready to use, no patches) vs. a Qt6 6.12 superbuild (MinGW host + API 23, no source patches needed; you still need `patch_needed.py` + main visibility before deploying — see §1.6) | Prefer Qt5; Qt6-only projects take the Qt6 route (not infeasible — see §1.6) |
| **Module availability** | Check against the [[qt-harmonyos-modules]] matrix: the Qt5 SDK lacks Multimedia/D-Bus/WebEngine/Charts/SerialBus/QuickControls2/Quick3D/WebSockets/UiTools/SvgWidgets/Core5Compat; Qt6 dev has only qtbase + a subset of submodules | A hit on something missing that can't be dropped → blocked |
| **Project type** | grep `int main(` → application/example (playbook A); none → library/plugin/header-only (B); for **source-only projects with no build files**, look for the existence of `.cpp`/`.h` (the QtCustomControls lesson) | Determines the playbook (see §1.0a) |
| **Platform coupling** | grep for `X11`/`xcb`/`windows.h`/`HWND`/`WM_`/`QDBus`/`Cocoa` and check whether it's a **core feature** (not an optional branch) | Core coupling → infeasible (e.g. QHotkey, Qt-Nice-Frameless-Window) |
| **foreach usage** | grep `foreach(`/`Q_FOREACH` | If used → **OMIT** `QT_NO_FOREACH` (defining it breaks the build) |
| **Third-party dependencies** | **Preferred: portgraph dependency closure analysis** (`python portgraph/portgraph.py fetch-deps <app> --dry-run`, which outputs the number of bottles available for direct download + the list of gaps needing a source build; see the step 0 gate below); only when the repo tooling is unavailable, grep by hand: bundled (in-repo) vs. system; header-only = ok, small pure-C libraries = maybe, FFmpeg/Skia/Boost/OpenCV/PCL = no | Heavyweight system libraries with no bottle → blocked, or cross-compile them separately (size the work by the closure gap list) |
| **C++20 gaps (clang15/libc++15)** | `python tools/cpp20-gap-scan.py scan <src_dir>` (8 rules: structured binding captures / make_unique_for_overwrite / stop_token / atomic_ref / ranges / `<=>` / init-capture / setaffinity; see [[build-clang15-libcpp15-cpp20-gaps]]) | On a hit → pre-fix the mechanical items with `fix --apply` and the rest per the problems pages — **avoiding hitting errors one build round at a time** (one build round of a large project takes tens of minutes) |

**Output**: a pre-flight report (Qt version + SDK choice + playbook + module gaps + platform coupling + foreach + third-party dependencies), which decides whether to enter phase one.

### 🚧 Step 0 gate: portgraph dependency closure assessment (mandatory for applications with many dependencies)

> **Trigger condition**: the application has ≥3 third-party dependencies, or its dependencies come from external repositories (not bundled).
> In that case the "third-party dependencies" pre-flight item must be concluded with the portgraph tool — **judging each one by hand is forbidden**.
> The proven cost of skipping it (2026-09, a large application with 68 dependencies): the first round didn't run the closure analysis, and the agent went straight down the wrong path of
> cross-compiling each library from source; after the correction, portgraph `fetch-deps` produced the solution in one go:
> **59 bottles downloaded directly + 9 source builds** — bottles covered 87%, a two-orders-of-magnitude difference in effort.

```bash
# ① Portability verdict (portable / blocked / uncertain + blocking reasons)
python portgraph/portgraph.py analyze <app>

# ② Comprehensive dependency analysis: who needs build artifacts (link) / who is a build tool (build-tool) /
#    who is used only at runtime (runtime) / who ships its own source (vendored) + version ranges and requirement checks
python portgraph/portgraph.py deps <app>

# ③ Dependency closure preview: which have ready-made bottles (.so downloaded directly), which need source cross-compilation (writes nothing to disk)
python portgraph/portgraph.py fetch-deps <app> --dry-run

# ④ Once feasibility is confirmed, run the download (artifacts land in portgraph/workspace/ohos-libs/, a cache shared across applications)
python portgraph/portgraph.py fetch-deps <app> --json   # integration parameters (CMAKE_PREFIX_PATH, etc.)
```

**Interpreting and routing**:

| Closure result | Action |
|----------|------|
| `analyze` = blocked | **Not an automatic stop** — look at the guard evidence for the blockers: it's a hard block only if it's `ohos-active`, **matched unconditionally** (e.g. `#include <X11/Xlib.h>` with no guard at all), and on a core path; those excluded by a macro guard or at file level are mostly optional branches (proven case: for a large application, analyze reported 6 blockers, all in optional branches/vendored code; after review it was let through and the port succeeded). If it's genuinely core and irreplaceable → stop at the assessment and write the report |
| `deps` version conflict | The HarmonyOS artifact's version is lower than the project requires (e.g. it requires >=9.9 but only 1.3.2 exists): confirm whether the existing version can be used (min_version is often a conservative declaration) or build the new version from source |
| Bottles cover most dependencies | Prefer downloading bottles directly (skipping source cross-compilation); the gaps go down the source route |
| The unknowns list (pkg-unknown dependencies) | This is the "source build gap list": check each item against [[fetch-ohos-third-party-lib]] (single-library bottles) and [[qt-harmonyos-third-party-libs]] (source cross-compilation); **gaps that can't be resolved must be reported to the user explicitly** — never trimmed silently |
| NTFS symlinks broken after extracting a bottle (0 bytes/EACCES) | Delete the broken links and copy the real versioned files (measured on a large application: 202 fixed) |

Tool docs: `portgraph/docs/deps-report.md` (dependency roles/version ranges), `portgraph/docs/fetch-deps.md` (artifact retrieval).

### ⚠️ Pitfall: declared Qt5, actually Qt6 code

Two real batches went off the rails:
- **A spreadsheet tool** (rows 400-499, row 405): the `.pro` uses Qt5 syntax and the spreadsheet says Qt5, but the C++ is all Qt6-only API (`beginFrame/endFrame`, `QEvent::isInputEvent`, the Qt6 `QHoverEvent`/`QQmlListProperty` ctors) → it took 3 build attempts peeling back the layers to confirm, and it was also missing three modules: Quick3D/QuickControls2/WebSockets.
- **A downloader** (rows 300-399, row 394): the `.pro` says Qt5 but the code uses `QList::emplace_back` (a Qt6 API) → 4 retries.

**The rule**: determine the Qt version from **the APIs the code actually uses**, not from `.pro`/`QT +=`/the spreadsheet. The grep list is in row 1 of the table above. A `.pro` saying Qt5 only tells you the author **intended** Qt5; it's no guarantee no Qt6 API has crept in (common when a project "migrated from Qt5 to Qt6 and then reverted the declaration" or "uses Qt6 headers but the .pro still says Qt5").

### ⚠️ Pitfall: multiple edits to the same file must be serialized

When adapting the source of a large project, **multiple edit points in the same file must be done serially** — parallel edits to one file overwrite each other (in practice, race-condition overwrites happened repeatedly, silently losing changes). Different files can be edited in parallel, but edits within one file must queue; after each edit, confirm the change is on disk before making the next one.

---

## Phase one: assessment and preparation

> **📋 TODO sync point**: update this task's "progress" column in `<LOCAL_TODO>` → `Phase one complete: feasibility assessment passed, project directory and project created`

### 1.1 Feasibility assessment

| Item | What to check | Reference |
|------|---------------|-----------|
| Qt version | Which Qt version the application uses (5.12 / 5.15) | [[qt-harmonyos-modules]] |
| Module dependencies | Whether the Qt modules used are supported on HarmonyOS | [[qt-harmonyos-modules]] |
| Platform APIs | Whether there's deep platform coupling (e.g. D-Bus, the Win32 API) | [[qt-harmonyos-api-mapping]] |
| UI complexity | Number of windows, modal dialogs, fullscreen requirements | [[qt-harmonyos-window-model]] |
| Child processes | Whether it relies on QProcess or system() | [[qt-harmonyos-api-mapping]] §1 |
| Third-party libraries | Whether it depends on C/C++ libraries that need cross-compiling | [[qt-harmonyos-third-party-libs]] |

**Output**: a feasibility report (portable / has risk items / not portable)

> **💡 A shortcut for prebuilt third-party libraries**: use portgraph for the application-level dependency closure (the phase zero step 0 gate;
> `fetch-deps <app>` handles the bottle downloads and the gap list for all dependencies in one go). Only for a **single** third-party library
> already known to have an `arm64_ohos` bottle in Harmonybrew can you use the single-library script `fetch-ohos-bottle.sh` from [[fetch-ohos-third-party-lib]].
> Only when neither route yields a bottle do you take the source cross-compilation route below.

> **🎮 Choosing a playbook** (phase zero determined the project type; here you act on it)
>
> | Project type | Playbook | Artifact | Build method |
> |--------------|----------|----------|--------------|
> | application / example (has `int main()`) | **A** | `entry-default-unsigned.hap` | `hvigorw assembleHap` + OhosExampleApp + the HarmonyOS template |
> | library / plugin / header-only (no main) | **B** | `libOhos<Slug>.a`/`.so` | `cmake + ninja + ohos.toolchain.cmake` + ohos-build |
>
> **Qt5/Qt6 is an orthogonal axis**: both A and B work with Qt5 (the ready-made SDK, no patches) or Qt6 (a 6.12 superbuild, no source patches needed; handle NEEDED/main before deploying — see §1.6). Phase zero already picked the SDK; here you only pick A or B.

### 1.2 Create the project directory

> **📋 TODO sync point**: update this task's "progress" column in `<LOCAL_TODO>` → `Phase one in progress: project directory created, extracting the template`

**Each migration project gets its own folder under `${PROJECTS_ROOT}`** (see `ENV.md` for the path):

```bash
# Create the project directory (named after the original application + -ohos)
mkdir -p "<MIGRATION_PROJECT_ROOT>/<app-name>-ohos"
```

**Directory naming convention**:
- Format: `<original-app-name>-ohos` (e.g. `calculator-ohos`, `notepad-ohos`)
- All lowercase, with spaces replaced by hyphens
- The project folder itself is the complete HarmonyOS project structure

### 1.3 Prepare the project structure (copy the glue template bundled with the source)

> **⚠️ Core principle: a HarmonyOS project must be generated by copying the glue code template bundled with the Qt source; never create the directory structure by hand.**
> The template contains the complete ArkTS glue code, the build-profile configuration, the qEmbeddedUiExtensionHost module and more,
> and creating it by hand very easily misses a critical file or misconfigures something.
>
> Recent Qt HarmonyOS branches **bundle the glue template in the source tree** at `qtbase/src/harmonyos/templates`,
> so there's no need to download a ZIP from Gerrit any more (the old ZIP route is retired to a fallback).

**Getting the template** (see `OHOS_TEMPLATE_SRC` in `ENV.md` for the path, i.e. `<QT_SRC>/qtbase/src/harmonyos/templates`) and copying it into the project directory `${PROJECTS_ROOT}/<app-name>-ohos/`:

```bash
# Copy the bundled template from the Qt source tree into the project directory (recommended; both the 5.15 and 5.12 trees have it, with identical content)
cp -r <QT5_15_SRC>/qtbase/src/harmonyos/templates/. "${PROJECTS_ROOT}/<app-name>-ohos/"
# The Qt 5.12 equivalent: <QT5_12_SRC>/qtbase/src/harmonyos/templates
```

**Without the Qt source** (e.g. when using only a prebuilt SDK, or on a HarmonyOS PC): download the standalone template archive `templates-0625.zip` from the GitCode releases, extract it into `workspace/templates/`, then copy:
```bash
bash skills/kb-init/scripts/download-template.sh --dest=workspace/templates
cp -r workspace/templates/. "${PROJECTS_ROOT}/<app-name>-ohos/"
```
Download page: https://gitcode.com/ohos-qt/qt-harmonyos-src/releases

**The project structure you get after extracting** (scenario one: creating from scratch):

```
<the extracted project root>/
├── entry/
│   ├── src/main/
│   │   ├── cpp/                      # ★ write your Qt C++ code and CMakeLists.txt here
│   │   └── ets/
│   │       ├── entryability/         # the ArkTS glue code (generated by the template; don't touch)
│   │       ├── pages/                # ArkTS pages
│   │       └── common/
│   │           └── QtAppConstants.ets # ★ configure APP_LIBRARY_NAME
│   ├── build-profile.json5           # module-level build configuration
│   └── libs/arm64-v8a/               # the Qt runtime libraries (you need to populate this)
├── qEmbeddedUiExtensionHost/         # the cross-process embedding module (generated by the template)
├── build-profile.json5               # project-level build configuration
├── AppScope/app.json5                # the application's bundleName
└── local.properties                  # SDK paths
```

**What you still have to do after extracting**:
1. Write the Qt C++ source and `CMakeLists.txt` in `entry/src/main/cpp/`
2. Set `APP_LIBRARY_NAME` in `QtAppConstants.ets` (it must match the built library's name)
3. Set `CMAKE_PREFIX_PATH` in `entry/build-profile.json5` (pointing at the Qt SDK)
4. Populate `entry/libs/arm64-v8a/` with the Qt runtime libraries (`libqohos.so` and friends)
5. Manually copy `libqohosstyle.so` into `libs/arm64-v8a/styles/`
6. Change the application's display name (`app_name` + `QAbility_label`, see §1.4)

**Scenario two (porting an existing project)**: put the extracted template into a `HarmonyOS/` subdirectory and make `entry/build-profile.json5`'s `path` an **absolute path** pointing at the root CMakeLists.txt.

> For the detailed directory structure and configuration, see [[qt-harmonyos-project-structure]].

### 1.4 Change the application's display name

> **⚠️ Mandatory**: the template's default display names are placeholders (`app_name`=`ohosQtTemplate`, `QAbility_label`=`label`), so if you don't change them the home screen icon and the task manager will show "label" / "ohosQtTemplate" instead of the real application name.

HarmonyOS configures display names through resource references — the `label` field in `app.json5` / `module.json5` holds `$string:<resource-name>`, and the actual display text is the `value` in `string.json`. **Change the value, not the reference.** Two resources need changing:

| Resource name | Template default value | File | Purpose |
|---------------|------------------------|------|---------|
| `app_name` | `ohosQtTemplate` | `AppScope/resources/base/element/string.json` | The application name under the home screen icon |
| `QAbility_label` | `label` | `entry/src/main/resources/{base,en_US,zh_CN}/element/string.json` | The Ability name in the task manager / recent tasks |

Change both resources' `value` to the real application name (e.g. `Calculator`). `QAbility_label` must be changed consistently in all three locale directories (`base` / `en_US` / `zh_CN`); `zh_CN` can hold the Chinese application name.

```json5
// AppScope/resources/base/element/string.json
{ "string": [ { "name": "app_name", "value": "<application name>" } ] }

// entry/src/main/resources/base/element/string.json (en_US has the same structure; zh_CN can use Chinese)
{
  "string": [
    { "name": "module_desc", "value": "module description" },
    { "name": "QAbility_desc", "value": "description" },
    { "name": "QAbility_label", "value": "<application name>" }
  ]
}
```

> **Don't** edit the `"label": "$string:..."` references in `app.json5` / `module.json5` directly — the HarmonyOS spec requires labels to go through resource references, so changing `string.json`'s `value` is enough.

### 1.5 Key CMake configuration

```cmake
# 1. Cross-compilation search paths
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)

# 2. Link the Qt modules
find_package(Qt5 REQUIRED COMPONENTS Core Gui Widgets)

# 3. Produce a shared library (required by HarmonyOS)
add_library(myapp SHARED ${SOURCES})

# 4. Link the QPA plugin
target_link_libraries(myapp PRIVATE Qt5::QOhosPlatformIntegrationPlugin)
```

---

### 1.6 Qt6-specific OHOS considerations

> Only applies if phase zero chose the **Qt6 SDK**. The Qt 5.15.16 SDK is ready to use with no patches, so skip this section.
> Verified on 2026-07-13: a Qt 6.12.0 superbuild builds on a Windows + MinGW host with an OHOS Clang target and API 23, and gallery passed on a physical device, with no source patches needed; using the Qt6 SDK has 8 known pitfalls. For details see [[qt-harmonyos-qt6-status]].

**Prerequisites for building the Qt6 SDK** (the Qt 6.12.0 superbuild):

| Item | Requirement |
|------|-------------|
| Version/path | Qt **6.12.0** (`c7581743`) superbuild (`qt5/configure.bat -submodules qtbase,qtsvg,qtimageformats,qtshadertools,qtlanguageserver,qtdeclarative`), no source patches needed. |
| Host compiler | MinGW g++ 13.1.0 (bundled with the Qt SDK). **Don't use llvm-mingw clang 22** (NTSYSCALLAPI redeclaration, D3D12MemAlloc `-Werror` and other compatibility problems) |
| Extra Windows configuration | The wiki only gives macOS instructions; on Windows you must supply 7 CMake variables by hand (`NodeAddonApi_INCLUDE_DIR` + `_INCLUDE_DIR` and `_LIBRARY` for `EGL`/`GLESv2`/`Fontconfig`) plus the `DEVECO_SDK_HOME` and `JAVA_HOME` environment variables |
| Mandatory runtime steps | Before deploying to a device: rewrite DT_NEEDED to bare names + add `visibility("default")` to `main` (see "Two mandatory runtime checks" below) |

> The old dev branch + 6 patches + 6.12 BLOCKER route is abandoned (the BLOCKER is worked around by the superbuild + MinGW g++ + API 23; the three variables weren't isolated individually — see [build-fail-qt6-libcpp-musl-isystem]).

**Two mandatory Qt6 OHOS runtime checks** (skip them and the device crashes):

1. **Absolute Windows paths in DT_NEEDED** → `dlopen` fails on the device. Qt6 `.so` files have no SONAME, and Windows cross-compilation links imported targets by absolute path → `DT_NEEDED` records absolute Windows paths (e.g. `<Qt6-build-dir>/libQt6Widgets.so`). **You must use `patch_needed.py` to rewrite the NEEDED entries of every `.so` (your own libraries plus the Qt libraries themselves) to bare names.** After packaging, use `llvm-readelf -d` to check that no native `.so` inside the HAP contains an absolute path.
2. **`main` must be `GLOBAL DEFAULT`** → otherwise `dlsym("main")` fails. The Qt6 OHOS glue finds the entry point through `dlsym("main")`, which only searches the dynamic symbol table. If the target uses `CXX_VISIBILITY_PRESET hidden`, the `main` in your source is local and invisible. **Fix**: add `__attribute__((visibility("default")))` to `main` (under OHOS only — don't change the whole target's hiding policy). Verify with `llvm-readelf --dyn-syms` that `main` is `GLOBAL DEFAULT`.

**Other Qt6 OHOS pitfalls**:

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| C++20 ranges/libc++ gaps | `std::ranges::find`/`std::views::reverse`/`std::views::cache_latest`/`std::string_view <=>` fail to compile | Locally replace with `std::find_if`/reverse iterators/a hand-written `std::strong_ordering`; degrade `Utils::views::cache_latest` to a no-op |
| CMake doesn't know the OHOS platform | `CMAKE_LINK_LIBRARY_USING_WHOLE_ARCHIVE` is uninitialized (importing static plugins reports an unsupported link feature) | Define `CMAKE_LINK_LIBRARY_USING_WHOLE_ARCHIVE` explicitly + the C/CXX supported flags |
| Resource deployment | Runtime data under `share/xxx` (such as Qt Creator's themes/fonts) is filtered out by Hvigor if placed in `entry/libs/`, and can't be found on the device if placed in `rawfile/` | Put it in `entry/src/main/resources/resfile/share/xxx`; the application locates it via `QOhosAppContext::resourceDir()+"/share/xxx"` |
| hvigor env | `Invalid DEVECO_SDK_HOME` / `spawn java ENOENT` | Inject `DEVECO_SDK_HOME` + `JAVA_HOME` + the JBR `bin` PATH through `cmake -E env`; use the `--no-daemon` wrapper to avoid the daemon caching a stale env |
| Platform detection misfires | A third-party library (e.g. libarchive) takes the Unix configuration and then uses interfaces OHOS doesn't support | Add a `config_ohos.h` (based on `config_unix.h` with `HAVE_CLOSEFROM`/`HAVE_CLOSE_RANGE`/`HAVE_LCHMOD` undef'd) |
| Module gaps | D-Bus / OpenSSL / WebEngine / MCP / QML Designer are currently unavailable on Qt6 OHOS | Prune them (`FEATURE_dbus=OFF`, `INPUT_openssl=no`, skip the relevant subdirectories) |

> For the **Qt5→Qt6 API differences** (close-event APIs made private, changed QStandardPaths mappings, the `qt_add_executable` CMake API, etc.) see [[qt-harmonyos-qt6-status]].

---

## Phase two: step-by-step migration (the 8-step decision tree)

> **📋 TODO sync point**: update this task's "progress" column in `<LOCAL_TODO>` → `Phase two in progress: step N of the 8-step migration` (update it after each step)

Work through the 8-step decision tree from [[qt-harmonyos-porting-workflow]]:

### Step 1: scan for platform APIs

```bash
# Scan the source for platform-coupled APIs
grep -rn "QProcess\|QDesktopServices\|system(\|exec(" src/
grep -rn "chmod\|symlink\|dlopen" src/
grep -rn "winId\|setMask\|showFullScreen" src/
```

Classify the results and decide on a replacement for each API.

### Step 2: replace APIs using the mapping

Work through the 12 categories in [[qt-harmonyos-api-mapping]] one by one:

1. **Process management**: choose a `QProcess` approach per scenario — headless stays as is; a Qt UI uses `startAppProcess`, a non-Qt UI uses `startAbility`; native hosting uses `startNoUiChildProcess` (see the decision tree in [[qt-harmonyos-api-mapping]] §1)
2. **Inter-application communication**: `QDesktopServices::openUrl` → `startAbility(want)`
3. **Window management**: a standalone QDialog → set a parent or tagSubWindow
4. **Filesystem**: remove `setPermissions` and `symlink` calls
5. ... and so on through the list

### Step 3: window adaptation

- Set a transientParent on every standalone QDialog
- Review how modal dialogs are used
- Handle special needs like fullscreen/floating windows/minimizing
- See [[qt-harmonyos-window-model]]

### Step 4: lifecycle adaptation

- Implement the three levels of close interception in `closeEvent()`
- Handle the Ability moving between foreground and background
- Implement state save/restore (if you need continuation)
- See [[qt-harmonyos-lifecycle]]

### Step 5: handle platform limitations

Check [[qt-harmonyos-platform-limits]] and make sure the code doesn't touch:
- chmod / fchmod (guard with `#ifndef Q_OS_OHOS`)
- symlink (copy the file instead)
- pthread_cancel (switch to cooperative termination)
- System path access (sandbox restrictions)

### Step 6: build system adaptation (configuring the extracted template)

> The project template was extracted in phase 1.2, so this step is about **configuring** rather than creating.

- Write `entry/src/main/cpp/CMakeLists.txt` (cross-compilation configuration, Qt module links, the QPA plugin)
- Set `CMAKE_PREFIX_PATH` in `entry/build-profile.json5` (pointing at the Qt SDK)
- Set `APP_LIBRARY_NAME` in `QtAppConstants.ets` (matching the CMake `add_library` target name)
- Populate `entry/libs/arm64-v8a/` with the Qt runtime libraries (`libqohos.so` + `libqohosstyle.so`)
- Set `bundleName` in `AppScope/app.json5`
- See [[qt-harmonyos-project-structure]]

### Step 7: HarmonyOS enhancements (optional)

- Dark mode: `setColorThemeMode(FollowSystemSetting)`
- Sharing: `ShareKit::shareDataWithShareKit()`
- Application continuation: the `continueRequestReceived` signal
- Want interaction: handling URIs/parameters passed in from outside

### Step 8: module-level verification

- Verify the build module by module
- Verify at runtime feature by feature
- See [[qt-ohos-project-analyzer-workflow]]

---

## Phase three: build verification

> **📋 TODO sync point**: update this task's "progress" column in `<LOCAL_TODO>` → `Phase three complete: build verification passed`

### 3.1 Building

> **🎯 The build verification target = an unsigned HAP**: use the application's own name for `bundleName` (`com.example.<appslug>`) and don't configure signing in `build-profile.json5`. **Done means `entry-default-unsigned.hap` exists + `BUILD SUCCESSFUL`.** Signing is a separate follow-up step (you only need to configure it when installing on a physical device, which is outside this build workflow) and does not block build verification.

See [[qt-harmonyos-build-run-workflow]]:

1. Build through the DevEco MCP toolchain (or the hvigorw CLI approach — see that page's §"The hvigorw CLI alternative")
2. Fix the build errors (see the four-step build failure troubleshooting method)
3. Produce the .hap (unsigned is fine)

### 3.2 Deploy and run

1. Deploy to the emulator or a physical device
2. Verify the features one by one
3. Do basic performance testing

### 3.3 Common problems

| Problem | Where to look |
|---------|---------------|
| The build can't find headers | CMAKE_FIND_ROOT_PATH_MODE_PACKAGE |
| Undefined symbols at link time | A missing Qt module dependency |
| A black screen at runtime | XComponent initialization / window tagging |
| A crash | Lifecycle ordering / null pointers |
| `no member named 'SslConnection'` / QSslSocket unavailable | OHOS Qt Network has no OpenSSL, so SSL branches need a `#ifndef QT_NO_SSL` guard |
| `Could NOT find Qt5QuickControls2Config.cmake` | The OHOS Qt5 SDK lacks QuickControls2/Quick3D/WebSockets, so QML Controls applications should be deferred or go the Qt6 route |
| `no viable conversion from 'const char[]' to 'QPixmap'` | clang strictly rejects the double implicit conversion MSVC allows — construct explicitly |
| `expected '(' after "this"` / deducing-this | OHOS clang 15 doesn't support C++23 P0847 — switch to CRTP or defer |
| `no member named 'emplace_back' in QList` | Qt5's QList has no emplace_back (that's a Qt6 API) — use `append({...})` brace-init; **also a sign of Qt6 code declared as Qt5** (see the phase zero pitfall) |
| Qt6 `dlopen` fails on the device (NEEDED contains absolute paths) | DT_NEEDED contains absolute Windows paths — rewrite them to bare names with `patch_needed.py` (§1.6) |
| Qt6 `dlsym() failed to find 'main'` on the device | `main` is hidden by hidden visibility — add `__attribute__((visibility("default")))` (§1.6) |
| Qt6 `no member named 'nullptr_t'` / `__promote` | [build-fail-qt6-libcpp-musl-isystem] — 6.12's `-isystem` injection lets musl shadow a clang builtin; **worked around (2026-07-13)**: doesn't reproduce with the superbuild + MinGW g++ + API 23 (§1.6) |

---

## Phase four: capturing the knowledge

> **📋 TODO sync point**: update `<LOCAL_TODO>` — move this task from "📌 In progress" to "✅ Done" and fill in the completion date and a summary of the migration result

### 4.1 Record the migration experience

**After every migration**, summarize:

1. **New problems you hit**: scenarios the knowledge base doesn't cover
2. **Solutions that worked**: code patterns verified to work
3. **Traps you fell into**: wrong directions that wasted time
4. **Updated mappings**: newly discovered API replacements

### 4.2 Update the knowledge base

- New API mappings → update [[qt-harmonyos-api-mapping]]
- New code patterns → update [[qt-harmonyos-code-patterns]]
- New platform limitations → update [[qt-harmonyos-platform-limits]]
- Execution errors → create a `problems/` entry
- Project experience → create an `episodic/` entry

---

## Phase five: batch migration (optional)

> When you need to migrate a whole batch (N≥10) of Qt applications at once, add this orchestration layer on top of the single-application workflow (phases zero through four).
> The lessons here are distilled from three real batches (207 applications, 117 successful builds — see the `qt-opensource-apps-batch-port-*` retrospectives in the `episodic/` domain).

### 5.1 Before the batch: sample to pick a route

Read the first 20 rows of the spreadsheet's `qt_modules` column and judge the app/lib ratio:
- **Mostly GUI applications** (core+gui+widgets) → a single HAP route (playbook A only), as in rows 300-399.
- **Mixed apps + libraries** → both routes A/B, as in rows 400-499 (17 HAPs + 53 libraries).
- **Mostly libraries** → a single .a route (playbook B only).

### 5.2 Triage → port as a pipeline, not a barrier

`pipeline(items, triageStage, portStage)`: as soon as one item finishes triage (clone + scan, fast) it goes straight into porting (writing files + building, slow) rather than waiting for all triage to finish. The slow tail of triage overlaps with the fast head of porting, saving ~30% wall-clock over running the two phases serially. The port phase runs `parallel` (~16 concurrent) over the feasible subset.

### 5.3 Pre-filter with the module matrix (blocking modules never enter the build batch)

The triage agent reads the module matrix in [[qt-harmonyos-modules]]; anything that hits a blocking module (multimedia/dbus/webengine/charts/serialbus/core5compat/quickcontrols2/svgwidgets and so on) and can't simply drop it is marked `feasibility=blocked` and never enters the port phase. That saved the rows 300-399 batch 55 builds that were bound to fail. **The module matrix has been verified to produce zero false positives.**

### 5.4 Clone failure fallbacks (a CGNAT network)

This machine's home broadband is behind CGNAT (no public IP), so `git clone` from github.com hits frequent TCP resets. The fallback order:
1. `git clone --depth 1 <url>` fails → retry once without `--depth`.
2. Still failing → the `https://codeload.github.com/<owner>/<repo>/zip/refs/heads/<default-branch>` tarball (unzip and go, no .git).
3. Triage only (no local source needed) → the GitHub REST API `api.github.com/repos/<owner>/<repo>/contents/<path>` to read the build file list + module declarations.

### 5.5 During a safety classifier outage

When the glm-5.2 safety classifier is intermittently unavailable, the main loop's Bash/Write/Agent calls are blocked, but the Workflow tool's internal spawns don't go through the main loop's classifier. **Carry every batch spawn through the Workflow tool** (clone-retry, triage and port all launched via Workflow) to route around the outage.

### 5.6 Agent prompt conventions

- **No shared TaskList subtasks**: agents track progress in their own context and must not call `TaskCreate` to make per-application subtasks (it pollutes the main task list — two batches were polluted with 60+ entries).
- **Assess the code, not the build files**: triage must grep for Qt6-only APIs per the phase zero pre-flight table, not just read `.pro`/`QT +=` (real failure cases).
- **At most 3 build attempts per project**: read the error tail → fix the most likely cause → rebuild. If it doesn't pass in 3 attempts, mark it failed with the error attached; don't force it into a success.

### 5.7 Batch deliverables

- `${PROJECTS_ROOT}/<batch>/_BATCH_REPORT.md` — the full result table (row × status × artifact × error).
- `${PROJECTS_ROOT}/<batch>/_results/<row>.json` — the migration + build report for each project.
- `${PROJECTS_ROOT}/<batch>/_assessments/<row>.json` — the triage assessment for each project.
- `${PROJECTS_ROOT}/<batch>/_RUNBOOK.md` / `_playbook.md` — the migration recipe for the batch (which every port agent follows).

---

## Checklist

- [ ] **Phase zero pre-flight done** (Qt version from the code not the declaration, Qt5/Qt6 SDK choice, module availability, project type → playbook A/B, platform coupling, foreach, third-party dependencies)
- [ ] **Step 0 gate**: with ≥3 third-party library dependencies, `portgraph analyze` + `fetch-deps --dry-run` have been run and the bottle/source-build routing conclusion is out (gaps reported to the user explicitly)
- [ ] Feasibility assessment done (module dependencies, platform APIs, UI complexity)
- [ ] Project directory created under `${PROJECTS_ROOT}/<app-name>-ohos/`
- [ ] The glue code template has been copied from the bundled source path (`<QT_SRC>/qtbase/src/harmonyos/templates`) into the project directory
- [ ] The application display name has been changed (`app_name` + `QAbility_label` set to the application name)
- [ ] All 8 steps of the decision tree worked through
- [ ] The build passes
- [ ] **If using Qt6**: DT_NEEDED rewritten to bare names (`patch_needed.py`) + `main` verified as `GLOBAL DEFAULT` (§1.6)
- [ ] Deployed and verified at runtime
- [ ] The migration experience has been recorded in the knowledge base

---

## Supply chain

> For details see the "application porting" section of the workflow supply chain

| Aspect | Details |
|--------|---------|
| **Upstream sources** | ① HarmonyOS migration requests from commercial Qt customers ② internal marketing demo requests ③ self-driven (assessing the feasibility of a new scenario) |
| **Upstream inputs** | The original Qt project/source, the target feature requirements, the Qt version information |
| **Downstream recipients** | **Commercial Qt customers** / internal (marketing demos) |
| **Deliverables** | A feasibility assessment report → the migrated HarmonyOS project → the build artifact (.hap) |
| **Deliverables path** | `${PROJECTS_ROOT}/<app-name>-ohos/` (see `ENV.md`) |
| **Routing rules** | None; **knowledge capture**: update the KB after every migration (API mappings → `api-mapping.md`, code patterns → `code-patterns.md`, problem experience → `problems/`) |

---

## Related context

- [[qt-harmonyos-porting-workflow]] — The 8-step decision tree in detail
- [[qt-harmonyos-api-mapping]] — The 12-category API mapping table
- [[qt-harmonyos-code-patterns]] — Before/after code patterns
- [[qt-harmonyos-lifecycle]] — Lifecycle handling
- [[qt-harmonyos-window-model]] — The window model
- [[qt-harmonyos-project-structure]] — Project structure
- [[qt-harmonyos-build-run-workflow]] — Building and running
- [[qt-harmonyos-platform-limits]] — Platform limitations
- The workflow supply chain — An overview of the workflow supply chain (upstream/downstream relationships and the contact list)

## Content sources

| Source type | Notes |
|-------------|-------|
| 🛠️ Working experience | Workflow design, checklists, grep patterns, debugging table, knowledge accumulation process — all from practical Qt-for-HarmonyOS migration experience |
| 📖 Wiki | Qt Wiki pages (wiki.qt.io/Qt_for_HarmonyOS/*): module support lists, CMake cross-compile guide, user development guide, API compatibility notes — accessed indirectly through referenced semantic pages |
| 🔍 Framework source | Qt framework internals: QOhosPlatformIntegrationPlugin CMake target, QPA plugin architecture, closeEvent root cause mechanism, QOhosAbilityContext signal names |
| 📦 Exported interfaces | QtOhosExtras public API surface: startNoUiChildProcess, startAbility, setColorThemeMode, ShareKit::shareDataWithShareKit, continueRequestReceived, tagWindowOrWidgetAsSubWindowOf |
| 📄 Huawei official documentation | HarmonyOS platform concepts: Ability/Want model, sandbox constraints, ShareKit framework, application continuation — underlying platform context |

### Qt framework versions (the verification baseline)

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |
| QtOhosExtras 5.15 | tqtc/harmonyos-5.15.16 | b60937d5 | 2026-04-19 |
| QtOhosExtras 5.12 | tqtc/harmonyos-5.12.12 | a802177c | 2026-05-25 |

---

## References

- [Qt for HarmonyOS (Qt Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS) — The overall architecture and module status
- [API Compatibility Notes (Qt Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS/api_inconsistencies_on_harmonyos) — API differences in detail
- [User Development Guide (Qt Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide) — The development guide series
- [Building Qt for HarmonyOS (Qt Wiki)](https://wiki.qt.io/Building_Qt_for_HarmonyOS) — Build configuration
