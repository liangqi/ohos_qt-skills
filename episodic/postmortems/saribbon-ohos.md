---
id: episodic-projects-saribbon-ohos
type: episodic
domain: project
tags: [saribbon, harmonyos, qt5.12, ribbon-ui, cmake]
created: 2026-06-26
updated: 2026-06-26
status: active
audience: public
refs: [procedural-qt-app-harmonyos-migration, semantic-qt-harmonyos-modules, semantic-qt-harmonyos-build]
summary: >
  Complete SARibbon v2.5.5 HarmonyOS migration: standalone build files + building the MainWindowExample application (48 MB HAP)
  + two build fixes (QDesktopWidget::screen type mismatch + incompatible lazy import syntax).
  Key findings: the QDesktopWidget API inside the SARibbon source returns QWidget* rather than QScreen* under Qt 5.12 OHOS,
  the template's lazy import syntax requires API 12 beta3, and the project needs its own CMakeLists.txt to avoid modifying the source.
  Reusable: the standalone-build-file pattern for keeping third-party Qt library sources intact during HarmonyOS porting.
---

# SARibbon v2.5.5 HarmonyOS migration — lessons learned

## Project overview

| Field | Content |
|-------|---------|
| Date | 2026-06-26 |
| Role | Qt for HarmonyOS developer |
| Tech stack | SARibbon v2.5.5 + Qt 5.12.12 + CMake + the OHOS SDK |
| Scale | A Ribbon UI widget library (35 .cpp files) + the MainWindowExample sample application |
| Status | ✅ Complete (library built + sample application built + HAP packaged) |

## Background and goals

Port [SARibbon](https://github.com/czyt1988/SARibbon) v2.5.5 to HarmonyOS. SARibbon is a Qt-based Ribbon interface widget library that provides a Microsoft Office-style ribbon, suitable for industrial software and complex UIs. v2.5.5 is the version the repository explicitly marks as "Qt 5.12 compatible".

**Goal**: build the SARibbonBar library + the MainWindowExample sample, and package them as an OHOS HAP.

## Key technical decisions

### Decision 1: standalone build files instead of modifying the source

**Background**: SARibbon's CMakeLists.txt targets desktop platforms (Windows/Linux/macOS), and modifying it directly would break the others.

**Choice**: define the entire build in `OhosExampleApp/CMakeLists.txt`, leaving SARibbon's original build system untouched.

**Rationale**: keeps the source intact, making future version upgrades and cross-platform builds easier.

**Result**: success — the upstream SARibbon repository needed no fork or patch.

### Decision 2: use an __attribute__((constructor)) entry point

**Background**: OHOS requires Qt applications to be shared libraries, which need a custom entry point.

**Choice**: use GCC's `__attribute__((constructor))` and `__attribute__((destructor))`.

**Rationale**: OHOS runs constructor functions automatically when a shared library loads, which fits the platform conventions better than main().

**Result**: success — QApplication initializes automatically when the library loads.

### Decision 3: include the full SARibbonBar source

**Background**: SARibbonBar is a library and needs to be linked into the sample application.

**Choice**: include all the SARibbonBar source files directly in OhosExampleApp's CMakeLists.txt rather than linking it as a separate library.

**Rationale**: the OHOS build environment is complex, and a single-library build simplifies dependency management.

**Result**: success — all symbols resolved with no link errors.

## Pitfalls we hit

### Problem 1: QDesktopWidget::screen(int) has a mismatched return type

**Stage**: C++ compilation  
**Symptom**: `SARibbonUtil.cpp:225` fails to compile
```
cannot initialize a variable of type 'QScreen*' with an rvalue of type 'QWidget*'
if (QScreen* sc = dw->screen(idx))
```

**Root cause**: in SARibbon's `#if QT_VERSION < QT_VERSION_CHECK(5, 14, 0)` branch, the return value of `QDesktopWidget::screen(int)` is misused. In Qt 5, that method returns `QWidget*` (deprecated), not `QScreen*`. This is a bug in the SARibbon repository itself.

**Fix**: replace it with the correct Qt 5 API
```cpp
// Before
if (QScreen* sc = dw->screen(idx))

// After (using QGuiApplication::screens())
QList<QScreen*> screens = QGuiApplication::screens();
if (idx >= 0 && idx < screens.size()) {
    QScreen* sc = screens.at(idx);
    return sc->devicePixelRatio();
}
```

**Lesson**: third-party library code may contain platform-specific bugs that cross-compilation exposes. When fixing, check the official Qt 5 documentation to confirm the API signature.

### Problem 2: the template glue code's lazy import syntax is incompatible

**Stage**: ArkTS compilation  
**Symptom**: `OhosExportModules.ts` fails to compile
```
Current configuration does not support using lazy import. 
Lazy import can be used in the beta3 version of API 12 or higher versions.
```

**Root cause**: the Qt 5.12 OHOS template files use the `import lazy` syntax, but the currently configured DevEco Studio `compatibleSdkVersion = "5.0.0(12)"` doesn't support it (API 12 beta3 is required).

**Fix**: remove the `lazy` keyword from every `import lazy`
```typescript
// Before
import lazy { xxx } from '@kit.XxxKit';

// After
import { xxx } from '@kit.XxxKit';
```

**Lesson**: OHOS glue templates may contain newer syntax, so check SDK version compatibility before using them. `lazy import` is an optimization; removing it doesn't affect functionality.

## Project structure

```
project/saribbon-ohos/
├── SARibbon/                          (tag v2.5.5)
│   ├── CMakeLists.txt                 (original, unchanged)
│   ├── src/                           (SARibbonBar library source, unchanged)
│   ├── example/MainWindowExample/     (sample source, unchanged)
│   ├── OhosExampleApp/                (★ new)
│   │   ├── CMakeLists.txt             (OHOS build configuration)
│   │   └── main.cpp                   (constructor entry point)
│   └── HarmonyOS/                     (★ new)
│       ├── entry/libs/arm64-v8a/libOhosSARibbonExample.so
│       └── ...
├── qt_env.md                          (environment configuration)
├── qt_compile_plan.md                 (build plan)
├── compile_fix_pro.md                 (record of problem fixes)
└── qt_summary_saribbon.md             (project summary)
```

## Reusable takeaways

1. **A strategy for porting third-party libraries**: keep the source intact and create standalone build files (such as `OhosExampleApp/CMakeLists.txt`), avoiding forks or patches to the upstream repository.

2. **A Qt 5 API pitfall**: `QDesktopWidget::screen(int)` returns `QWidget*` in Qt 5 (deprecated); the `QScreen*` version only arrived in Qt 5.14+. Cross-version code needs conditional compilation.

3. **OHOS template lazy import**: Qt OHOS templates may contain newer syntax; when you hit a `lazy import` error, just remove the `lazy` keyword — it doesn't affect functionality.

4. **Choosing an entry point**: OHOS shared libraries should initialize the Qt environment via `__attribute__((constructor))`, which fits the platform conventions better than a custom main().

5. **A single-library build simplifies dependencies**: including the library source directly in the application's CMakeLists.txt avoids the dependency-management complexity of linking multiple libraries.

## Related resources

- [[procedural-qt-app-harmonyos-migration]] — The Qt application HarmonyOS migration process
- [[semantic-qt-harmonyos-modules]] — Qt OHOS module support status
- [[semantic-qt-harmonyos-build]] — The Qt OHOS build guide
- [[episodic-projects-coin3d-quarter-ohos]] — The Coin3D Quarter OHOS migration (a similar project)

## File inventory

| File | Path | Notes |
|------|------|-------|
| SARibbon source | `project/saribbon-ohos/SARibbon/` | tag v2.5.5, unmodified |
| OHOS build configuration | `project/saribbon-ohos/SARibbon/OhosExampleApp/CMakeLists.txt` | The standalone build file |
| Entry point | `project/saribbon-ohos/SARibbon/OhosExampleApp/main.cpp` | constructor/destructor |
| Build plan | `project/saribbon-ohos/qt_compile_plan.md` | The complete build steps |
| Problem record | `project/saribbon-ohos/compile_fix_pro.md` | The 2 build fixes |
| Project summary | `project/saribbon-ohos/qt_summary_saribbon.md` | Environment, versions, verification |
| HAP artifact | `project/saribbon-ohos/SARibbon/HarmonyOS/entry/libs/arm64-v8a/libOhosSARibbonExample.app` | 48 MB |
