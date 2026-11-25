---
id: procedural-qt6-ohos-windows-cli-deploy
type: procedural
domain: deploy
tags: [qt6, qt6.12, harmonyos, ohos, cmake, hvigor, harmonydeployqt, hap, windows, cli, installer, beta2]
created: 2026-08-01
updated: 2026-08-01
status: active
audience: public
refs: [semantic-qt-harmonyos-qt6-status, semantic-qt-harmonyos-build, semantic-qt-harmonyos-build-run-workflow, semantic-qt-harmonyos-project-structure]
summary: >
  Building a Qt project end to end from the Windows command line with a prebuilt-installer Qt 6.12.0 Beta2 and generating a HarmonyOS DevEco project:
  the official wiki CLI workflow (qt-cmake → cmake --build → harmonydeployqt6 → sign in DevEco and install on the device)
  + this machine's actual paths (${QT6_INSTALL_ROOT}, the ${DEVECO_STUDIO} junction, API 23 native) +
  what the prebuilt build saves you from patching (NEEDED entries are already bare names, qt_add_executable makes main GLOBAL DEFAULT automatically). Fills in what the wiki doesn't cover:
  QT_CHAINLOAD_TOOLCHAIN_FILE being mandatory, the DevEco whitespace pitfall, the one-shot _make_hap target, and the six signing artifacts.
---

# Qt 6.12.0 Beta2 prebuilt + the Windows CLI: from building a Qt project to generating a HarmonyOS DevEco project

> Based on the Windows section of the official wiki page [Qt for HarmonyOS development with 6.12.0 Beta2](https://wiki.qt.io/Qt_for_HarmonyOS_development_with_6.12.0_Beta2#Windows),
> with this machine's actual paths substituted and KB-tested pitfalls injected. This is the **CLI command-line workflow** (not the Qt Creator IDE).
>
> **The three workflow forms** (this page is one of them):
> - **Prebuilt + the CLI** (this page) — the simplest path, good for scripting/CI.
> - **Prebuilt + the Qt Creator IDE** — graphical development with a configured kit.
> - **A source superbuild** — building Qt 6.12 yourself (needs extra patches); only use it when the prebuilt is missing a module you need.
>
> The verification baseline: this machine's `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a` (150 libQt6*.so files, 37 top-level repositories, 27 QML modules, 24 plugin categories; only WebEngine/DBus/Wayland/Pdf are missing).

---

## 0. Prerequisites and applicability

| Item | Requirement | State on this machine |
|------|-------------|-----------------------|
| The Qt 6.12.0 Beta2 prebuilt | In the Qt online installer, tick `Qt 6.12.0 → HarmonyOS arm64_v8a` + `MinGW 64-bit` (host) + `CMake + Ninja` (Tools) | ✅ `${QT6_INSTALL_ROOT}` |
| DevEco Studio | Installed at a path **without whitespace** (the wiki warns that whitespace makes hvigor's spawn fail) | ⚠️ Actually installed at `C:\Program Files\Huawei\DevEco Studio` (with spaces); use a junction — see §1.1 |
| The OHOS native SDK | Ships with DevEco; API 23 (HarmonyOS 6.1.0), Clang 15.0.4 | ✅ Under the DevEco directory |
| additional-packages | **Not required for the prebuilt workflow** (the prebuilt ships fontconfig/freetype and so on; only a source superbuild needs them) | Not installed here, and configure succeeds even without `CMAKE_FIND_ROOT_PATH` |
| The target example | The installer's own `${QT6_INSTALLER_ROOT}/Examples/Qt-6.12.0/widgets/gallery` | ✅ |

> **The key difference**: the prebuilt workflow **doesn't need** the two runtime patches a source superbuild requires —
> ① The `DT_NEEDED` entries in the Qt6 `.so` files are already bare names (libicui18n/libz/libc++_shared and so on, with no Windows absolute path prefix);
> ② `qt_add_executable` automatically makes it a `MODULE .so` with `CXX_VISIBILITY_PRESET=default` (so `main` is automatically `GLOBAL DEFAULT`, with no manual `__attribute__((visibility("default")))` needed).
> (Both patch problems only occur with a source superbuild and don't apply to the prebuilt.)

---

## 1. The environment inventory (this machine's actual paths)

### 1.1 A whitespace-free DevEco path (do this once)

Per the wiki and verified on this machine on 2026-07-23: a DevEco path containing whitespace makes hvigor's node workers fail to spawn `java`/`hvigorw`. It's installed with spaces here, so create a whitespace-free alias with a junction (no reinstall):

```cmd
:: Run cmd as administrator
mklink /J C:\DevecoStudio "C:\Program Files\Huawei\DevEco Studio"
```

> From then on, all Qt 6.12 workflow paths use `${DEVECO_STUDIO}` (with forward slashes, which CMake prefers). **Don't use** `C:/Program Files/...`.
> If you already created this junction on 2026-07-23, skip this step.

### 1.2 Path inventory

| Item | Path | Purpose |
|------|------|---------|
| The Qt 6.12 installation root | `${QT6_INSTALL_ROOT}` | Installed by the installer |
| The Qt6 harmonyos target | `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a` | `CMAKE_PREFIX_PATH` (set automatically by qt-cmake) |
| The Qt6 host build | `${QT6_INSTALL_ROOT}/mingw_64` | `QT_HOST_PATH`; **harmonydeployqt6.exe lives here** |
| qt-cmake.bat | `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a/bin/qt-cmake.bat` | Line 10 sets `CMAKE_TOOLCHAIN_FILE` automatically |
| qt.toolchain.cmake | `${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a/lib/cmake/Qt6/qt.toolchain.cmake` | The Qt-side toolchain |
| The DevEco root (whitespace-free) | `${DEVECO_STUDIO}` | `DEVECO_SDK_HOME` |
| The OHOS native SDK | `${DEVECO_STUDIO}/sdk/default/openharmony/native` | `OHOS_SDK_NATIVE`, containing `llvm/`, `sysroot/`, and `build/cmake/ohos.toolchain.cmake` |
| ohos.toolchain.cmake | `${DEVECO_STUDIO}/sdk/default/openharmony/native/build/cmake/ohos.toolchain.cmake` | `QT_CHAINLOAD_TOOLCHAIN_FILE` (**mandatory**) |
| hvigorw.bat | `${DEVECO_STUDIO}/tools/hvigor/bin/hvigorw.bat` | HAP packaging (`--hvigor` / `QT_HARMONYOS_HVIGOR`) |
| node | `${DEVECO_STUDIO}/tools/node` | `NODE_HOME` |
| java (jbr) | `${DEVECO_STUDIO}/jbr/bin` | `JAVA_HOME` |
| **harmonydeployqt6.exe** | `${QT6_INSTALL_ROOT}/mingw_64/bin/harmonydeployqt6.exe` | A host tool — **not in the harmonyos target's `harmonyos_arm64_v8a/bin/`** |

> ⚠️ The `DEVECO_PATH`/`OHOS_SDK_NATIVE` in `ENV.local.md` are the Qt5 workflow's values (with spaces); the Qt 6.12 workflow uses the **separate whitespace-free** `${DEVECO_STUDIO}` — don't mix them.

---

## 2. Environment variables

> **Settle two things on the host side first** (measured on 2026-11-16 on Windows 10.0.26300 + the Qt 6.12.0 prebuilt kit):
> First, **the generator** — in a restricted session (a CI sandbox, a non-interactive service account), `-G Ninja` spins
> at 0 CPU and never returns; switching to `-G "MinGW Makefiles"` (the kit ships `mingw_64/bin/mingw32-make.exe`) works fine.
> Second, **whether the bundled scripts are real** — the kit's `qmake.bat` is often a build-machine artifact (its content points to
> `/home/qt/work/install/bin\qmake6.exe`) and is unusable on Windows; judge whether the kit is usable by
> `qt-cmake.bat`, `bin/moc.exe`, and `harmonydeployqt6.exe`.
> Also, PowerShell's `>` redirection outputs UTF-16LE with a BOM by default; before handing a log to `analyze-log`, pipe it through
> `| Out-File -Encoding utf8`, or no QOH pattern will match.

### 2.1 Build time (for qt-cmake + cmake --build)

```cmd
SET HARMONY_OS_API_VER=23
SET OHOS_SDK_ROOT=%USERPROFILE%/AppData/Local/OpenHarmony/Sdk
SET NATIVE_OHOS_SDK=${DEVECO_STUDIO}/sdk/default/openharmony/native
SET ARCH=arm64-v8a
:: In the prebuilt workflow, OHOS_ADDITIONAL_PACKAGES can be left unset; set it only if you installed additional-packages:
:: SET OHOS_ADDITIONAL_PACKAGES=C:/Dev/ohos-additional-packages
SET PATH=%NATIVE_OHOS_SDK%\build-tools\cmake\bin;%PATH%
```

> The wiki uses a separately downloaded SDK at `%USERPROFILE%/AppData/Local/OpenHarmony/Sdk/23`. Here we use the native SDK DevEco ships (`${DEVECO_STUDIO}/.../native`, API 23) — equivalent and with nothing extra to download. `OHOS_SDK_ROOT` is just a placeholder; `NATIVE_OHOS_SDK` is what's actually used.

### 2.2 Deployment time (for harmonydeployqt6; node/jbr ship with DevEco)

```cmd
SET NODE_HOME=${DEVECO_STUDIO}/tools/node
SET JAVA_HOME=${DEVECO_STUDIO}/jbr/bin
SET DEVECO_SDK_HOME=${DEVECO_STUDIO}
SET QT_HARMONYOS_HVIGOR=${DEVECO_STUDIO}/tools/hvigor/bin/hvigorw.bat
SET PATH=%PATH%;%NODE_HOME%;%JAVA_HOME%;${DEVECO_STUDIO}/tools/hvigor/bin;${DEVECO_STUDIO}/tools/ohpm/bin
```

> With `QT_HARMONYOS_HVIGOR` set, harmonydeployqt6 finds hvigorw even without `--hvigor`.

---

## 3. Configure (qt-cmake configure)

Change into the example directory and configure with `qt-cmake.bat` (which automatically sets `CMAKE_TOOLCHAIN_FILE` to `qt.toolchain.cmake`):

```cmd
cd ${QT6_INSTALLER_ROOT}\Examples\Qt-6.12.0\widgets\gallery

${QT6_INSTALL_ROOT}\harmonyos_arm64_v8a\bin\qt-cmake.bat -B build -S . -G Ninja ^
  -DCMAKE_TOOLCHAIN_FILE="${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a/lib/cmake/Qt6/qt.toolchain.cmake" ^
  -DQT_HOST_PATH="${QT6_INSTALL_ROOT}/mingw_64" ^
  -DQT_CHAINLOAD_TOOLCHAIN_FILE="%NATIVE_OHOS_SDK%/build/cmake/ohos.toolchain.cmake" ^
  -DOHOS_ARCH=%ARCH% ^
  -DOHOS_SDK_NATIVE="%NATIVE_OHOS_SDK%" ^
  -DCMAKE_FIND_ROOT_PATH="%OHOS_ADDITIONAL_PACKAGES%"
```

> The last line's `-DCMAKE_FIND_ROOT_PATH` **can be omitted** in the prebuilt workflow (without additional-packages installed, `ohos.toolchain.cmake` sets the sysroot itself). Omitting it still gives `Configuring done` in practice.

### 3.1 What the CMake variables do

| Variable | Purpose | If you omit it |
|----------|---------|----------------|
| `CMAKE_TOOLCHAIN_FILE` | The Qt-side toolchain (qt-cmake.bat line 10 would set it anyway; passing it explicitly is fine) | qt-cmake fills it in |
| `QT_HOST_PATH` | The host Qt (mingw_64), providing moc/rcc/uic/qsb/harmonydeployqt6 | **Mandatory**; without it the host tools aren't found |
| `QT_CHAINLOAD_TOOLCHAIN_FILE` | The OHOS native toolchain (ohos.toolchain.cmake) | **Mandatory!** Without it, `qt.toolchain.cmake` line 135 falls back to the Linux default path baked in when Qt was built, `/opt/harmonyos/.../ohos.toolchain.cmake` (which doesn't exist) → the OHOS toolchain isn't loaded → clang links Windows libraries as if on the host → `Check for working CXX compiler - broken` |
| `OHOS_ARCH` | The target architecture `arm64-v8a` (the only one) | The default may be wrong |
| `OHOS_SDK_NATIVE` | The native SDK path, which must come from the same source as the toolchain | The sysroot isn't found |
| `CMAKE_FIND_ROOT_PATH` | The additional-packages root | Can be omitted for the prebuilt |

### 3.2 Success markers

```
-- Configuring done
-- Generating done
-- Build files written to .../build
```

It should identify `Clang 15.0.4` and find `EGL`/`GLESv3`/`sysroot`. A clean configure on this machine gives `Configuring done (9.4s)`.

---

## 4. Build (cmake --build)

```cmd
cmake --build build --parallel
```

**The artifact**: `build/libgallery.so` (the business library; `qt_add_executable` makes it a `MODULE` with `main GLOBAL DEFAULT` automatically).

> Linking against the Qt6 libraries is slow (for gallery, linking took several minutes after the 51/52 objects compiled — not a configuration problem). If it times out, re-run `cmake --build build` to continue incrementally.

### 4.1 The prebuilt workflow needs no patching (the key difference from a source superbuild)

The prebuilt `libQt6Core.so`'s `DT_NEEDED` entries are already bare names (`libicui18n`/`libicuuc`/`libicudata`/`libz`/`libc++_shared`/`libc`), so a business `.so` linked against the Qt libraries also gets bare names → `dlopen` succeeds on the device, and **no `patch_needed.py` is needed**.
The business `main` is made `GLOBAL DEFAULT` automatically by `qt_add_executable` → `dlsym("main")` succeeds, so **no manual `__attribute__((visibility("default")))` is needed**.

Verification (optional):

```cmd
:: The NEEDED entries should have no C:/ absolute paths
${DEVECO_STUDIO}/sdk/default/openharmony/native/llvm/bin/llvm-readelf -d build\libgallery.so | findstr "NEEDED"
:: main should be GLOBAL DEFAULT
${DEVECO_STUDIO}/sdk/default/openharmony/native/llvm/bin/llvm-readelf --dyn-syms build\libgallery.so | findstr " main"
```

> Only if your CMake uses a bare `add_executable` (rather than `qt_add_executable`) do you need to add `visibility("default")` to `main` by hand.

---

## 5. Generate the DevEco project (harmonydeployqt6)

Once configure + build have produced `libgallery.so`, call `harmonydeployqt6` to generate the DevEco/hvigor project:

```cmd
${QT6_INSTALL_ROOT}\mingw_64\bin\harmonydeployqt6.exe ^
  --input build/gallery-harmony-deployment-settings.json ^
  --output build/hap ^
  --hvigor ${DEVECO_STUDIO}/tools/hvigor/bin/hvigorw.bat ^
  --verbose
```

> `<target>-harmony-deployment-settings.json` is generated automatically by `qt_add_executable` at configure time (change the target name for a different project, e.g. `gallery-harmony-deployment-settings.json`).

### 5.1 The authoritative harmonydeployqt6 options (from `--help`)

| Option | Purpose |
|--------|---------|
| `--input <file>` | The JSON configuration (**mandatory**), i.e. `<target>-harmony-deployment-settings.json` |
| `--output <dir>` | The output directory for the generated DevEco/hvigor project |
| `--hvigor <path>` | The path to hvigorw.bat (or the env var `QT_HARMONYOS_HVIGOR`); it **must be absolute**, or you get `Failed to start hvigorw` |
| `--no-build` | Skip hvigor's HAP packaging (generate the project only; useful as a verification command) |
| `--install` | Install to a connected device (via hdc; requires a connected device and signing) |
| `--release` | The release configuration (debug is the default) |
| `--verbose` | Verbose output |
| `--signing-* ×6` | Command-line signing (see §7) |

### 5.2 Success markers

A complete DevEco project is generated under `build/hap/`:

```
build/hap/
├── AppScope/              app.json5 + resources
├── entry/                 the module (with the ets glue and libs/arm64-v8a/ containing the business .so + the Qt runtime .so files)
├── hvigor/                the build scripts
├── oh-package.json5
└── build-profile.json5
```

In `--no-build` verification mode on this machine: exit 0, 3.9 s, with the plugin dependency check passing.

---

## 6. Open in DevEco / sign / install on a device

1. **Open**: DevEco Studio → Open → select the `build/hap/` directory.
2. **Sign**: DevEco → File → Project Structure → Signing Configs → tick `Automatically generate signature` (DevEco generates a debug certificate automatically). Without the `--signing-*` options, the HAP is left unsigned, so use this officially recommended flow.
3. **Build/install**: click Run in DevEco → it builds the HAP → and installs it on a device/emulator via hdc.

> You can also install an unsigned HAP from the command line and push it with hdc (bringing your own signature), but signing and installing through DevEco is the official recommendation.

---

## 7. Optional: the one-shot `<target>_make_hap` target (officially recommended)

With §2.2's environment variables set (especially `QT_HARMONYOS_HVIGOR`), you can skip the manual harmonydeployqt6 call in §5 and just run:

```cmd
cmake --build build --target gallery_make_hap
```

This is equivalent to "build `libgallery.so` first, then call harmonydeployqt6 to package the HAP" in one step. The official documentation, [harmonyos-building-deploying-apps](https://doc.qt.io/qt-6.12/harmonyos-building-deploying-apps.html), recommends this approach.

### 7.1 Command-line signing (optional, instead of DevEco's)

All six artifacts must be supplied together, or the HAP is left unsigned:

```cmd
harmonydeployqt6 --input ... --output ... --hvigor ... ^
  --signing-cert-path <.cer> ^
  --signing-profile <.p7b> ^
  --signing-store-file <.p12> ^
  --signing-key-alias <alias> ^
  --signing-key-password <encrypted> ^
  --signing-store-password <encrypted>
```

> The passwords must be **hvigor-encrypted strings** (not plaintext), generated by DevEco.

---

## 8. Pitfall quick reference (verified on this machine)

| Symptom | Root cause | Fix |
|---------|------------|-----|
| `Check for working CXX compiler - broken` / `program not executable` | Missing `QT_CHAINLOAD_TOOLCHAIN_FILE` → the Linux default path is used → clang links Windows libraries as if on the host | `-DQT_CHAINLOAD_TOOLCHAIN_FILE` is mandatory and must point at the real `ohos.toolchain.cmake` |
| `Could not find toolchain file` (though the file exists) | (In the Qt Creator case) the initial configuration value has leading/trailing `"` + `:UNINITIALIZED` → cmake receives a path with literal quotes | With quotes on the CLI, cmake parses it correctly; this pitfall only exists in Qt Creator's kit configuration table |
| Can't find `harmonydeployqt6.exe` (looking in `harmonyos_arm64_v8a/bin`) | It's a host tool and isn't in the cross target | Use `mingw_64/bin/harmonydeployqt6.exe` |
| `Failed to start hvigorw` | A relative path was passed to `--hvigor` | `--hvigor` must be absolute, or set the `QT_HARMONYOS_HVIGOR` env var |
| `Warning: No hvigor path specified, skipping build` (**exit code 0**) | `QT_HARMONYOS_HVIGOR` is missing, so packaging is silently skipped | Set an absolute path; scripts that judge success by exit code must also match this line |
| `EPERM ... symlink ... node_modules\@ohos\hvigor` | A non-administrator can't create symlinks; hvigor deletes and recreates them every time, so copying them in beforehand doesn't help | Pre-create the two junctions with `mklink /J`, or use an administrator session |
| `Invalid custom userhome hvigor data dir` | `HVIGOR_USER_HOME` was given a relative path and silently fell back | Pass an absolute, writable path |
| harmonydeployqt6 spawns `java` with ENOENT | hvigorw's node workers spawn `java` (to run app_packing_tool.jar) and lose the environment | Confirm `JAVA_HOME` + `jbr/bin` are on PATH; §2.2 covers this |
| Deployment says `libgallery.so` is missing | You only configured, never built | Run `cmake --build build` first |
| A DevEco path with spaces → assorted mysterious failures | The wiki already warns that whitespace makes hvigor's spawn fail | Use the whitespace-free junction alias `${DEVECO_STUDIO}` from §1.1 |
| On-device `dlopen failed: ...C:/...` with an absolute path | A source superbuild's developer build writes absolute NEEDED entries | **This doesn't happen with the prebuilt**; if it does, you're mistakenly using superbuild artifacts — switch to the prebuilt or run `patch_needed.py` |
| On-device `dlsym("main")` fails | The business `main` is a local symbol | Use `qt_add_executable` (which makes it GLOBAL DEFAULT automatically), or add `visibility("default")` by hand |

---

## 9. End-to-end verification checklist

| # | Step | Command | Expected |
|---|------|---------|----------|
| 1 | The junction | `mklink /J C:\DevecoStudio "C:\Program Files\Huawei\DevEco Studio"` | Skip if it already exists |
| 2 | Set the environment variables | §2.1 + §2.2 | — |
| 3 | configure | `qt-cmake.bat -B build -S . -G Ninja ...` (§3) | `Configuring done`, identifying Clang 15.0.4 |
| 4 | build | `cmake --build build --parallel` | `libgallery.so` is produced |
| 5 | NEEDED entries are bare names | `llvm-readelf -d build\libgallery.so \| findstr NEEDED` | No `C:/` absolute paths |
| 6 | main is visible | `llvm-readelf --dyn-syms build\libgallery.so \| findstr " main"` | `GLOBAL DEFAULT` |
| 7 | Generate the DevEco project | `harmonydeployqt6 --input ... --output build/hap --hvigor ... --verbose` | `build/hap/` contains `AppScope/ entry/ hvigor/` |
| 8 | Open in DevEco, sign, install | DevEco → Open `build/hap/` → auto-sign → Run | gallery runs on the device |

---

## 10. The sequence at a glance

```cmd
:: 1. The junction (one time)
mklink /J C:\DevecoStudio "C:\Program Files\Huawei\DevEco Studio"

:: 2. Environment variables (reset them in each cmd window)
SET NATIVE_OHOS_SDK=${DEVECO_STUDIO}/sdk/default/openharmony/native
SET ARCH=arm64-v8a
SET NODE_HOME=${DEVECO_STUDIO}/tools/node
SET JAVA_HOME=${DEVECO_STUDIO}/jbr/bin
SET DEVECO_SDK_HOME=${DEVECO_STUDIO}
SET QT_HARMONYOS_HVIGOR=${DEVECO_STUDIO}/tools/hvigor/bin/hvigorw.bat
SET PATH=%NATIVE_OHOS_SDK%\build-tools\cmake\bin;%PATH%;%NODE_HOME%;%JAVA_HOME%;${DEVECO_STUDIO}/tools/hvigor/bin;${DEVECO_STUDIO}/tools/ohpm/bin

:: 3. configure
cd ${QT6_INSTALLER_ROOT}\Examples\Qt-6.12.0\widgets\gallery
${QT6_INSTALL_ROOT}\harmonyos_arm64_v8a\bin\qt-cmake.bat -B build -S . -G Ninja ^
  -DCMAKE_TOOLCHAIN_FILE="${QT6_INSTALL_ROOT}/harmonyos_arm64_v8a/lib/cmake/Qt6/qt.toolchain.cmake" ^
  -DQT_HOST_PATH="${QT6_INSTALL_ROOT}/mingw_64" ^
  -DQT_CHAINLOAD_TOOLCHAIN_FILE="%NATIVE_OHOS_SDK%/build/cmake/ohos.toolchain.cmake" ^
  -DOHOS_ARCH=%ARCH% -DOHOS_SDK_NATIVE="%NATIVE_OHOS_SDK%"

:: 4. build
cmake --build build --parallel

:: 5. Generate the DevEco project (or use the one-shot gallery_make_hap from §7)
cmake --build build --target gallery_make_hap

:: 6. Open build/hap/ in DevEco → auto-sign → Run
```

---

## 11. Related context

- [[qt-harmonyos-qt6-status]] — Qt6 HarmonyOS porting status (the prebuilt strategy B′, the module inventory, and the Qt5→Qt6 differences)
- [[qt-harmonyos-build]] — The Qt OHOS build environment and toolchain
- [[qt-harmonyos-build-run-workflow]] — DevEco MCP building/launching/logs/UI testing
- [[qt-harmonyos-project-structure]] — Project structure / key CMake configuration / .so deployment
- 📖 [Qt for HarmonyOS development with 6.12.0 Beta2](https://wiki.qt.io/Qt_for_HarmonyOS_development_with_6.12.0_Beta2#Windows) — The official wiki (the Windows section)
- 📖 [Building and Deploying Qt Applications for HarmonyOS](https://doc.qt.io/qt-6.12/harmonyos-building-deploying-apps.html) — The official documentation (the `_make_hap` target)

## Content sources

| Source | Notes |
|--------|-------|
| 📖 The Qt wiki | The official 6.12 Beta2 Windows section (CMake options, environment variables, the harmonydeployqt6 invocation) |
| 🛠️ Hands-on experience | The 2026-07-23 end-to-end verification on this machine (configure + harmonydeployqt6 `--no-build`); the 2026-08-01 inventory of the prebuilt SDK's modules (150 .so files / 37 repositories) |
| 🔍 Tool testing | Verified with `harmonydeployqt6 --help`, `qt-cmake.bat`, and `llvm-readelf -d/--dyn-syms` |
| 🔍 Framework source | Line 135 of `qt.toolchain.cmake`, which falls back to the Linux default path (when `QT_CHAINLOAD_TOOLCHAIN_FILE` is missing) |
