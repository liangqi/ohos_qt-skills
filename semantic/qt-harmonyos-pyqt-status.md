---
id: semantic-qt-harmonyos-pyqt-status
type: semantic
domain: tech
tags: [qt, pyqt, python, harmonyos, ohos, runtime, cpython, feasibility]
created: 2026-08-26
updated: 2026-08-26
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-build, semantic-qt-harmonyos-modules, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-third-party-libs]
summary: >
  Feasibility status of PyQt5 for HarmonyOS: verified feasible via pyqt5-demo (Qt 5.15.16).
  The architecture is identical to standard C++ Qt (the libqohos.so QPA plugin); the only difference is that the C++ launcher layer
  embeds a CPython 3.12 runtime to interpret Python scripts. It depends on DevPython-OH (a cross-compiled CPython)
  and PythonForArkUI (the PyQt5 site-packages). Known pitfalls: openblas needs a binary patch,
  sys.exit() produces appspawn crash logs, and only tablet/2-in-1 are supported.
leader_summary: >
  Completed the feasibility study and demo analysis for PyQt5 on HarmonyOS, confirming that PyQt5 applications run on OHOS
  and providing a technical reference path for porting open-source PyQt applications.
impact: [Migration efficiency, Framework support]
deliverables: [knowledge page]
evidence: [Analysis of the pyqt5-demo repository (https://gitcode.com/ohos-qt/pyqt5-demo)]
---

# PyQt5 for HarmonyOS status

> **In one sentence**: PyQt5 works on HarmonyOS, reusing the standard Qt for OHOS QPA plugin architecture; the only difference is that the C++ launcher embeds a CPython runtime.

## Feasibility conclusions

| Item | Conclusion |
|------|------------|
| **Cross-compiling CPython for OHOS** | ✅ Feasible — [DevPython-OH](https://gitcode.com/OpenHarmonyPCDeveloper/DevPython-OH) provides a Python 3.12 OHOS build |
| **Running PyQt5 on OHOS** | ✅ Verified — pyqt5-demo (a glmark2 GPU benchmark GUI) runs on a real device |
| **Reusing the QPA architecture** | ✅ Fully reused — libqohos.so + XComponent, identical to a C++ Qt application |
| **OpenGL ES rendering** | ✅ Uses OpenGL ES 2.0 via PyOpenGL |
| **Demo source** | [ohos-qt/pyqt5-demo](https://gitcode.com/ohos-qt/pyqt5-demo) (commit 798669d) |

## Architecture (the call chain)

```
HarmonyOS UIAbility (QAbility.ets)
  → libqohos.so (the Qt QPA platform plugin, standard architecture)
    → libpyqtlauncher.so (the C++ main entry point)
      → Py_Initialize()
      → PyRun_SimpleFileEx("app.py")
        → the Python 3.12 runtime (CPython)
          → PyQt5 (QtWidgets, QtCore, QtGui)
          → PyOpenGL (OpenGL ES 2.0)
            → the user's Python application code
```

### Differences from a standard C++ Qt application

| Layer | C++ Qt application | PyQt5 application |
|-------|--------------------|-------------------|
| The ArkTS layer (QAbility.ets / XComponent) | ✅ Identical | ✅ Identical |
| The QPA plugin (libqohos.so) | ✅ Identical | ✅ Identical |
| The C++ main entry point | `main()` → `QApplication` + business logic | `main()` → `Py_Initialize()` + `PyRun_SimpleFileEx()` |
| Application code | C++ compiled into a .so | Python scripts in resfile/, interpreted at runtime |
| Extra dependencies | None | libpython3.12.so + the PyQt5 site-packages (~1.8 GB) |

## Dependency list

### External dependencies (all assembled manually, gitignored)

| Dependency | Source | Where it goes |
|------------|--------|---------------|
| Qt 5.15.16 OHOS | Built from the `tqtc/harmonyos-5.15.16` branch | `entry/libs/arm64-v8a/*.so` + `libqohos.so` |
| The Python 3.12 runtime | [DevPython-OH](https://gitcode.com/OpenHarmonyPCDeveloper/DevPython-OH) | Headers → `cpp/thirdparty/include/`, .so files → `libs/arm64-v8a/` |
| The PyQt5 site-packages | [PythonForArkUI](https://gitcode.com/OpenHarmonyPCDeveloper/PythonForArkUI), `other/site-packages` | `libs/arm64-v8a/Python/lib/python3.12/site-packages/` |

### Python package dependencies (requirements.txt)

| Package | Version requirement | Purpose |
|---------|---------------------|---------|
| PyQt5 | ≥ 5.15.0 | The Qt Python bindings |
| PyOpenGL | ≥ 3.1.5 | The OpenGL Python bindings |
| PyOpenGL-accelerate | ≥ 3.1.5 | OpenGL acceleration |
| numpy | ≥ 1.19.0 | Numerical computing |

### Dependency assembly steps

```bash
# 1. Python 3.12 headers and runtime
cp -r python-wheel-3.12/include entry/src/main/cpp/thirdparty/include
cp python-wheel-3.12/lib/*.so* entry/libs/arm64-v8a/
mv entry/libs/arm64-v8a/python3.12 entry/libs/arm64-v8a/Python/lib/python3.12

# 2. The Qt 5.15.16 runtime
cp <qt-install>/lib/*.so entry/libs/arm64-v8a/
cp <qt-install>/plugins/platforms/libqohos.so entry/libs/arm64-v8a/

# 3. The PyQt5 site-packages
cp -r <PythonForArkUI>/other/site-packages \
  entry/libs/arm64-v8a/Python/lib/python3.12/site-packages

# 4. The openblas binary patch (must be run under Linux/WSL)
openblas_so=entry/libs/arm64-v8a/Python/lib/python3.12/site-packages/numpy.libs/libopenblasp-r0-76071c68.3.27.so
printf '\x1f\x20\x03\xd5' | dd of=$openblas_so bs=1 seek=2464508 conv=notrunc
```

## Key points of the C++ launcher implementation

The core logic of a PyQt5 application's C++ entry point (`pyqtlauncher.cpp`):

```cpp
int main(int argc, char *argv[]) {
    // 1. Point PYTHONHOME at the Python runtime inside the HAP
    setenv("PYTHONHOME", "/data/storage/el1/bundle/libs/arm64/Python", 1);

    // 2. Initialize the Python interpreter
    Py_Initialize();

    // 3. Set sys.argv
    wchar_t *pyArgv0 = Py_DecodeLocale(scriptPath, NULL);
    PySys_SetArgvEx(1, &pyArgv0, 1);

    // 4. Run the Python script
    FILE *pyFile = fopen(scriptPath, "r");
    int ret = PyRun_SimpleFileEx(pyFile, scriptPath, 1);

    // 5. Clean up
    PyMem_RawFree(pyArgv0);
    Py_Finalize();
    return ret;
}
```

**Key points**:
- `PYTHONHOME` must point at the Python runtime directory inside the HAP package (`libs/arm64/Python`)
- The script path is the absolute path after the HAP is unpacked (`/data/storage/el1/bundle/entry/resources/resfile/...`)
- Use an RAII guard to manage the `Py_Initialize` / `Py_Finalize` lifecycle

### CMake configuration

```cmake
add_library(pyqtlauncher SHARED pyqtlauncher.cpp hilog-easy.c)
target_link_libraries(pyqtlauncher PUBLIC libace_napi.z.so libhilog_ndk.z.so)

set(PYTHON_INCLUDE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/thirdparty/include/python3.12)
set(PYTHON_LIBRARIES -l:libpython3.12.so.1.0)

target_include_directories(pyqtlauncher PRIVATE ${PYTHON_INCLUDE_DIR})
target_link_directories(pyqtlauncher PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../../../libs/${OHOS_ARCH})
target_link_libraries(pyqtlauncher PRIVATE ${PYTHON_LIBRARIES})
```

## Known problems and limitations

| # | Severity | Problem | Cause | Solution |
|---|:--------:|---------|-------|----------|
| 1 | 🟠 | numpy's openblas crashes on OHOS | One ARM instruction in openblas raises an exception in the HarmonyOS runtime | Binary-patch it to a NOP (`\x1f\x20\x03\xd5` at offset 2464508) |
| 2 | 🟡 | `sys.exit()` produces crash logs | appspawn intercepts the `exit()` syscall | Functionality is unaffected and the logs can be ignored; or use `QApplication.quit()` instead |
| 3 | 🟠 | Only tablet / 2-in-1 are supported | Phone devices have a bug where a minimized window can't be restored (QTFOROH-1076) | Exclude phone from deviceTypes in module.json5 |
| 4 | 🟡 | The HAP is large (~1.8 GB) | CPython + PyQt5 + numpy + Qt are all packaged | Trim the site-packages you don't need; consider packaging only the modules actually used |
| 5 | 🟡 | Hard-coded Python paths | `PYTHONHOME` and the script path are hard-coded as absolute paths in the launcher | They could be parameterized through environment variables or a config file |

## A decision tree for porting PyQt applications to HarmonyOS

```
A request to port a PyQt application to HarmonyOS
  │
  ├─ Does it only use QtWidgets/QtCore/QtGui? ───────→ ✅ Feasible; follow the demo architecture
  │
  ├─ Does it use QML/QtQuick? ───────────────────────→ ⚠️ Unverified
  │   │                                                   The PyQML bindings would need building separately
  │   └─ Can it be rewritten with QtWidgets? ────────→ ✅ Feasible
  │
  ├─ Does it use QtMultimedia? ──────────────────────→ 🔴 Blocked
  │                                                       Qt Multimedia isn't included in the OHOS SDK
  │
  ├─ Does it depend on many C extension modules? ────→ ⚠️ Verify each one
  │   │                                                   Every C extension must be cross-compiled for OHOS
  │   └─ Is there a pure-Python alternative? ────────→ ✅ Swap it in, then follow the standard process
  │
  └─ Does it depend on platform-specific features (dbus, system tray, ...)? ──→ 🔴 Replace API by API
                                                          See [[qt-harmonyos-api-mapping]]
```

## Relationship to the C++ Qt migration workflow

For a PyQt application, the **ArkTS layer, the QPA layer, and the HAP packaging layer** are identical to a C++ Qt application, so all the iron rules in [[qt-harmonyos-golden-rules]] apply (B1–B12 build and deployment, W1–W5 window management, L1–L4 lifecycle).

The only difference is the **launcher layer**:
- C++ Qt: `main()` creates `QApplication` and the business windows directly
- PyQt5: `main()` starts CPython, and the Python script creates `QApplication` and the business windows

So a PyQt migration reuses phases 1–4 of the [[qt-app-harmonyos-migration]] workflow (pre-flight → feasibility → build and deploy → verify); you only need to add preparing the Python runtime and site-packages to phase 0.

## Related context

- [[qt-harmonyos-overview]] — The overall Qt for HarmonyOS architecture
- [[qt-harmonyos-build]] — The Qt build process
- [[qt-harmonyos-modules]] — The Qt module support matrix
- [[qt-harmonyos-platform-limits]] — Platform limitations
- [[qt-harmonyos-project-structure]] — Project structure
- [[qt-harmonyos-third-party-libs]] — Integrating third-party libraries
- [[qt-harmonyos-golden-rules]] — Quick reference to the iron rules

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Verified the feasibility of PyQt5 for HarmonyOS, confirming that open-source PyQt5 applications can be ported and widening the scope of migration support |
| Scope of impact | Migration assessments for open-source PyQt applications, consulting on commercial PyQt projects |
| Deliverables | Knowledge page, demo repository analysis |
| Evidence | Source analysis of the pyqt5-demo repository (commit 798669d) |
| How to reuse | When you get a request to port a PyQt application to HarmonyOS, scan this page first to judge feasibility and the technical path |
