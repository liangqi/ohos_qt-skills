---
id: problem-runtime-harmonydeployqt-deploy-gaps
type: problem
domain: runtime
title: harmonydeployqt device-side deployment gaps (5 kinds of systematic problems)
tags: [runtime, harmonydeployqt, deployment, soname, fontconfig, libz, hap, bottle]
summary: "A chain of device-side dlopen failures in signed HAPs built by harmonydeployqt: the QPA plugin's non-Qt dependencies (the fontconfig chain) aren't deployed, bottles without a SONAME truncate dependency resolution, libz.so.1 is outside the application namespace, device system libraries are in non-standard paths, and bottles lack unversioned file names. Includes a readelf closure-check method and a 5-item checklist."
refs: [semantic-qt-harmonyos-third-party-libs, problem-runtime-hap-missing-so-closure]
keywords: [harmonydeployqt, deploy, dlopen, MUSL-LDSO, handleAbilityStageOnCreate, fontconfig, SONAME, DT_NEEDED, libz.so.1, chipset-sdk-sp, bottle, unversioned]
created: 2026-10-08
status: solved
severity: high
audience: public
updated: 2026-10-08
---

# harmonydeployqt device-side deployment gaps (5 kinds of systematic problems)

> Source: captured after hitting a chain of pitfalls in the deployment/install stage during a test of a "fully automated, zero-human-intervention HarmonyOS port"
> (which took about 1/4 of the total time). All of them are generic gaps at the deployer/toolchain layer, unrelated to any specific application.

## Symptoms

harmonydeployqt completes deployment normally and produces a signed HAP, but the application jscrashes right at startup on the device
(`Cannot read property handleAbilityStageOnCreate of undefined`) or hits MUSL-LDSO
`Error loading shared library`, and **every time you add one library, the next missing one pops up**.

## Root cause (5 kinds)

1. **The QPA plugin's non-Qt dependencies aren't deployed**: `copyPlatformPlugin` (harmonydeployqt
   main.cpp ~L2365) only handles dependencies with the `libQt6*` prefix, so the
   `libfontconfig.so.1` that libqohos.so needs, and its transitive closure (freetype/expat/libintl/png/bz2),
   are all skipped.
2. **A .so without a SONAME produces an absolute-path DT_NEEDED**: some
   .so files in Harmonybrew bottles have no SONAME → lld records the full build-machine path in the application .so → the deployer's
   `readElfDependencies` hits a line containing `:` (a drive letter) and simply breaks, **truncating the entire dependency
   list** (tested: Qt6Widgets/ffmpeg/openssl all went undeployed).
3. **libz.so.1 is treated as a system library**: the deployer's `isSystemLibrary` skips `libz.*`
   (an Android convention), but on HarmonyOS devices libz.so.1 is in `/system/usr/lib`,
   **outside the application's linker namespace**; the bottle builds of freetype/png/ffmpeg all need it.
4. **Device system libraries are in non-standard paths**: `libnative_*.so` is in chipset-sdk-sp/,
   `libpixelmap/libudmf` in ndk/, `libz.so` in platformsdk/; a closure check
   can't look only at /system/lib64.
5. **Bottles lack unversioned file names**: the Qt6 kit links against unversioned names (such as
   libbrotlicommon.so), while the bottle only has libbrotlicommon.so.1 →
   both levels of findExtraDepLibrary's lookup fail.

## Solution

1. Explicitly declare the fontconfig dependency on the application target (`--as-needed` drops libraries with no symbol references,
   so it must be wrapped):
   ```cmake
   target_link_libraries(<application target> PRIVATE
       "-Wl,--no-as-needed" "${FONTCONFIG_LIB}" "-Wl,--as-needed")
   ```
   so that `detectAndCopyDependencies` finds the whole fontconfig chain by scanning the application binary.
2. Bottle libraries without a SONAME: rebuild from source with `-Wl,-soname,libfoo.so.N`.
3. Inject libz.so.1 into entry/libs/arm64-v8a/ by hand, then re-run the incremental HAP build.
4. Materialize unversioned copies in the bottle directory (libfoo.so ← libfoo.so.1).
5. The three essentials for the hvigor environment: `DEVECO_SDK_HOME` + `JAVA_HOME` (DevEco's jbr) + a java path in PATH
   written with **backslashes** (node spawn fails to resolve a PATH in `C:/` form →
   `spawn java ENOENT`; see also build-fail-hvigor-spawn-java-enoent).
6. The deployment JSON's `extra-libs-dirs` comes from **CMAKE_FIND_ROOT_PATH** (not
   CMAKE_PREFIX_PATH); the Qt CMake finalizer doesn't propagate through the imported indirection layer, so you need to call
   `_qt_internal_harmonyos_executable_finalizer` manually.

## Verification

Tested on a large project: after the fixes, `aa start` → the process survives, the Qt render loop runs, the main window is visible,
and `qt-ohos-run verify` G0-G9 all PASS.

**Check method**: run a readelf NEEDED closure check on every .so in the deployment directory, with whitelist =
the deployed set ∪ the system libraries actually present on the device (verified path by path across chipset-sdk-sp/ndk/platformsdk).

## Checklist (run through it before deploying)

1. A local closure check before deploying (every NEEDED of all third-party libraries covered)
2. The QPA plugin's dependencies (the fontconfig chain) explicitly declared on the app binary
3. Every bottle .so has a SONAME
4. libz.so.1 injected by hand
5. hvigor environment: DEVECO_SDK_HOME + JAVA_HOME + a backslash PATH

## Related

- [runtime-hap-missing-so-closure](runtime-hap-missing-so-closure.md):
  the same family of problems: DT_NEEDED closure analysis when a HAP dies at startup (this page covers the systematic
  root causes and fixes on the deployer side; that page covers the troubleshooting method on the runtime side)
- [semantic/qt-harmonyos-third-party-libs](../semantic/qt-harmonyos-third-party-libs.md)
  §3.4: techniques for handling bottle gaps (mirror sources/static-to-shared conversion)
