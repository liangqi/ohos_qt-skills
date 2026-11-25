---
id: problem-runtime-hap-missing-so-closure
type: problem
domain: runtime
tags: [so-closure, libqohos, jscrash, TypeError, libdav1d, libaom, libbz2, aom-build, static-lib-to-so, portgraph, QT_HARMONYOS_EXTRA_LIBS, OpenSSL, libssl.so.3, HAP-dependencies]
created: 2026-09-11
updated: 2026-11-16
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-third-party-libs]
summary: >
  The HAP dies 64 ms after launch, no cppcrash, jscrash TypeError "handleAbilityStageOnCreate
  of undefined": the root cause is missing transitive .so dependencies of libqohos.so (libbz2/libz/libdav1d/
  libaom). Gives a recursive llvm-readobj closure troubleshooting method + building aom from source + turning static dav1d into a .so.
leader_summary: >
  Established the "dies at startup → check the .so closure" troubleshooting path, and ways to supply two kinds of dependencies that have no bottle
impact: [Runtime troubleshooting, Dependency management]
deliverables: [problem record]
evidence: []

error_message: >
  jscrash: TypeError: Cannot read property handleAbilityStageOnCreate of undefined
  at onCreate entry (entry/src/main/ets/qabilitystage/QAbilityStage.ets:41:9)
  appspawn: com.example.xxx exit with code:254
  hiview: OnFault: xxx Unsupported faultlog abily (no cppcrash)
error_code: ""
keywords: [so closure, NEEDED, jscrash, handleAbilityStageOnCreate, libqohos, fontconfig, freetype, dav1d, aom, bz2, HAP, startup crash, QT_HARMONYOS_EXTRA_LIBS, libssl.so.3, OpenSSL, imported SHARED, dependency closure broken]
symptoms: "The signed HAP installs successfully, but after aa start the process disappears in <100ms, with no cppcrash, only a jscrash TypeError; simple Qt applications built with the same kit work fine"

environment: "Windows build + Qt 6.12-beta3 kit + portgraph bottle dependencies + HUAWEI MateBook Pro device"
---

# The HAP dies at startup (jscrash TypeError) = the dependency .so closure is incomplete

## Error message

```
Reason: TypeError
Error message: Cannot read property handleAbilityStageOnCreate of undefined
Stacktrace: at onCreate entry (entry/src/main/ets/qabilitystage/QAbilityStage.ets:41:9)
appspawn: exit with code:254
```

No cppcrash; faultlogger reports "Unsupported faultlog". The process disappears about 64ms after
QAbilityStage::onCreate().

## Root-cause chain

`import qpa from 'libqohos.so'` returns **undefined** (the import doesn't throw: when the napi
module registration stage throws, ArkTS gets undefined, and the TypeError only appears on use).
libqohos.so is the platform glue; before its napi registration, .so loading expands transitively along DT_NEEDED,
and a missing .so at any link → the whole chain fails to load → qpa is undefined.

Missing in this case (the Qt 6.12 kit + bottle dependency combination):

```
libqohos.so → libfontconfig.so → libfreetype.so → libbz2.so.1.0   ✗
                                             └→ libz.so.1          ✗
libapp.so → libavcodec.so.63 → libdav1d.so.7                  ✗
             → libavif.so.16  → libaom.so.3 / libdav1d.so.7        ✗
             → libheif.so.1   → libaom.so.3                        ✗
             → libz.so                                                  ✗
```

Control group: another Qt application running fine on the same device happened to deploy these .so files.

## Troubleshooting method (recursive closure script)

1. `hdc shell ls /system/lib64 /system/lib64/platformsdk ...` to get the set of system .so files
   (NDK system libraries such as libhilog_ndk.z.so live in other search paths on the device, and their presence is normal)
2. BFS starting from `libqohos.so` + `libapp.so`: parse each NEEDED with `llvm-readobj --dynamic-table`;
   if it's found in the deployment directory, keep drilling down; if not, it's missing
3. Filter false positives: a whitelist of system libraries; focus on app-level versioned .so files (.so.N)

## Fixes

**Copy whatever a bottle provides** (zlib/bzip2/brotli/fontconfig) directly into `entry/libs/arm64-v8a/`.

**Two options for what has no bottle** (neither Harmonybrew nor cmd-pkgs has aom, and dav1d only has a .a):

1. **Cross-compile aom from source** (about 5 minutes):
   the v3.11.0 tarball from `github.com/m-ab-s/aom` (a mirror for when googlesource/gitcode is blocked),
   with ohos.toolchain.cmake + `BUILD_SHARED_LIBS=ON`, producing libaom.so.3.

2. **Turn the static library into a .so with whole-archive** (seconds):
```
clang --target=aarch64-linux-ohos --sysroot=$SYSROOT \
  -shared -o libdav1d.so.7 \
  -Wl,--whole-archive libdav1d.a -Wl,--no-whole-archive \
  -Wl,-soname,libdav1d.so.7
```
   Prerequisite: cmd-pkgs' .a is PIC (OHOS's all-PIC policy; tested to work); verify key symbols in the output
   (dav1d_open and so on) with `llvm-nm -D`.

## Variant: imported SHARED libraries don't go into the HAP automatically (Qt6's `QT_HARMONYOS_EXTRA_LIBS`)

The above covers Qt's own chain of transitive dependencies. Another kind of failure is more insidious: **imported SHARED
dependencies linked by the business code** (OpenSSL is typical) are perfectly fine at link time, and the linker writes `libssl.so.3` into
`libapp.so`'s `DT_NEEDED`, but nobody copies it into the HAP when packaging:

```
$ llvm-readelf -d libFinceptTerminal.so | grep NEEDED
  (NEEDED)  Shared library: [libssl.so.3]
  (NEEDED)  Shared library: [libcrypto.so.3]
$ unzip -l app.hap | grep libs/arm64-v8a/ | grep -c ssl
0
```

After installing, `dlopen` fails and the process exits as soon as it starts; a gate that only checks "the HAP file exists" would say PASS.

**Root cause**: Qt6's `_qt_internal_harmonyos_collect_extra_libs`
(`Qt6HarmonyOSMacros.cmake`) only collects Qt targets and the imported targets tracked by `qt_add_executable`;
the imported SHARED that `find_package(OpenSSL)` provides isn't on the list.

**Fix**: explicitly add the soname to `QT_HARMONYOS_EXTRA_LIBS` (the version number must be appended:
packaging looks up files by soname; `${OPENSSL_SSL_LIBRARY}` is `libssl.so`, but the actual
soname is `libssl.so.3`):

```cmake
set_target_properties(FinceptTerminal PROPERTIES
  QT_HARMONYOS_EXTRA_LIBS
  "${OPENSSL_SSL_LIBRARY}.3;${OPENSSL_CRYPTO_LIBRARY}.3")
```

Don't guess the `.3`: check the `SONAME` with `llvm-readelf -d` first, or just copy the
name in `DT_NEEDED`. System libraries (libc/libm/libdl/liblog/libz and so on) don't need adding, but libssl isn't a system library.

**How to verify (two layers)**:
1. After packaging, `unzip -l app.hap | grep libs/`; the libraries must be in the HAP;
2. G5 of `python tools/qt-ohos-run.py verify` now unpacks the HAP and validates the `DT_NEEDED` closure:
   when something is missing it reports `dependency closure broken: libssl.so.3 (needed by libFinceptTerminal.so)`,
   instead of only checking "the `.hap` exists". Libraries you really do want to let through go in `hap_allowed_libs` (prefix match).

## Related pitfall: NTFS symlink corruption in portgraph bottles

When a bottle is extracted onto NTFS, the .so symlinks become 0-byte files or inaccessible reparse points
(getsize throws WinError 1920/4390), causing:
- readobj failures when harmonydeployqt deploys (llvm-readobj failed exit 1)
- EACCES: permission denied lstat when hvigor packages the HAP

Fix: scan the bottle directory, delete .so/.a files whose `lstat` shows a reparse point/0 bytes, and copy in the longest-versioned file with the same prefix
(libX.so ← libX.so.1.2.3). 202 were fixed in this case.

## Verification

Once filled in, success is when the startup log shows the complete chain:
```
setupQtApplication() - sharedLibraryName: libapp.so
opened library '.../libapp.so' with main function
calling 'main' function in library ... (argc=2)
QAbility::onForeground()
```
