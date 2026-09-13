---
id: procedural-qt6-ohos-manual-deploy
type: procedural
domain: deploy
tags: [qt6, qt6.12, harmonyos, ohos, deploy, manual, harmonydeployqt6, workaround, qml, hap, windows]
created: 2026-08-06
updated: 2026-08-06
status: active
audience: public
refs: [procedural-qt6-ohos-windows-cli-deploy, semantic-qt-harmonyos-qt6-status, semantic-qt-harmonyos-project-structure]
summary: >
  A manual deployment process that works around the 5 deployment defects in harmonydeployqt6 (Qt 6.12 Beta2): copy the DevEco project skeleton from the SDK templates
  + manually deploy the business .so + libqohos + the Qt6 runtime + the QML module qmldir files + the QML plugin .so files + the QML plugins' Qt6 dependencies
  into the right locations (libs/ vs resfile/qml/) + configure APP_LIBRARY_NAME + build with signing. harmonydeployqt6 is never invoked.
---

# Manual Qt 6.12 OHOS deployment (working around harmonydeployqt6's 5 bugs)

> **Purpose**: `harmonydeployqt6` (the Qt 6.12 Beta2 prebuilt) has 5 deployment defects (see the pitfall table in [[qt6-ohos-windows-cli-deploy]] §8, and the harmonydeployqt6 defect report delivered upstream):
> 1. Recursive copying of rawfile/qml (a 7.8 GB HAP explosion + the tool hangs)
> 2. It doesn't deploy `libqohos.so` (the QPA plugin) → the app crashes at startup with `load libqohos.so failed`
> 3. It doesn't deploy the QML modules' `qmldir` files into `resfile/qml` → a white screen with `module not installed`
> 4. The QML plugin `.so` path is wrong (placed in `resfile/qml`, MUSL-LDSO's namespace rejects it with `errno=22`; it belongs in `libs/`)
> 5. It doesn't deploy the QML plugins' Qt6 dependencies (111 libraries missing) → `Cannot load library Invalid argument`
>
> This document **never invokes `harmonydeployqt6`**: it generates the DevEco project from the SDK templates by hand and deploys every runtime resource, avoiding all 5 bugs.

---

## Prerequisites

| Item | Requirement |
|------|-------------|
| The Qt 6.12.0 Beta2 prebuilt SDK | `${QT6_INSTALL_ROOT}` (the prebuilt installation root), containing `harmonyos_arm64_v8a/` (the cross target) + `mingw_64/` (the host) |
| Your business `.so` is already built | `qt-cmake.bat` configure + `cmake --build` producing `build/lib<TARGET>.so` (with bare NEEDED names + `main GLOBAL DEFAULT`; the prebuilt needs no patching) |
| DevEco Studio | A whitespace-free junction `${DEVECO_STUDIO}` = `C:/DevecoStudio`, containing the OHOS native SDK (API 23, Clang 15.0.4) + hvigor + node + jbr |
| A device | Developer mode + USB debugging (a real device or the emulator) |

> For building the business .so, see [[qt6-ohos-windows-cli-deploy]] §3-4 (qt-cmake configure + cmake --build).

---

## SDK resource inventory

| Resource | SDK path | Purpose |
|----------|----------|---------|
| The DevEco project template | `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a/src/harmonyos/templates/` | The skeleton: AppScope + build-profile + hvigor + oh-package + **the ets glue** (QAbility/QtUtils/OhosExportModules/QAbilityStage/QChildProcess/NativeNode pages) + qt/libqohos.d.ts + cpp/CMakeLists + ohosTest |
| `libqohos.so` (the QPA plugin) | `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a/plugins/platforms/libqohos.so` | The Qt OHOS platform plugin (4.3 MB) |
| The Qt6 libraries (150 `.so` files) | `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a/lib/` | libQt6Core/Gui/Quick/Qml/CanvasPainter/Canvas2D/Charts/Quick3D/QuickControls2 and more |
| The QML modules | `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a/qml/` | QtQuick/QtCanvas2D/QtQuick.Controls and 20+ other modules (with `qmldir` + `.qmltypes` + plugin `.so` files) |
| `llvm-readelf` | `${DEVECO_STUDIO}/sdk/default/openharmony/native/llvm/bin/llvm-readelf.exe` | Scanning `.so` NEEDED entries |

---

## Steps

> Below, `$HAP` = the project output directory (e.g. `build/hap`), `$TARGET` = your business target name (e.g. `qcpainterbench`), and `$SDK` = `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a`.

### §1 Copy the DevEco project skeleton from the SDK templates (avoiding Bug 1)

```bash
SDK=${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a
HAP=build/hap
rm -rf "$HAP"
cp -r "$SDK/src/harmonyos/templates/." "$HAP/"
# templates contains cmake_install.cmake/CTestTestfile.cmake (cmake artifacts — delete them)
rm -f "$HAP/cmake_install.cmake" "$HAP/CTestTestfile.cmake"
```

The skeleton structure (after copying):
```
$HAP/
├── AppScope/app.json5 + resources/
├── build-profile.json5
├── hvigor/hvigor-config.json5
├── hvigorfile.ts
├── oh-package.json5
└── entry/
    ├── build-profile.json5 + hvigorfile.ts + oh-package.json5
    └── src/main/
        ├── cpp/CMakeLists.txt + hello.cpp + types/libentry/   ← replaced in §2 with your business .so configuration
        ├── ets/ (common/QtAppConstants + pages/* + process/QChildProcess
        │        + qability/QAbility/QtUtils/OhosExportModules/QEmbeddedComponentCreator
        │        + qabilitystage/QAbilityStage)
        ├── module.json5
        ├── qt/libqohos.d.ts + oh-package.json5                ← libqohos.so added in §4
        └── resources/ + ohosTest/
```

> The ets glue (QAbility/QtUtils/OhosExportModules and so on) comes with the templates — nothing to write by hand.

### §2 Configure APP_LIBRARY_NAME and remove the cpp template

```bash
TARGET=qcpainterbench  # change to your target
# Set the business .so name in QtAppConstants.ets
sed -i "s/export const APP_LIBRARY_NAME = .*/export const APP_LIBRARY_NAME = 'lib${TARGET}.so';/" \
  "$HAP/entry/src/main/ets/common/QtAppConstants.ets"
# Remove the cpp template (hello.cpp + CMakeLists); the business .so is deployed into libs/ in §3, so no entry cpp build is needed
rm -rf "$HAP/entry/src/main/cpp"
# entry/build-profile.json5's externalNativeOptions.path points at cpp/CMakeLists.txt; after deleting cpp, change or remove that field
```

> If you keep cpp/CMakeLists (so hvigor builds your source), point it at your sources instead; this document assumes the business .so was deployed in §3 (no hvigor build).

### §3 Deploy the business .so + the Qt6 runtime into entry/libs/arm64-v8a/

```bash
SDK=${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a
READELF=C:/DevecoStudio/sdk/default/openharmony/native/llvm/bin/llvm-readelf.exe
LIBS=$HAP/entry/libs/arm64-v8a
mkdir -p "$LIBS"

# The business .so
cp build/lib${TARGET}.so "$LIBS/"

# The business .so's direct Qt6 dependencies (scanned from NEEDED)
for lib in $("$READELF" -d "build/lib${TARGET}.so" | grep NEEDED | sed 's/.*\[\(.*\)\]/\1/'); do
  [[ "$lib" == libQt6* ]] && cp "$SDK/lib/$lib" "$LIBS/" 2>/dev/null
done

# Qt6's non-Qt runtime dependencies (icu/fontconfig/freetype/png/jpeg/brotli/expat/uuid/c++_shared)
for lib in libicudata libicui18n libicuuc libfontconfig libfreetype libpng16 libjpeg \
            libturbojpeg libbrotlicommon libbrotlidec libbrotlienc libexpat libc++_shared; do
  cp "$SDK/lib/$lib.so" "$LIBS/" 2>/dev/null
done
# uuid may be a .a (static), so copy it only if present
cp "$SDK/lib/libuuid.so" "$LIBS/" 2>/dev/null
```

### §4 Deploy libqohos.so (the QPA plugin, avoiding Bug 2)

```bash
# The qt/ module directory (.d.ts + oh-package.json5 were copied from templates; add the .so binary)
cp "$SDK/plugins/platforms/libqohos.so" "$HAP/entry/src/main/qt/libqohos.so"
# Put a copy in libs/ too (the runtime dlopen path that QAbility.ets's `import qpa from 'libqohos.so'` resolves)
cp "$SDK/plugins/platforms/libqohos.so" "$LIBS/libqohos.so"
```

### §5 Deploy the QML modules' qmldir + .qmltypes into resfile/qml/ (avoiding Bug 3)

```bash
RESFILE=$HAP/entry/src/main/resources/resfile/qml
mkdir -p "$RESFILE"
# Copy the whole SDK qml/ (including qmldir + .qmltypes + .so; §6 moves the .so files out)
cp -r "$SDK/qml/." "$RESFILE/"
```

### §6 Move the QML plugin .so files into libs/, leaving only qmldir + .qmltypes in resfile (avoiding Bug 4)

```bash
# Move the QML plugin .so files from resfile/qml/<Module>/ into libs/ (HarmonyOS MUSL-LDSO only allows dlopen from libs/)
find "$RESFILE" -name "*.so" -exec cp {} "$LIBS/" \;
# Leave only qmldir + .qmltypes + .qml in resfile (delete the .so files)
find "$RESFILE" -name "*.so" -delete
```

> `qmldir` uses `optional plugin <name>` (a plugin name, not a path), and Qt finds `lib<name>.so` via `LD_LIBRARY_PATH` (which includes `libs/arm64-v8a/`).

### §7 Deploy the QML plugins' Qt6 dependencies (fill the gaps by scanning NEEDED, avoiding Bug 5)

```bash
# Scan the NEEDED entries of every .so in libs/ (business + libqohos + QML plugins) and fill in any missing Qt6 libraries
for so in "$LIBS"/*.so; do
  "$READELF" -d "$so" 2>/dev/null | grep NEEDED | sed 's/.*\[\(.*\)\]/\1/'
done | sort -u | while read lib; do
  if [[ "$lib" == libQt6* ]] && [ ! -f "$LIBS/$lib" ]; then
    echo "Adding: $lib"
    cp "$SDK/lib/$lib" "$LIBS/" 2>/dev/null
  fi
done
```

> In practice, qcpainterbench needed 111 additional Qt6 libraries (libQt6Canvas2D/Charts/Quick3D*/QuickControls2* and others). Copying the whole SDK lib/ also works (150 `.so` files, skipping the scan):
> `cp "$SDK/lib/"libQt6*.so "$LIBS/"` (though that includes unused modules and makes the HAP larger).

### §8 Configure build-profile + app.json5 + module.json5

- **`AppScope/app.json5`**: `bundleName` (e.g. `org.qtproject.example.<TARGET>`) + `versionCode`/`versionName`
- **`entry/src/main/module.json5`**: permissions as needed (e.g. `ohos.permission.INTERNET`)
- **The root `build-profile.json5` signingConfigs**: DevEco auto-signing (filled in at step 2 of §9)

### §9 Open in DevEco + sign + build the HAP + install + start

1. DevEco Studio → Open → select `$HAP/`
2. File > Project Structure (Ctrl+Alt+Shift+S) > Signing Configs > tick "Automatically generate signature" > Apply (DevEco fills in `signingConfigs` and generates a debug certificate)
3. Run ▶ (DevEco runs `hvigor assembleHap` to build a signed HAP, then installs and starts it)
   - Or build from the CLI: `hvigorw assembleHap` (for the environment variables, see [[qt6-ohos-windows-cli-deploy]] §2.2)
   - Or install/start from the CLI: `hdc file send <signed.hap> /data/local/tmp/app.hap && hdc shell bm install -r -p /data/local/tmp/app.hap && hdc shell aa start -b <bundleName> -a QAbility`

---

## Verification

### Static (after deployment, before the build)

```bash
READELF=C:/DevecoStudio/sdk/default/openharmony/native/llvm/bin/llvm-readelf.exe
LIBS=$HAP/entry/libs/arm64-v8a
# The business .so's NEEDED entries are bare names (no C:/ absolute paths)
"$READELF" -d "$LIBS/lib${TARGET}.so" | grep NEEDED
# main GLOBAL DEFAULT
"$READELF" --dyn-syms "$LIBS/lib${TARGET}.so" | grep -E " main$"
# The number of .so files in libs/ (business + libqohos + the Qt6 runtime + QML plugins + Qt6 dependencies; usually 200+)
ls "$LIBS"/*.so | wc -l
# No .so files in resfile/qml (only qmldir + .qmltypes)
find "$HAP/entry/src/main/resources/resfile/qml" -name "*.so" | wc -l  # should be 0
# qt/ contains libqohos.so
ls "$HAP/entry/src/main/qt/libqohos.so"
```

### Runtime (on the device)

- The process stays alive (`hilog` shows no `load libqohos.so failed` / `module ... not installed` / `MUSL-LDSO ... check ns accessible` / `Cannot load library`)
- Qt renders (hilog shows `RSNode::AddChild` + `SurfaceNode`)
- The screenshot isn't a white screen

---

## How the 5 bugs are avoided

| Bug | What harmonydeployqt6 does | How this document avoids it |
|-----|----------------------------|------------------------------|
| 1 rawfile recursion | `qml-root-path` includes the project root and `build/` without excluding them → a 7.8 GB HAP | §1 copies the skeleton from the SDK templates (**never invoking harmonydeployqt6**, so there's no qml-root-path copy) |
| 2 libqohos.so not deployed | `qt/` has only the `.d.ts` plus a broken symlink | §4 copies `libqohos.so` into `qt/` + `libs/` manually |
| 3 QML module qmldir not deployed | `resfile/qml` is empty | §5 copies the SDK's `qml/` into `resfile/qml/` |
| 4 Wrong QML plugin .so path | `resfile` is rejected by MUSL-LDSO | §6 moves the QML plugin .so files into `libs/`, leaving only `qmldir` + `.qmltypes` in `resfile` |
| 5 QML plugins' Qt6 dependencies not deployed | Only the business target's direct dependencies are deployed | §7 scans every .so's NEEDED entries and fills in the missing Qt6 libraries |

---

## Comparison with harmonydeployqt6

| Dimension | harmonydeployqt6 | This document (manual) |
|-----------|------------------|------------------------|
| Project skeleton | Copied from the SDK templates ✅ | Copied from the SDK templates ✅ (§1) |
| Business .so direct dependencies | Deployed ✅ | Deployed ✅ (§3) |
| libqohos.so | ❌ Not deployed (Bug 2) | ✅ Deployed (§4) |
| resfile/qml qmldir | ❌ Not deployed (Bug 3) | ✅ Deployed (§5) |
| QML plugin .so path | ❌ resfile (Bug 4) | ✅ libs/ (§6) |
| QML plugins' Qt6 dependencies | ❌ Not deployed (Bug 5) | ✅ Filled in by scanning (§7) |
| rawfile recursion | ❌ Bug 1 | ✅ None (harmonydeployqt6 isn't invoked) |
| HAP size | 7.8 GB (Bug 1), or 89 MB after cleanup but missing QML | ~190 MB (including the full Qt6 + QML runtime — normal) |

---

## Notes

- This document assumes the business .so is already built (`qt-cmake` + `cmake --build`; see [[qt6-ohos-windows-cli-deploy]] §3-4). The prebuilt SDK means no `patch_needed.py` (the NEEDED entries are already bare names) and no manual `visibility("default")` (`qt_add_executable` makes `main GLOBAL DEFAULT` automatically).
- QML is already AOT-compiled into the `.so`'s qrc (`qmlcache_loader.cpp`); the `.qml` files in `resfile/qml` exist only as a non-AOT fallback, and at runtime everything loads from the qrc.
- If the application doesn't use QML (pure Widgets), §5-7 can be skipped (just §1-4 + §8-9).
- The workarounds for the 5 bugs in this document were verified end to end with `qcpainterbench` (a Qt 6.12 QML application): the application launches, QML loads, Qt renders (hilog `RSNode`/`SurfaceNode`), and the screenshot is 456 KB (vs. 153 KB for a white screen).

---

## Related

- [[qt6-ohos-windows-cli-deploy]] — Qt 6.12 CLI deployment (including the harmonydeployqt6 flow + the 5-bug pitfall table in §8)
- [[qt-harmonyos-qt6-status]] — Qt6 HarmonyOS porting status (the prebuilt strategy B′)
- [[qt-harmonyos-project-structure]] — Project structure / key CMake configuration / .so deployment
- The harmonydeployqt6 5-bug defect report delivered upstream (ISSUE.md)

## Content sources

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | The 2026-08-06 end-to-end qcpainterbench HarmonyOS port (working around harmonydeployqt6's 5 bugs, with manual deployment and successful rendering) |
| 🔍 Tool testing | The SDK templates structure + the libqohos.so/qml/lib paths + llvm-readelf NEEDED scanning + MUSL-LDSO's namespace rejecting dlopen from resfile |
| 📖 Qt documentation | The harmonydeployqt6 5-bug defect report (delivered upstream) |
