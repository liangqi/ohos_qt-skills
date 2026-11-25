---
id: problem-build-qt6-app-must-be-shared
type: problem
domain: build
tags: [SHARED, QPA, dlopen, main, QAbility, OBJECT-library, static-linking, application-layer-classes, tdesktop]
created: 2026-11-18
updated: 2026-11-18
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-golden-rules]
summary: >
  The application target must be SHARED: on the HarmonyOS side, QAbility loads lib<app>.so with dlopen and calls its
  main. Built as a static library/executable, it exits right at startup or dlsym can't find the entry point; backend libraries that depend on application-layer
  classes can only stay OBJECT, otherwise the static archive gets pulled into the .so and causes duplicate symbols.
leader_summary: >
  Established the "the application is a .so, not an executable" linking model, and the OBJECT vs STATIC trade-off
impact: [Build system, Linking model]
deliverables: [problem record]
evidence: []

error_message: >
  dlopen failed: library "libapp.so" not found
  # or the process exits as soon as it starts, with no application logs at all in hilog
  # or at link time: undefined reference to `main'
  # or duplicate symbol: the same set of source files compiled once into a STATIC library and once into the .so
error_code: ""
keywords: [SHARED, add_library SHARED, qt_add_executable, QPA, dlopen, dlsym main,
           QAbility, EntryAbility, OBJECT library, STATIC, duplicate symbols, exits at startup]
symptoms: "Compiling and linking succeed and the HAP gets assembled, but after installing, aa start launches it and it exits immediately; or the link
  reports undefined reference to main; or duplicate symbols appear after changing a backend library to STATIC"
environment: "Qt 6 HarmonyOS kit (QAbility template) + a large C++ application (tested with tdesktop 7.4.4)"
---

# The application target must be SHARED: QAbility calls main after dlopen

## Symptoms

Three seemingly unrelated failures with the same root cause:

1. **Exits at startup**: `aa start` returns success, the process lives a few hundred milliseconds and is gone, and hilog only has
   `appspawn` records, not a single log line from the application itself.
2. **main not found at link time**: `undefined reference to 'main'`, even though the source clearly has
   `int main(...)`.
3. **Duplicate symbols**: after changing some backend library from `SHARED` to `STATIC`, the link reports
   `duplicate symbol`, pointing at two copies of the same set of source files.

## Root cause

On the HarmonyOS side, the Qt application's entry point isn't C++'s `main` but ArkTS's `QAbility`:

```
entry/src/main/ets/qability/QAbility.ets
  → dlopen("lib<app>.so")
  → dlsym(handle, "main")
  → main(argc, argv)      // only after this does it enter Qt's QApplication flow
```

So the build output must be a **shared library** that exports `main`. Three direct consequences:

- The ELF produced by `add_executable()` isn't `ET_DYN`, so QAbility's `dlopen` can't load it;
- If you write the main program as a `STATIC` library and "link it into" some shell, the shell doesn't export a `main` symbol;
- If a backend library is `STATIC`, it gets pulled wholesale into `lib<app>.so`; and when that `STATIC` library is
  also linked somewhere else, the same symbols appear twice.

## Fix

**Main program**:

```cmake
add_library(app SHARED ${APP_SOURCES})
# or Qt6's wrapper (internally it's add_library(... SHARED))
qt_add_executable(app ${APP_SOURCES})
```

And confirm on the output:

```bash
llvm-readelf -h libapp.so | grep Type      # expect DYN
llvm-nm -D --defined-only libapp.so | grep ' main$'
```

`verify`'s G4 asserts each output is `ELF64 / AArch64 / DYN`, and G13 checks whether
the `DT_NEEDED` closure is complete.

**The OBJECT / STATIC trade-off for backend libraries**: the criterion is "will this library be depended on in reverse
by other modules".

- The backend library references application-layer classes (`Data`, `Session`, `Window`, and the like) → it can only be
  `OBJECT`: its object files go straight into `lib<app>.so` instead of forming a separate library, so there are never
  two copies of the symbols.
- The backend library is self-contained (depends only on Qt and third parties) → it can be `SHARED`, built as its own
  `.so` and attached via `DT_NEEDED` (in that case remember to put it into the HAP's
  `libs/<abi>/`; see [runtime-hap-missing-so-closure](runtime-hap-missing-so-closure.md)).

Tested (tdesktop 7.4.4): backends that reference application-layer classes, such as `lib_ui`, `lib_webview`, and `lib_webrtc`,
all stay `OBJECT`; `libtdapp.so` (337 MB) is itself the main library that gets
`dlopen`ed.

## Verification

```bash
python tools/qt-ohos-run.py build && python tools/qt-ohos-run.py package
python tools/qt-ohos-run.py verify          # G4 = ELF64/AArch64/DYN
unzip -l build/hap/*.hap | grep 'libs/arm64-v8a/libapp'   # main library is in the package
```

## Related

- [build-qt6-no-undefined-symbols](build-qt6-no-undefined-symbols.md): symbol closure
- [runtime-hap-missing-so-closure](runtime-hap-missing-so-closure.md): `.so` closure
- `semantic/qt-harmonyos-golden-rules.md` B1
