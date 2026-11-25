---
id: procedural-demo-generation
type: procedural
domain: workflow
tags: [workflow, demo, qt, rendering, testing, opengl, project-creation]
created: 2026-06-12
updated: 2026-07-23
status: active
audience: public
refs: [procedural-qt-app-harmonyos-migration,semantic-qt-harmonyos-build,semantic-qt-harmonyos-project-structure,problem-runtime-crash-ohos-deviceinfo-global-expression]
summary: >
  The standalone demo generation workflow (a six-step loop): understand the requirement → technical design → create the project → write the code → verify the build → capture documentation.
  Applies when the user directly asks to "write a demo" / "generate a test project" and similar standalone demo scenarios.
  Distinct from the reproduction demos generated within framework issue analysis.
---

# The demo generation workflow

> When the user asks you to create a standalone Qt demo / test project (not a bug reproduction), follow this process.

---

## When to use this

- The user asks you to "write a demo", "generate a demo", or "create a test project"
- You need to verify a Qt feature / rendering effect / API usage
- You need example code demonstrating a technical feature
- A Qt project for promotional/demonstration purposes

**When this does *not* apply** (other workflows cover it):

- Creating a reproduction demo as part of bug analysis → use `framework-issue-analysis.md`
- Porting a whole application to HarmonyOS → use `qt-app-harmonyos-migration.md`

---

## Phase 1: understand the requirement

> **📋 TODO sync point**: add a "📌 In progress" entry to `<LOCAL_TODO>` → `just started`

Clarify the following:

| Item to confirm | Description |
|-----------------|-------------|
| The demo's goal | Feature verification / rendering effect / API usage demonstration / performance testing |
| Core functionality | The specific features or APIs to demonstrate/test |
| Target platform | Desktop (Windows/macOS/Linux) or HarmonyOS (OHOS) |
| Qt version | 5.12 / 5.15 / 6.x / cross-version compatible |
| Special requirements | Performance targets, visual effects, deep nesting, native windows, and so on |

**If the user already gave a clear requirement** (such as "write a rendering demo"), there's no need to confirm each item — just infer from what they said.

---

## Phase 2: technical design

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase 1 done: requirement clarified`

Work through the key technical decisions:

1. **Which Qt modules**: decide which Qt modules you need (Widgets / Quick / OpenGL / Multimedia / ...)
2. **Build system**: qmake (.pro) or CMake (CMakeLists.txt)
3. **Project structure**: single file vs. multiple files, and the directory layout
4. **Technical approach**: how to implement the core functionality (for example, whether OpenGL uses immediate mode or a shader pipeline)

### Choosing a build system

| Target platform | Build system | Rationale |
|-----------------|--------------|-----------|
| Desktop (Windows/macOS/Linux) | qmake (.pro) | Simple and fast; good for a standalone demo |
| HarmonyOS (OHOS) | CMake | The OHOS project standard, consistent with the glue-code template |
| Cross-platform | CMake | A single build, making later HarmonyOS porting easier |

---

## Phase 3: create the project

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase 2 done: technical approach designed`

### 3.1 Decide the project directory

```
<INTERNAL_KB_ROOT>/<INTERNAL_DEMO><demo-name>/
```

Naming convention for `<demo-name>`: a short descriptive name with words separated by `-` (such as `render-layers` or `mediaplayer-duration-test`).

### 3.2 Create the project files

Choose based on the target platform:

**Desktop (qmake)**:
```
<INTERNAL_DEMO><demo-name>/
├── <demo-name>.pro    ← QT += the modules you need
└── main.cpp           ← the complete code
```

**HarmonyOS (CMake + the glue template)**:
```
<INTERNAL_DEMO><demo-name>/
├── CMakeLists.txt
├── main.cpp / main.qml
├── qml.qrc            ← if you use QML
└── README.md
```

> A HarmonyOS project must be created from the glue template bundled with the Qt source (the path is `OHOS_TEMPLATE_SRC` in `ENV.md`, i.e. `<QT_SRC>/qtbase/src/harmonyos/templates`).
> See [[qt-app-harmonyos-migration]] phase 1.3 and [[qt-harmonyos-project-structure]] for details.
>
> **Without the Qt source**: download `templates-0625.zip` from the GitCode releases into `workspace/templates/`,
> then copy the template from there. Run `bash skills/kb-init/scripts/download-template.sh --dest=workspace/templates`.
> Download page: https://gitcode.com/ohos-qt/qt-harmonyos-src/releases

> ⚠️ **Pitfall: the source tree template's OhosExportModules.ts is a stale minimal version and will crash if used as-is**
>
> The `OhosExportModules.ts` in `qtbase/src/harmonyos/templates` predates the libqohos you link against; it has only 5 `@kit.*` lazy imports + the factories API (`getOhosExportModulesFactories` returning arrow factories) and **lacks every `@ohos.*` eager import**. When libqohos starts or recreates, its bare eval of `"@ohos.deviceInfo"` is rejected by the ArkTS runtime (not registered as a "known module path") → Napi::Error `global expression doesn't start with known module path: '@ohos.deviceInfo'` → SIGABRT. On top of that, the factories API mismatches the 515-generation libqohos's objects API (`makeJsModulesMap` + reading the `"modules"` field), so @kit.*/LocalStorage/QEmbeddedComponentCreator are silently discarded.
>
> **Mandatory checkpoints** (immediately after creating the project):
> 1. `strings <SDK>/plugins/platforms/libqohos.so | grep -E "^modules$|^modulesFactories$"` → determine the API (modules = objects / modulesFactories = factories)
> 2. Replace `entry/src/main/ets/qability/OhosExportModules.ts` + `QtUtils.ets` with the **canonical full reference template** (26 `@ohos.*` + 13 `@kit.*` **eager default-imports**, the objects API, `getModulesMapForQt`), and correspondingly change `getModulesFactoriesMapForQt()` → `getModulesMapForQt()` in `QAbilityStage.ets`/`QChildProcess.ets`
> 3. See [[problem-runtime-crash-ohos-deviceinfo-global-expression]] for details (including the diagnostics for both generations of the @ohos.deviceInfo crash family)

### 3.3 Qt+CEF / WebEngine migration demos (special: use the grafting script, not the usual 6 steps)

If the demo needs **web embedding** (QtWebEngine is out of scope on HarmonyOS — see [[qt-harmonyos-modules]]), take the Qt+CEF route — **don't hand-create the project per §3.1/3.2**; generate it in one shot with the grafting script:

- **The guide**: `procedural/qt-cef-ohos-dev-guide.md` (the WebEngine→CEF API mapping + migration plan + the de-versioned component package + adapting to version upgrades).
- **The script**: `kb-cef-graft.py` + the configuration `kb-cef-graft.config.example.json` (all environment configuration lives in the config file: deveco/device/SDK version/the Qt .so list, so switching environments means changing the config, not the script) — **shipped with the CEF component package, not part of this knowledge base** (see dev-guide §2.3; maintainers get it from the internal maintenance repo).
- **One command** (graft + sign + install + launch + crash check):
  ```bash
  cp kb-cef-graft.config.example.json .config.json  # edit deveco/device/qt_libs etc.
  python kb-cef-graft.py --config .config.json \
    --template <Qt OHOS template> --qt-sdk <Qt OHOS SDK> \
    --ohqtcef-glue <the OpenQtCef glue> --output <output project> --run
  ```
  `--run` automatically does devecocli signature generate + run (build + install + launch QAbility) + log --crash. **The correct approach is grafting CEF onto the Qt OHOS template** (whose QPA glue version is correct), not modifying a CEF demo. The script bakes in 15 runtime pitfalls (P1-P15, see the `_PITFALLS` comment).
- **Verification**: the `com.example.qtcefdemo` process + the CEF subprocesses (`:NetworkService`/`:Renderer`) + `devecocli log --crash --bundle-name com.example.qtcefdemo` showing no new crashes.

---

## Phase 4: write the code

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase 3 done: project created`

### Coding conventions

1. **Prefer a single file**: keep the demo in a single `main.cpp` where possible, to reduce file switching
2. **Compatibility**: use APIs compatible with Qt 5.12 (`QOpenGLWidget` rather than `QOpenGLWindow`, unless explicitly required)
3. **Comments**: explain key design decisions in comments
4. **A file header comment**: covering the demo's purpose, a structure diagram, and compatible versions
5. **Meaningful visual output**: the demo should give direct visual feedback so you can tell whether it works

### Demo types and what to emphasize

| Type | Emphasis | Example |
|------|----------|---------|
| **Feature demonstration** | Highlighting one API/feature's usage | Calling QtOhosExtras startAbility |
| **Rendering test** | Visual effect + performance metrics (FPS) | Layered widgets + OpenGL rendering |
| **API comparison** | A before/after comparison | Replacing QProcess with posix_spawnp |
| **Bug reproduction** | Minimal reproduction code + steps | Belongs to the framework issue analysis workflow, not this one |
| **Performance benchmark** | Timing + statistics | The performance of creating/laying out many widgets |

### File header template

```cpp
/*
 * <demo-name> — a one-line description
 *
 * Structure (outermost to innermost):
 *   MainWindow (...)
 *    └─ Layer-1 ...
 *        └─ Layer-2 ...
 *            └─ ...
 *
 * Compatible with: Qt 5.12 / 5.15 / 6.x
 * Usage: qmake && make && ./<demo-name>
 */
```

---

## Phase 5: verify the build

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase 4 done: code written`

### 5.1 Build

```powershell
# Desktop (qmake)
cd <INTERNAL_DEMO><demo-name>
qmake <demo-name>.pro
mingw32-make.exe -j8      # Windows MinGW
# or make -j8             # macOS/Linux

# HarmonyOS (CMake)
# Build and deploy through DevEco Studio or the hdc command line
```

### 5.2 Verification checklist

- [ ] It builds (no warnings, or only harmless ones)
- [ ] It runs correctly (the visuals match expectations)
- [ ] If there are performance metrics, the FPS/timing data displays correctly
- [ ] No memory leaks (a quick check: run it for 30 seconds and watch memory)

### 5.3 Handling build failures

If the build fails, follow the build troubleshooting process:
1. Check that `QT +=` includes every module you need
2. Check that the `#include`s are complete
3. Check API compatibility (Qt 5.12 vs. 5.15 vs. 6.x)
4. Check `problems/_lookup.md` for a known build error

---

## Phase 6: documentation and knowledge capture

> **📋 TODO sync point**: update `<LOCAL_TODO>` — move it from "📌 In progress" to "✅ Completed"

### 6.1 README (optional but recommended)

```markdown
# <demo-name>

> A one-line description

## Purpose
...

## Build and run
...

## Structure
...
```

### 6.2 Knowledge base updates

| Action | File |
|--------|------|
| Commit the changes | git commit (message format `<type>: <short description>`) |
| If you found something new | Capture it in `episodic/` or `problems/` |

---

## Checklist

- [ ] The requirement is clear (goal/features/platform/version)
- [ ] The technical approach is designed (modules/build system/structure)
- [ ] The project is created in `<INTERNAL_DEMO><demo-name>/`
- [ ] The code is written (single file preferred, Qt 5.12 compatible, commented)
- [ ] It builds
- [ ] It runs correctly
- [ ] A git commit has been made

---

## Relationship to other workflows

| Scenario | Workflow to use |
|----------|-----------------|
| Creating a standalone feature/rendering/performance demo | **Demo generation** (this process) |
| A reproduction demo during bug analysis | Framework issue analysis → phase one |
| Porting a whole application to HarmonyOS | Application porting |

---

## Supply chain

> See the workflow supply chain, §Demo generation

| Dimension | Details |
|-----------|---------|
| **Upstream source** | ① A direct user request ("write an xx demo") ② Self-driven (feature verification/rendering tests) ③ Promotional/demonstration needs |
| **Upstream input** | A description of the demo's goal, the functional requirements, and the target platform/version |
| **Downstream recipients** | Internal use (testing and verification) / promotional demos / customer demonstrations |
| **Deliverables** | `<INTERNAL_DEMO><demo-name>/`: the complete project + a README (optional) |
| **Deliverable path** | `<INTERNAL_KB_ROOT>/<INTERNAL_DEMO>` |
| **Routing rules** | None (standalone delivery); if you find a framework bug → move to framework issue analysis; if it needs porting to HarmonyOS → move to application porting |

---

## Related context

- [[qt-harmonyos-project-structure]] — Project structure (a reference for creating HarmonyOS projects)
- [[qt-harmonyos-build]] — The build guide (build environment configuration)
- [[qt-app-harmonyos-migration]] — Application migration (using the HarmonyOS project template)
- The workflow supply chain — An overview of the workflow supply chain

## Content sources

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | Distilled from actually creating demos such as render-layers and mediaplayer-duration-test |
