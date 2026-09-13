---
id: procedural-framework-issue-analysis
type: procedural
domain: workflow
tags: [workflow, qt, harmonyos, debugging, framework, analysis, logging, upstream-submission]
created: 2026-06-02
updated: 2026-08-14
status: active
audience: public
refs: [semantic-qt-harmonyos-api,semantic-qt-harmonyos-build,semantic-qt-harmonyos-overview]
summary: >
  The framework-internal issue analysis workflow (a four-phase loop): generate a reproduction demo → iterate on build fixes → localize the problem (via logs) → root cause analysis (framework code call chains) → verify the system interface → package and submit an upstream issue (the workflow's final step).
  Phase four is the closing point: produce a clean patch, prepare the issue write-up, output a pure-Qt reproduction demo, and update the knowledge base index.
  Applies to analyzing Qt framework bugs on HarmonyOS.
---

# Framework-internal issue analysis

> When you receive a Qt for HarmonyOS bug report or discover odd behavior, follow this process for systematic analysis and localization.

---

## When to use this

- You receive a bug report or problem feedback
- You discover odd Qt behavior on HarmonyOS yourself
- A problem a developer submitted needs internal investigation

---

## Phase 1: establish the symptom (an iterative loop)

> **📋 TODO sync point**: update the "Progress" column for this task in `<LOCAL_TODO>` → `Phase 1 done: minimal demo reproduces the issue`

> **This phase is a loop; you can only move to phase 2 once you have a minimal demo that reproduces the problem reliably.**

```
┌──────────────────────────────────────────────────────────┐
│  The loop begins                                          │
│  ↓                                                       │
│  1.1 Gather information about the problem                 │
│  ↓                                                       │
│  1.2 Try to reproduce it / simplify the code              │
│  ↓                                                       │
│  1.3 Does it build?                                       │
│  ├─ No → analyze the build errors → fix → back to 1.3    │
│  └─ Yes ↓                                                │
│  1.4 Does it reproduce?                                   │
│  ├─ No → adjust the conditions / gather more info → 1.1  │
│  └─ Yes → 1.5 Can it be simplified further?              │
│           ├─ Yes → keep simplifying → back to 1.2        │
│           └─ No → exit the loop ✓                        │
│                                                           │
│  Exit condition: the minimal demo builds and reproduces   │
│  the problem reliably                                     │
└──────────────────────────────────────────────────────────┘
```

### 1.1 Gather information about the problem

| What to gather | Description |
|----------------|-------------|
| The problem description | Expected behavior vs. actual behavior |
| Reproduction steps | The sequence of actions and the trigger conditions |
| Environment information | The Qt version, the OHOS SDK version, the device/emulator model |
| Scope of impact | Which modules/features are affected |
| The original code | The complete project or the problematic snippet the user provided |

### 1.2 Try to reproduce it / simplify the code

**Create the demo project**:

> **⚠️ The reproduction demo must be created from the glue-code template used for HarmonyOS project migration; creating the directories by hand is forbidden.**
> The template path is `OHOS_TEMPLATE_SRC` in `ENV.md` (i.e. `<QT_SRC>/qtbase/src/harmonyos/templates`, bundled with the source).

```bash
# Copy the bundled template from the Qt source tree into the demo directory (both the 5.15 and 5.12 trees have it, with identical content)
cp -r <QT5_15_SRC>/qtbase/src/harmonyos/templates/. "<demo target directory>/"
```

After extracting it, put your Qt C++ source into `entry/src/main/cpp/` and configure `CMakeLists.txt`, `QtAppConstants.ets`, and `build-profile.json5` exactly as in the migration workflow.

> See [[qt-app-harmonyos-migration]] phase 1.2 and [[qt-harmonyos-project-structure]] for details.

**Make only one simplification per iteration**:
1. Prefer verifying with an existing Qt example (from Qt's own examples directory)
2. Remove UI components, business logic, and resource files unrelated to the problem
3. Remove third-party dependencies, replacing them with minimal code
4. Simplify the data structures and the initialization flow
5. Keep the minimal code path that triggers the problem

### 1.3 Build verification (an iterative fix loop)

> **⚠️ Gate check**: the demo must build before you move on to reproduction verification. A demo that doesn't build is worthless.

```
┌──────────────────────────────────────────────────────────┐
│  The build loop begins                                    │
│  ↓                                                       │
│  Run the build                                            │
│  ↓                                                       │
│  Did it succeed?                                          │
│  ├─ No ↓                                                 │
│  │  Analyze the build error message                       │
│  │  ↓                                                     │
│  │  Find the root cause (a missing header/link library/   │
│  │  syntax/configuration/CMake issue...)                  │
│  │  ↓                                                     │
│  │  Fix it → back to the top of the loop                 │
│  └─ Yes → exit the build loop ✓                          │
│                                                           │
│  Exit condition: the demo builds and produces a           │
│  deployable artifact                                      │
└──────────────────────────────────────────────────────────┘
```

**Common build errors and where to look**:

| Error type | A typical message | Where to look |
|------------|-------------------|---------------|
| CMake can't find Qt | `find_package(Qt5 ... NOT FOUND)` | Check whether `CMAKE_PREFIX_PATH` points at the Qt OHOS SDK |
| A missing header | `'QMainWindow' file not found` | A missing `find_package` component or `target_link_libraries` entry |
| A link error | `undefined reference to ...` | Add the missing link libraries (`QOhosPlatformIntegrationPlugin` and so on) |
| find_package during cross-compilation | `find_package` finds host libraries instead of target ones | Check the `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` setting |
| The HarmonyOS template is missing | `QtAppConstants.ets` not found | Confirm you copied it correctly from the bundled template (`qtbase/src/harmonyos/templates`) |
| A library name mismatch | Loading fails at runtime | The `add_library` name in `CMakeLists.txt` must match `APP_LIBRARY_NAME` in `QtAppConstants.ets` |

**Fix principles**:
- Change one variable per fix so you can tell whether it worked
- Record the error message and solution from each round (you can capture them in the `problems/` knowledge base later)
- If it still doesn't build after 5 consecutive rounds, pause and re-examine the project configuration (the template version may not match the SDK)

### 1.4 Does it reproduce?

- **No** → the information is incomplete or a condition is missing; go back to 1.1 to gather more, or adjust the conditions:
  - Check for environment differences (Qt version, SDK version, device model)
  - Check the trigger conditions (a specific action sequence, timing, data state)
  - Check dependencies (a specific module, configuration, or permission)
  - Confirm the missing context with the user
- **Yes** → move to 1.5 and decide whether it's already minimal

### 1.5 Can it be simplified further?

Criteria:
- Is there still code unrelated to the problem you could remove?
- Could you use simpler APIs or data structures?
- Could you reduce the number of modules it depends on?
- Could there be fewer reproduction steps (the target is 3 or fewer)?

**It can be simplified** → back to 1.2 to keep simplifying
**It's already minimal** → exit the loop

### Loop exit conditions (all must hold)

- ✅ The minimal demo **reproduces the problem reliably** (not intermittently)
- ✅ The demo **builds and runs standalone** (with no dependency on the rest of the original project)
- ✅ The reproduction takes **3 steps or fewer**
- ✅ All code unrelated to the problem has been removed

### Handling loop failure (still not reproducing after 3 rounds)

- Record the simplification paths you tried and why they failed
- Mark it "can't reproduce" and set it aside for now
- Wait for the user to supply more information or new reproduction conditions

### Outputs (once the loop ends)

- The minimal reproduction demo (code + build artifacts)
- A reproduction steps document (3 steps or fewer)
- Expected vs. actual screenshots/logs
- A record of the simplification (how you got from the original code to the minimal demo)

> **⚠️ Gate check**: **do not proceed to phase 2** until phase 1's exit conditions are met. Localization without a reliable reproduction is meaningless.

---

## Phase 2: localize the problem

> **📋 TODO sync point**: update the "Progress" column for this task in `<LOCAL_TODO>` → `Phase 2 done: problem localized`

### 2.1 Analyze the Qt framework code's call flow

**The goal**: follow the call chain through the Qt source to the exact point where the problem occurs.

**The Qt 5.15 source**: `<LOCAL_PATH>`
**The Qt 5.12 source**: `<LOCAL_PATH>`

**Steps**:
1. Start from the demo's entry API and trace its implementation through the Qt source
2. Focus on the `src/plugins/platforms/ohos/` directory (the QPA plugin layer)
3. Map out the chain: `application call → the Qt wrapper → the QPA plugin → the system interface`
4. Note the parameter conversions and state changes at each step

**Key directories** (the OHOS QPA plugin):
```
src/plugins/platforms/ohos/
├── qohosintegration.cpp      # The platform integration entry point
├── qohoswindow.cpp           # Window management
├── qohosbackingstore.cpp     # The rendering backend
├── qohosinput.cpp            # Input events
└── ...
```

### 2.2 Add logging inside the framework to localize the problem

**The logging strategy**:
```cpp
// Add logs on the key paths in the QPA plugin layer
qDebug() << "[OHOS] functionName" << "param=" << param << "result=" << result;

// Add logs before and after the system interface call
qDebug() << "[OHOS] before OH_NativeXxx call, param:" << value;
auto ret = OH_NativeXxx(param);
qDebug() << "[OHOS] after OH_NativeXxx call, ret:" << ret;
```

**Logging conventions**:
- Use a consistent `[OHOS]` prefix so it's easy to filter
- Record the function name, key parameters, and return values
- Log which branch was taken at conditional branches
- Make sure the logging itself doesn't affect the execution logic (avoid adding sleeps at timing-critical points)

**Viewing the logs**:
```bash
hdc shell hilog | grep "\[OHOS\]"
```

### 2.3 Verify the system interface's behavior

**The goal**: confirm whether the problem is caused by the system interface misbehaving.

**How**:
1. Log the system interface's input parameters and return values
2. Compare them against the interface's documented behavior
3. If the system interface returns something anomalous, write a separate test to verify it (bypassing Qt and calling the N-API / OHOS system interface directly)

**Criteria**:

| Situation | Conclusion | Next |
|-----------|------------|------|
| The system interface behaves correctly but Qt misbehaves | A Qt framework problem | Fix the Qt code |
| The system interface returns something anomalous | A system interface problem | Record it and report it to Huawei |
| The system interface returns normally but the semantics don't match the docs | A system implementation bug | Confirm against the official documentation and report it |

---

## Phase 3: confirm the root cause

> **📋 TODO sync point**: update the "Progress" column for this task in `<LOCAL_TODO>` → `Phase 3 done: root cause analyzed`

### 3.1 Compare against the official interface documentation

- Check the official HarmonyOS documentation for the interface's expected behavior: https://developer.huawei.com/consumer/cn/doc/
- Pay particular attention to: interface version compatibility, known limitations, deprecated APIs
- If the documentation doesn't match the actual behavior, record the discrepancy

### 3.2 Write up the analysis conclusion

**The conclusion template**:
```
Problem: [a brief description]
Root cause: [the specific cause, down to the line of code]
Attribution: the Qt framework / the system interface / the application layer
Suggested fix: [an outline of the approach]
Related code: [file:line]
```

---

## Phase 4: upstream submission (the workflow's final step)

> **📋 TODO sync point**: update `<LOCAL_TODO>` — move this task from "📌 In progress" to "✅ Completed", filling in the completion date and a summary of the results

> **⚠️ This is the workflow's final closing step.** Once the fix has been verified, you must assemble the results into an upstream submission package and submit it to Tqtc.
> A workflow that isn't closed out this way counts as **incomplete** — even if the bug is fixed and verified, without submitting it upstream
> the fix will be overwritten in the next release and other team members won't know the problem existed.

> Once the problem is fixed and verified, assemble the results into an upstream submission package.

### 4.1 Create the delivery directory

> **⚠️ Iron rule**: deliverables submitted to Tqtc **must include a demo that reproduces the problem**. An issue report without a reproduction demo isn't convincing, and Tqtc may decline to work on it.

Under `${DELIVERABLES_ROOT}/<WORK_DIR>` (see `ENV.md`), create a subdirectory named after the bug (such as `leave-event-fix`) containing the following deliverables:

```
<WORK_DIR>/<bug-name>/
├── ISSUE.md          → The upstream issue write-up (bilingual Chinese/English)
├── patches/          → git patch files (if there's a fix)
│   └── 0001-*.patch
├── demo/             → ★ The reproduction demo (mandatory; never omit it)
│   ├── OHOS demo/    → The complete HarmonyOS project (buildable and deployable to a device)
│   └── qt-repro/     → A pure-Qt reproduction demo (with the OHOS glue removed, buildable on desktop)
└── README.md         → A deliverables overview
```

> **Why a reproduction demo is mandatory**:
> 1. Tqtc's upstream engineers need to be able to reproduce the problem themselves before they'll analyze and fix it
> 2. A text-only description invites misunderstanding; a demo is the only reliable way to reproduce
> 3. Later regression verification depends on that demo too
> 4. If the problem can't be reproduced, you shouldn't file the issue — investigate until it reproduces reliably first

### 4.2 The ISSUE.md format

| Section | Content |
|---------|---------|
| Issue Summary | Component/version/severity/branch/commit/reporter/date |
| Description | The symptom + reproduction steps (bilingual Chinese/English) |
| Root Cause | The root cause analysis (with code references) |
| Fix Strategy | The fix strategy (including an explanation of the design decisions) |
| Files Changed | The table of files involved (file/type of change/notes) |
| Testing | The test scenarios and verification results |

### 4.3 Generate the git patch

```bash
cd <Qt source>/qtbase
git add -A
git diff --cached -- src/plugins/platforms/ohos/ > patches/0001-<description>.patch
git reset HEAD
```

### 4.4 The pure-Qt demo

- Extract the pure Qt C++ code from the OHOS demo
- Remove the OHOS ArkTS glue (ets/, build-profile.json5, and so on)
- Change CMakeLists.txt to an add_executable that builds on desktop
- Have the README explain how to build it on desktop and note that the bug only reproduces on OHOS

### 4.5 Cleaning the patch

> **⚠️ Iron rule**: a git patch must contain only the changes relevant to the current bug fix.
> Before generating the patch, you must exclude unrelated changes on the same branch (tracing logs for other bugs, debug code, experimental features, and so on).

**Steps**:

1. Check the list of changes in the Qt source:
   ```bash
   cd <Qt source>/qtbase
   git diff --stat HEAD
   ```

2. Identify and exclude the unrelated changed files (common cases: `[OHOS-BUG-TRIAGE]` logs for other bugs, `[MDI_RENDER]` tracing, and so on)

3. Generate the patch from only the fix-related files:
   ```bash
   git diff HEAD -- <file1> <file2> ... > patches/0001-<description>.patch
   ```

4. Verify the patch's file list:
   ```bash
   grep "diff --git" patches/0001-*.patch
   ```

### 4.6 Checklist

- [ ] ★ **The reproduction demo is created** (both the OHOS project and the pure-Qt demo build and run)
- [ ] ★ **The pure-Qt demo is generated** and stored at `<INTERNAL_DEMO><bug-name>-qt/`
- [ ] ISSUE.md is created with a bilingual Chinese/English description
- [ ] ISSUE.md includes the reproduction steps (referring to the demo)
- [ ] **The git patch is generated and cleaned**, correctly formatted, and contains only bug-fix-related changes (if there's a fix)
- [ ] The patch was verified with `grep "diff --git"` to contain no unrelated files
- [ ] Every file is in the `<WORK_DIR>/<bug-name>/` directory
- [ ] `<WORK_DIR>/README.md` is updated (the deliverables index table)
- [ ] The <LOCAL_TODO> task is moved from "📌 In progress" to "✅ Completed"
- [ ] A git commit has been made
- [ ] The retrospective is updated (the corresponding file in `episodic/postmortems/`)

### 4.7 Closing the workflow

> **Completing phase four = the workflow is done.** Here's the closing confirmation checklist:

- [ ] **Phase 1**: the minimal reproduction demo builds and reproduces reliably (`<INTERNAL_DEMO><bug-name>/`)
- [ ] **Phase 2**: the call chain is traced and the root cause localized to a specific file:line
- [ ] **Phase 3**: the problem's attribution is established (the Qt framework / the system / the application)
- [ ] **Phase 4**: the deliverables are in `<WORK_DIR>/<bug-name>/` and the patch is cleaned
- [ ] **Knowledge capture**: the retrospective is written into `episodic/postmortems/`
- [ ] **Index sync**: `bash _scripts/kb-regen-indexes.sh` has been run to regenerate `_index/_map.md` and the other derived indexes (if there are new pages), and a git commit has been made

---

## Checklist

- [ ] The minimal reproduction demo **builds**
- [ ] The minimal reproduction demo runs standalone
- [ ] The problem's call chain is fully mapped out
- [ ] The system interface's behavior has been verified through logs
- [ ] The root cause is localized to a specific code location
- [ ] The problem's attribution is established (Qt / the system / the application)
- [ ] The analysis conclusion is recorded
- [ ] The upstream issue write-up is prepared
- [ ] The fix patch is generated
- [ ] The pure-Qt reproduction demo is created

---

## Common problem patterns

| Pattern | What you see | Where to look |
|---------|--------------|---------------|
| The window doesn't display | A black screen / nothing rendered | `qohoswindow.cpp` → XComponent initialization |
| Input doesn't respond | Clicks/touches do nothing | `qohosinput.cpp` → event callback registration |
| A crash | SIGABRT/SIGSEGV | Null pointers / lifecycle timing / resource release |
| Rendering glitches | Corruption/flicker | `qohosbackingstore.cpp` → buffer management |
| An API has no effect | Calling the API does nothing | Check whether the API is implemented on this platform |

---

## Supply chain

| Dimension | Details |
|-----------|---------|
| **Upstream source** | ① Self-driven (framework anomalies found in day-to-day testing/code review) ② Direct feedback from commercial Qt customers ③ The known-issues list before a release |
| **Upstream input** | The bug description, reproduction steps, logs/screenshots, the Qt version and environment details, and the original project code (if available) |
| **Downstream recipients** | **The Qt Company (Tqtc)** framework team |
| **Deliverables** | `<WORK_DIR>/<bug-name>/`: ISSUE.md + patches/ + demo/ + README.md |
| **Deliverable path** | `${DELIVERABLES_ROOT}/<WORK_DIR>` (see `ENV.md`) |
| **Routing rules** | None (this workflow's output *is* the final deliverable, submitted directly upstream) |

---

## Related context

- [[qt-harmonyos-overview]] — Understanding the QPA plugin architecture
- [[qt-harmonyos-build]] — Building (you need to rebuild after adding logging)
- [[qt-harmonyos-api]] — API compatibility differences
- [[qt-harmonyos-platform-limits]] — Known platform limitations (so you don't mistake a known limitation for a bug)
- [[ohos-common-kb/semantic/harmonyos-development-fundamentals|HarmonyOS development fundamentals]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-development-fundamentals.md)) — Using the hdc tool

## Content sources

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | The overall document structure, the methodology, the debugging conventions, the logging practice, the templates, and the checklists |
| 🔍 Framework source | The QPA plugin directory path (src/plugins/platforms/ohos/), the key filenames (qohosintegration.cpp, qohoswindow.cpp, qohosbackingstore.cpp, qohosinput.cpp), and the call chain architecture |
| 📄 Huawei official documentation | The HarmonyOS API documentation reference (developer.huawei.com/consumer/cn/doc/) and the comparison of expected system interface behavior in the decision matrix ([developer.huawei.com](https://developer.huawei.com/consumer/cn/doc/)) |

### Qt framework versions (validation baseline)

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |

## References

- A workflow developed from personal Qt framework debugging experience; no external documentation source
- Parts of the methodology draw on Qt's internal bug analysis process (Gerrit code review + QTBUG tracking)
