---
id: semantic-qt-ohos-project-analyzer-workflow
type: semantic
domain: tech
tags: [qt, harmonyos, ohos, porting, workflow, dependency-analysis, build-orchestration, verification]
created: 2026-06-02
updated: 2026-07-02
status: active
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-overview, semantic-qt-harmonyos-platform-limits]
summary: >
  The core workflow for porting a Qt project to OHOS: the iron-rule constraints, how to inventory dependencies, the build orchestration process, and the dual cross-check protocol
---

# The Qt-OHOS project analyzer workflow

## Iron rules

All porting work must obey the iron rules below; violating any one of them means the process has failed.

### Meta iron rules

**Iron rule α — the rule review mechanism**
Before performing any task, review every iron rule in this section in full and confirm there's no risk of violating one. "Remembering only some of the rules and acting anyway" is forbidden.

**Iron rule β — file operation discipline**
Any write, modification, or deletion of a file must have a process justification, error evidence, and a captured record. Forbidden:
- Modifying files ahead of the step that calls for it
- Preventive changes not authorized by the process ("I think this might break later, so I changed it now")
- Deleting or overwriting historical fix records

### Process ordering iron rules

Follow the skill's process strictly; skipping steps or improvising outside the plan is forbidden. `qt_env.md` must maintain a "process progress" table, marking each completed step with ☑ + a timestamp (YYYY-MM-DD HH:mm). **Before moving to the next step, verify the previous one is ☑.**

| Step | Completion marker |
|------|-------------------|
| §1 Requirements discussion | The user confirms the requirements |
| §2 Confirming the prerequisites | Every item in `qt_env.md`'s prerequisite checklist is ☑ |
| §3 Dependencies and environment | The dependency overview table is appended with clear statuses |
| §4.1 Knowledge base preparation | The `compile_fix_pro.md` path is recorded |
| §4.2 Pre-build preparation | `qt_compile_plan.md` is created and confirmed by the user |
| §4.3 Running the build | The build is error-free, or every error is fixed and captured |
| §4.4 Build completion confirmation | Every item in the verification checklist passes |
| §4.5 Summary document output | `qt_summary_<project>.md` is generated and confirmed by the user |

### The no-speculation iron rule

**When you hit a problem, read the code and check the knowledge base first; speculating without evidence is forbidden.**

| Violation | The correct approach |
|-----------|----------------------|
| Guessing without reading the code | Read the source first |
| "It might be because..." | Find the specific line of code |
| "I think it's probably..." | Say explicitly "there isn't enough evidence; I need XXX" |

**Warning signs** (stop immediately if you catch yourself thinking any of these):
- Drawing a conclusion from documentation alone
- Assuming another platform's behavior applies to OHOS
- "This should work the same as Windows..."
- "This error is probably..."

→ **Caught a warning sign → stop. Go back and read the code.**

### The knowledge-base-first iron rule

When you hit a problem, the **first** step is to search `compile_fix_pro.md` for a matching solution:
- Found a match → apply it directly without re-analyzing
- No match → analyze normally, and append the new solution after fixing it

⛔ **Skipping the knowledge base and going straight to analysis is a violation.**

### The platform isolation iron rule

Every OHOS adaptation must be isolated with a conditional branch; modifying shared logic directly is forbidden:

```cpp
// C++ code
#if defined(Q_OS_OHOS)
    // The OHOS-specific implementation
#else
    // The original logic (unchanged)
#endif
```

```cmake
# CMake
if(OHOS)
    # OHOS configuration
else()
    # Other platforms' configuration
endif()
```

```qmake
# qmake
ohos: {
    # OHOS configuration
} else {
    # Other platforms' configuration
}
```

### The source-first iron rule

Change only the source (CMakeLists.txt, .pro files, source code), never generated artifacts (Makefiles and intermediates under build/) as your primary fix. Every change must be traceable to a source file.

### The fix-capture iron rule

After a successful fix you **must** capture it in `compile_fix_pro.md`. Once you've fixed more than 3 problems, append the earlier fixes to the knowledge base before continuing.

**The capture format**:
```markdown
## Problem title
- Problem description: the exact error message
- Where it occurred: build / link / packaging / runtime
- Cause: the root cause analysis
- Fix: the specific steps and code changes
- Files changed: the file paths involved
- Verification command: the command that confirms the fix worked
```

### The gate-failure iron rule

You **must not** mark success in any of these cases:
- Missing build artifacts / no HAP produced
- Installation fails / launch fails
- A Qt .so is missing / an incomplete RPATH / a broken dependency

Only when every gate passes may a step be marked complete.

### The dependency inventory iron rule

Never assume a dependency exists. You must record each dependency's status explicitly in `qt_env.md`:
- ☑ Ready
- ☐ Missing
- ⚠️ A degraded alternative

Skipping the inventory and building anyway is a violation.

### The platform-limitation degradation iron rule

Once something is confirmed to be a platform limitation (syscall/permission/filesystem/dynamic library loading), record it in `qt_env.md` marked "platform limitation" and choose an alternative or degrade the feature. Repeatedly retrying the same command is forbidden.

### The user interaction iron rule

Any step that says "ask the user" or "put the question to the user" **must actually ask and wait for a reply**. Forbidden:
- Continuing without asking
- Assuming an answer before the user replies
- Not following up when the user's reply is vague ("should be fine")

No reply from the user = the step isn't complete, and you must not move on.

---

## Dependency inventory methodology

### 3.0 Understand the project's purpose

**Steps**:
1. Read the README.md, official documentation, and source comments
2. Establish the **core functionality** (e.g. a code editor component, a charting library)
3. Establish the **target artifact type** (shared library / static library / executable)

**Output**: a 2–3 sentence project summary appended to `qt_env.md`.

### 3.1 Assess the Qt version dependency

#### Qt5 projects

Confirm the minimum compatible minor version and go straight to 3.2.

#### Qt6 projects → assessing Qt5 compatibility

**Background**: the current HarmonyOS Qt branches only support Qt5 (5.12.12 / 5.15.16), so a Qt6 project needs a feasibility assessment.

**Step A: detect Qt6-only features**

Search the source and build files for:

| What to detect | How to search |
|----------------|---------------|
| Qt6-only modules | `Qt6::` / `find_package(Qt6` / `QT += core5compat` |
| The Qt6 CMake API | `qt_add_qml_modules` / `qt_add_executable` |
| Qt6-only classes | `#include <QPromise>` / `QFuture::then` |
| QML changes | `import QtQuick` (with no version number = Qt6 style) |
| C++17 + Qt6 | `CMAKE_CXX_STANDARD 17` appearing alongside Qt6 APIs |

- No hits → it's Qt5-compatible; continue
- Hits → go to Step B

**Step B: look for a Qt5 version**

```bash
# 1. A quick filter by name
git branch -a | grep -iE 'qt5|5\.[0-9]+'
git tag -l | grep -iE 'qt5|5\.[0-9]+'

# 2. List every tag/branch (don't skip this)
git tag -l --sort=-creatordate
git branch -a

# 3. Check the build files' contents (without switching branches)
git show <ref>:CMakeLists.txt 2>/dev/null | grep -iE 'find_package\(Qt5|Qt5::'
git show <ref>:<project>.pro 2>/dev/null | grep -iE 'QT\s*\+='
```

**The verdict**: build files containing `find_package(Qt5` / `Qt5::` → Qt5-compatible; only `find_package(Qt6` → incompatible.

**Selection priority** (tags beat branches):
1. A tag (such as `v1.2.3` or `qt5-stable`) — an immutable snapshot
2. A release branch (such as `release/1.x`) — usually protected
3. An ordinary branch (such as `qt5`) — may still be changing

**Step C: verify it's a real release**

| Criterion | A real release | Debug/experimental |
|-----------|:--------------:|:------------------:|
| Naming | `release-*`, `stable-*`, `v1.2.3` | `test-*`, `wip-*`, `dev-xxx` |
| Commit history | Ongoing commits | Abandoned after 1–2 commits |
| README/CHANGELOG | Has release notes | No notes, or marked "experimental" |
| CI/CD | Has a passing build badge | No build record |
| Relationship to the main branch | Forked from or merged into main | An orphan branch |

Meeting ≥3 of the "real release" criteria → ✅ adopt it; fewer than 3 → ❌ don't.

**Step D: switch and re-assess**

1. `git checkout <the chosen tag or branch>`
2. Confirm HEAD with `git log --oneline -1`
3. Verify the build files reference Qt5 (with no `Qt6::`)
4. **Re-run §3.0–§3.6** (the code has changed, so the dependency information is stale)

### Qt version adaptation principles

Use the `QT_VERSION_CHECK` macro for conditional compilation to keep Qt5/Qt6 compatibility:

```cpp
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
    // The Qt6 code (leave it exactly as-is)
    QPromise<int> promise;
#else
    // A Qt5 replacement implementation (newly added, used only for the HarmonyOS build)
    QFuture<int> future = QtConcurrent::run([]() { return 42; });
#endif
```

**Principles**:
- Don't affect the existing Qt6 code
- Only add branches for Qt5
- Only test the Qt5 HarmonyOS build

### 3.2 Inventory the Qt module dependencies

**How to inventory them** (in priority order):
1. Analyze `find_package(Qt...)` / `target_link_libraries(Qt...)` in CMakeLists.txt
2. Analyze the `QT +=` lines in .pro files
3. grep the source for `#include <QXxx>` and infer the modules
4. The build files are authoritative

**Output format** (appended to `qt_env.md`):

| Qt module | Evidence | HarmonyOS status | Notes |
|-----------|----------|:---------------:|-------|
| QtCore | `find_package(Qt5 COMPONENTS Core)` | ☑ | — |
| QtWidgets | `#include <QWidget>` | ☑ | — |
| QtPrintSupport | `QT += printsupport` | ☐ | Needs degrading |

See: [[semantic-qt-harmonyos-modules]]

### 3.3 Direct system capability calls

Determine whether the project bypasses Qt and calls OS APIs directly. If so, assess the OHOS alternatives.

See: [[semantic-qt-harmonyos-api]]

### 3.4 Third-party library dependencies

Record every third-party library:
- Name, purpose, version
- How it's integrated (built from source / a prebuilt package / installed system-wide)
- Whether it supports OHOS cross-compilation

### 3.5 The build system and build configuration

- The build system type (qmake / CMake / mixed)
- Build options, macro definitions, conditional compilation branches
- Platform-specific build scripts and toolchain files

See: [[semantic-qt-harmonyos-build]]

### 3.6 Environment readiness comparison

Compare the environment you have against the dependencies inventoried in 3.1–3.5, item by item:
- ☑ Ready
- ☐ Missing (record why)
- ? Unsure (ask the user)

**Append to `qt_env.md`**:

| Category | Dependency | Status | Source/path | Notes |
|----------|------------|:------:|-------------|-------|
| Qt module | QtCore | ☑ | `<path>/libQt5Core.so` | — |
| Third-party library | zlib | ☑ | Ships with the system | — |
| Toolchain | OHOS NDK | ☑ | `<SDK path>` | — |

**Confirm with the user**:
1. The environment is ready → move on to the build step
2. There are uncertain items → discuss them one by one
3. Something is missing and can't be obtained automatically → provide the help request (what's missing, the steps to take, the expected result)
4. If it's ultimately confirmed that the conditions can't be met → append that conclusion to `qt_env.md`

---

## Build orchestration process

### 4.1 Knowledge base preparation

Ask the user whether they already have a `compile_fix_pro.md`:
- They do → record its path
- They don't → create one and write in the example format

### 4.2 Pre-build preparation

**Prerequisite**: every necessary dependency from §3 is ☑ or has a documented degraded alternative ⚠️

**Steps**:
1. Review `qt_env.md` and confirm the dependency statuses are unambiguous
2. Invoke the `qt-harmonyos-porting` skill for code adaptation:
   - Scan for platform-specific APIs (QProcess, QDesktopServices, window management, file operations)
   - Apply the replacements per api-mapping / code-patterns / window-model / lifecycle
   - Check platform-limitations.md and module-status.md
3. Invoke the `create-qt-app` skill to create the project structure
4. When you hit an error:
   - Check `compile_fix_pro.md` first
   - Identify which stage the error is in (preprocessing / compilation / linking / packaging)
   - Fixed it → record it in the knowledge base
   - Couldn't fix it → ask the user for help
5. Create `qt_compile_plan.md` with the detailed build steps
6. **Only after showing it to the user for confirmation may you proceed to 4.3**

### 4.3 Run the build

**The error retry policy**:
- At most **3 attempts** per error
- Each attempt must use a **different approach**
- Beyond 3 attempts → stop, assemble the error context and what you've tried, and ask the user for help

**Every time you hit an error**:
1. Check `compile_fix_pro.md` first
2. Identify which stage it's in
3. Analyze the cause
4. Fixed it → capture it; couldn't fix it → ask for help

### 4.4 Build completion confirmation

**The verification checklist** (everything must pass before marking it complete):

| Item | How to verify | Expected result |
|------|---------------|-----------------|
| The build has no errors | The dual cross-check protocol | Both rounds pass |
| HAP installation and launch have no errors | The dual cross-check protocol | Both rounds pass |
| The application library artifact exists | `ls entry/libs/arm64-v8a/lib<AppName>.so` | The file exists |
| The Qt core libraries are deployed | `ls entry/libs/arm64-v8a/libQt5Core.so` | The file exists |
| The platform plugin is deployed | `ls entry/libs/arm64-v8a/libqohos.so` | The file exists |
| The style library is deployed | `ls entry/libs/arm64-v8a/styles/libqohosstyle.so` | The file exists |

---

## The dual cross-check protocol

This applies to "the build has no errors" and "HAP installation and launch have no errors". Each item must go through both rounds; failing either round means ❌.

### Round one: automated AI review (log review)

| Step | Action | Criterion |
|:----:|--------|-----------|
| 1 | Get the complete build/install log (not truncated) | The log was obtained successfully |
| 2 | Search for failure keywords: `ERROR`, `FAILED`, `fatal`, `undefined reference`, `cannot find`, `No such file`, `BUILD FAILED`, `Install Failed`, `crash`, `SIGSEGV`, `SIGABRT` | Record every hit |
| 3 | Rule out false positives: is it in a comment/document, a known warning, or an internal dependency-library log that doesn't affect the artifacts? | Keep only the real errors |
| 4 | Output the review conclusion | "No real errors" or "Found N errors: \<list\>" |

⚠️ **You must search for each keyword individually** — don't skip it with "I glanced at the log and didn't see a problem".

### Round two: user confirmation (a human cross-check)

**Regardless of round one's result, you must show the user the full review conclusion and ask explicitly.**

| Round one's result | What to show | The question |
|--------------------|--------------|--------------|
| No real errors | A summary of the log review | "Please confirm: on your side, did the build/run also show no errors at all?" |
| Errors found | The specific error list | "These are the errors I found — is the list complete? Are you seeing any others on your side?" |

**How to interpret the user's reply**:

| The user's reply | Verdict |
|------------------|---------|
| An explicit "no errors" / "confirmed clean" | ✅ Pass |
| They report new errors | ❌ Fail — fold them into the fix process |
| A vague reply ("should be fine") | ⚠️ Not a pass — follow up for an explicit confirmation |
| No reply | ⏸️ Waiting — you must not assume it passed |

### The two-round cross-check matrix

| Round one (AI) | Round two (user) | Final verdict | Next action |
|:--------------:|:----------------:|:-------------:|-------------|
| ✅ No errors | ✅ Confirms no errors | ☑ Pass | Mark it complete |
| ✅ No errors | ❌ Reports errors | ❌ Fail | The AI has a blind spot; the user is authoritative — go fix it |
| ❌ Errors found | ✅ Confirms those are all | ❌ Fail | Fix the listed errors and re-run the cross-check |
| ❌ Errors found | ❌ Adds more errors | ❌ Fail | Merge into a complete error list, fix, and re-run the cross-check |

🔑 **The core principle: only ✅ + ✅ counts as a pass.**

Once everything is ☑:
- Update `qt_compile_plan.md` to mark the build status complete
- Update §4.4 in `qt_env.md`'s process progress table to ☑
- Failed → handle it per the gate-failure iron rule

---

## Summary document output

**Prerequisite**: every item in §4.4's verification checklist is ☑

**Filename**: `qt_summary_<project>.md`

**Document structure**:

```markdown
# <project> HarmonyOS porting build summary

> Generated: YYYY-MM-DD HH:mm

## 1. Project overview
| Item | Details |
|------|---------|
| Original project | <project> <version> — <what it does> |
| Target platform | OpenHarmony (OHOS) |
| Qt version | Qt 5.15.16 (the harmonyos branch) |
| Glue template | `<QT_SRC>/qtbase/src/harmonyos/templates` (bundled with the source) |
| Build tools | DevEco MCP + CMake + Hvigor |
| Target artifact | `entry-default-signed.hap` |

## 2. Feature trimming and degradation list
### 2.1 Qt modules dropped
| Module dropped | Original purpose | Why it was dropped | Degraded alternative | Scope of impact |

### 2.2 Third-party libraries dropped
| Library dropped | Original purpose | Why it was dropped | Alternative | Scope of impact |

### 2.3 System capabilities degraded
| Original syscall/capability | How it was degraded | Functional impact |

### 2.4 Feature flags and conditional compilation
| Feature/macro disabled | Files involved | Why it was disabled |

## 3. Record of code changes
| File changed | Type of change | Summary | Reason |

## 4. Build problem fix summary
| Problem title | Where it occurred | Root cause | Fix |

## 5. Outstanding problems and known limitations
| Problem | Severity | Status | Notes |

## 6. Reproducibility information
| Item | Value |
|------|-------|
| OHOS SDK version | |
| NDK version | |
| DevEco Studio version | |
| Path to the Qt build artifacts | |
| Build system | |
| Host OS | |
```

**Data source mapping**:

| Document section | Primary source | Supplementary source |
|------------------|----------------|----------------------|
| §1 Project overview | `qt_env.md` §3.0, §2 | §1 Requirements discussion |
| §2.1 Qt modules dropped | The ☐ items in `qt_env.md` §3.2 | `qt_compile_plan.md` |
| §2.2 Third-party libraries dropped | The ☐ items in `qt_env.md` §3.4 | `compile_fix_pro.md` |
| §2.3 System capabilities degraded | `qt_env.md` §3.3 | `qt_compile_plan.md` |
| §2.4 Feature flags | `qt_compile_plan.md` | The record of code changes |
| §3 Code changes | `compile_fix_pro.md` | `qt_compile_plan.md` |
| §4 Fix summary | `compile_fix_pro.md` | — |
| §5 Outstanding problems | The platform limitation entries in `qt_env.md` | `qt_compile_plan.md` |
| §6 Reproducibility | `qt_env.md` §3.5, §3.6 | System environment detection |

**The generation process**:
1. Determine the project name → derive the filename
2. Read `qt_env.md` and extract data per the mapping table
3. Read `qt_compile_plan.md` and fill in the build plan
4. Read `compile_fix_pro.md` and extract the fix records
5. Assemble it per the template, **keeping the heading for any section with no data and noting "this project had no trimming of this kind"**
6. Show it to the user for confirmation, then mark §4.5 ☑

⚠️ **Never fill anything in from memory or speculation.** Every data point must have an original source in `qt_env.md`, `qt_compile_plan.md`, or `compile_fix_pro.md`. If you can't find a source, mark it "⚠️ To be filled in — the original record is missing".

---

## References

- [[semantic-qt-harmonyos-build]] — CMake/qmake configuration and the build process
- [[semantic-qt-harmonyos-overview]] — An overview of the OHOS platform and the background to porting Qt
- [[semantic-qt-harmonyos-platform-limits]] — OHOS platform limitations and degradation strategies
- [[semantic-qt-harmonyos-modules]] — Qt module porting status on OHOS
- [[semantic-qt-harmonyos-api]] — The mapping from Qt APIs to OHOS
