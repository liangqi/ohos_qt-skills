---
id: problem-build-qt6-host-codegen-and-pango
type: problem
domain: build
tags: [QT_HOST_PATH, moc, rcc, uic, host-tools, cross-compilation, rcc-writes-no-file, pango, DESKTOP_APP_USE_PANGO, tdesktop]
created: 2026-11-18
updated: 2026-11-18
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-third-party-libs]
summary: >
  When cross-compiling, moc/rcc/uic must run from the host kit (QT_HOST_PATH), otherwise configure
  dies right at Qt6::moc; on Windows, the host rcc fails silently when it can't write to the target directory.
  Also: applications that use pango as their text backend should set DESKTOP_APP_USE_PANGO=OFF to use Qt's own
  text layout, avoiding dragging the whole pango chain into the HarmonyOS build.
leader_summary: >
  Spelled out two easily overlooked prerequisites, the "host toolchain" and the "text backend", each with an actionable criterion
impact: [Build system, Cross-compilation]
deliverables: [problem record]
evidence: []

error_message: >
  CMake Error: The following variables are used in this project, but they are
  set to NOTFOUND: Qt6CoreTools_DIR
  # or
  Qt6::moc not found. Set QT_HOST_PATH to a host Qt installation.
  # or rcc exits normally but the target file doesn't exist
  # or every pango/pangocairo-related target fails to build on HarmonyOS
error_code: ""
keywords: [QT_HOST_PATH, Qt6CoreTools, moc, rcc, uic, host kit, cross-compilation,
           rcc writes no file, pango, pangocairo, DESKTOP_APP_USE_PANGO, text backend]
symptoms: "The configure stage reports Qt6::moc/Qt6CoreTools not found; or rcc returns 0 but
  the generated .cpp doesn't exist, so the link is missing symbols; or the pango-related sources fail to build wholesale on the HarmonyOS side"
environment: "Windows host + Qt 6.12 prebuilt kits (harmonyos_arm64_v8a + mingw_64) + OHOS SDK"
---

# Host codegen and the text backend: two hidden configure-time prerequisites

## Symptoms

1. **configure fails right away**: `Qt6CoreTools_DIR` is NOTFOUND, or
   `Qt6::moc not found`, even though the kit clearly has `bin/moc.exe`.
2. **rcc fails silently**: in the build log the rcc step shows `Exit code 0`, but the target `.cpp`
   doesn't exist at all, and later the link reports missing symbols like `qInitResources_*`.
3. **pango fails to build wholesale**: a batch of `pangocairo`/`pangoft2` includes can't be found,
   or they link but the symbols don't match.

## Root cause

**Host codegen**: when cross-compiling, the target platform's Qt libraries can't generate code themselves; moc/rcc/uic
must run on the **host**. Qt6's toolchain relies on `QT_HOST_PATH` to find the host kit's
`lib/cmake/Qt6CoreTools` and the like. When you only give `CMAKE_PREFIX_PATH` (pointing at the target kit),
configure looks for the `*Tools` packages in the target kit first and reports NOTFOUND when it can't find them.

**rcc writes no file**: on Windows, if the host rcc's output directory has permission restrictions, an overly long path,
or is in a read-only location, rcc may return 0 without writing anything to disk. This kind of failure doesn't show up in the exit code; it only
shows up as "missing `qInitResources_*` at link time".

**pango**: pango is a very long dependency chain (pango → pangocairo → cairo →
fontconfig → freetype → harfbuzz → fribidi → glib → ...). Qt has its own complete
text layout implementation; some desktop applications (tdesktop) hook up pango only for better CJK layout.
HarmonyOS has no ready-made builds of this chain, so hooking it up amounts to porting 10 libraries at once.

## Fix

**Use `QT_HOST_PATH` for the host kit** (the Qt6 branch of `tools/qt_ohos/builder.py` already adds it to the configure arguments automatically
from `env.qt_host_sdk`):

```bash
python tools/qt-ohos-run.py config set qt_host_sdk "C:/Qt/6.12.0/mingw_64"
python tools/qt-ohos-run.py config set ohos_sdk_native "<SDK>/native"
python tools/qt-ohos-run.py doctor      # checks the target kit and the host kit separately
```

The corresponding CMake arguments:

```
-DCMAKE_TOOLCHAIN_FILE=<kit>/lib/cmake/Qt6/qt.toolchain.cmake
-DQT_HOST_PATH=<host kit>
-DQT_CHAINLOAD_TOOLCHAIN_FILE=<native>/build/cmake/ohos.toolchain.cmake
-DOHOS_SDK_NATIVE=<native>
```

**rcc writes no file**: put the generated directory on a short path inside the project (for example
`build-ohos/generated`) and confirm the directory is writable; if it still fails, use
`build --record-only --artifacts <glob>` to register externally built outputs, and in the
`patch` stage look at `cand-rcc-write` in the candidate list (it lists the locations of `qt_add_resources`).

**pango**: taking tdesktop as an example, the build switch is `DESKTOP_APP_USE_PANGO=OFF`; with it off,
text uses Qt's own layout, and `lib_ui` no longer needs the whole pango stack.

```bash
python tools/qt-ohos-run.py config set cmake_args "-DDESKTOP_APP_USE_PANGO=OFF"
```

Find similar switches according to the actual project: the criterion is "with this macro off, does the dependency still appear in
`find_package`/`pkg_check_modules`".

## Verification

```bash
python tools/qt-ohos-run.py doctor        # both the target kit and the host kit are present
python tools/qt-ohos-run.py build         # configure no longer reports *Tools NOTFOUND
python tools/qt-ohos-run.py verify        # G4 outputs present, G5 closure complete
```

The first step `plan` generates is `doctor`, precisely so that these two kinds of problems surface before configure
rather than after dozens of compile rounds.

## Related

- [build-qt6-app-must-be-shared](build-qt6-app-must-be-shared.md): the linking model
- `procedural/qt6-ohos-windows-cli-deploy.md`: host tools and the full hvigor flow
- `semantic/qt-harmonyos-third-party-libs.md`: handling long dependency chains like pango
