---
id: procedural-qt-app-harmonyos-completion
type: procedural
domain: workflow
tags: [workflow, qt, harmonyos, completion, functional-test, test-case, source-scan, human-test-loop, app-harmonyos]
created: 2026-07-16
updated: 2026-08-12
status: active
audience: public
refs: [procedural-qt-ohos-run-test, procedural-qt-app-harmonyos-migration, procedural-framework-fix-verification, procedural-framework-issue-analysis, procedural-demo-generation, semantic-qt-ohos-project-analyzer-workflow, semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-api-mapping]
summary: >
  The application-polish workflow for HarmonyOS porting (a feature-level test case loop, four phases): scan the application source to identify core features → generate 10 core test cases (an AI source scan + human review) →
  loop through manual testing / reporting problems / fixing / regression → close once all 10 cases pass. Prerequisite: the run test (qt-ohos-run-test) passes.
  Includes the standard trio (an ASCII loop diagram / the loop exit condition ✅ all 10 cases pass / gate checks ⚠️).
leader_summary: >
  Advances an application from "it runs" to "every core feature is verified", using an AI source scan to generate 10 core cases plus a manual test-report-fix loop, and capturing feature-level test assets.
impact: [Migration efficiency, Framework support]
deliverables: [workflow, test case list, captured problems]
evidence: [The <APP_NAME> polish test report, <WORKLOG>]
---

# The application-polish workflow for HarmonyOS porting

> **When it applies**: a Qt application ported to HarmonyOS already runs thanks to the run test ([[qt-ohos-run-test]]), and now needs an end-to-end verification loop over its core features (not just "it runs", but "every core feature passes").
> **Prerequisites**: ① all seven phases of the run-test workflow pass (process alive + rendering + lifecycle + windows + input + platform limitation regression) ② the application source is readable ③ a real device/emulator is available.
> **Expected effort**: 2–6 hours (depending on application complexity and defect density).

---

## When to use this

- The application has passed [[qt-ohos-run-test]] (the run test) and needs feature-level verification
- The customer/business side wants "every core feature verified", not just "it launches"
- You want to capture functional test assets after a migration (the list of 10 core cases is reusable)

> **The boundary with the run test**: run-test focuses on "getting the application running on a real device" (deployment/launch/rendering/crashes); this workflow focuses on "the core features behave correctly" (verifying expectations by following test case steps). run-test is a prerequisite for this workflow.

---

## Process overview

```
§1 Scan the application source → §2 Generate 10 core cases → §3 The manual test/report/fix loop → §4 Close out (all 10 pass)
                                                │
                                                └─ Loop exit condition: all 10 cases ✅
```

> **📋 TODO sync point**: this is a multi-step workflow — update the "Progress" column for this task in `<LOCAL_TODO>` at each phase transition; when the task completes, move it to "✅ Completed" in the same session and append to `<WORKLOG>`.

---

## Phase 1: scan the application source

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase 1 in progress: scanning the application source`

### 1.1 Locate the source and identify the entry point

- Locate the application source root (`OhosExampleApp/` + `main.cpp` + the business source)
- Identify the entry chain: the `extern "C" int main()` shim → QApplication → main window construction
- See [[qt-ohos-project-analyzer-workflow]] (the project analysis workflow, with dual verification)

### 1.2 Scan for core features

Use grep and source reading to identify the core features, by priority:

| Priority | Feature type | grep/identification keywords |
|----------|--------------|------------------------------|
| P0 | Main window and menus | `QMainWindow`/`QMenuBar`/`QToolBar`/`addAction` |
| P0 | Core business interactions | `QPushButton::clicked`/`QDialog`/`QInputDialog`/`exec()` |
| P1 | File operations | `QFileDialog`/`QFile`/`save`/`open` |
| P1 | Data models | `QTableView`/`QListView`/`QSql*Model` |
| P2 | Settings/configuration | `QSettings`/`QComboBox`/`QCheckBox` |
| P2 | Platform-specific APIs | `QProcess` (depends on the scenario: keep it when headless; switch to startAppProcess or startAbility when there's a UI) / `chmod`/`symlink` (see [[qt-harmonyos-api-mapping]]) |

> **⚠️ Meta-lesson**: while scanning, identify platform-specific APIs (QProcess/chmod/symlink and so on); these need replacing on HarmonyOS (see [[qt-harmonyos-golden-rules]] P1-P5 + [[qt-harmonyos-api-mapping]]), so include them in the test cases as focus areas.

### Loop exit conditions (all must hold)

- ✅ The entry chain is mapped out (main → QApp → main window)
- ✅ 15–20 candidate core features identified (with platform-specific APIs flagged)
- ✅ Features relating to platform limitations / iron rules are flagged (see [[qt-harmonyos-golden-rules]])

### Outputs

- A list of core features (15–20 items, labeled P0/P1/P2 with platform-specific markers)

> **⚠️ Gate check**: **do not generate test cases** before the source scan is complete (cases with no grounding in the source are pure guesswork).

---

## Phase 2: generate 10 core test cases

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase 2 in progress: generating the 10 core test cases`

### 2.1 The AI drafts the cases

Based on the feature list from phase 1, have the AI/agent draft 10 core test cases (P0 first, covering the main paths).

**Case template**:

```
### Case TC-NN: <case name>
- **Feature**: <the corresponding source feature>
- **Prerequisites**: <the run test passes + a specific initial state>
- **Steps**:
  1. <step 1>
  2. <step 2>
  3. <step 3>
- **Expected result**: <the observable correct behavior>
- **Actual result**: <to be filled in by a human: pass/fail + what happened>
- **Status**: <to be filled in: ✅pass / ❌fail / 🟡flaky>
```

### 2.2 Human review and finalization

- A human reviews the 10 draft cases: do they cover the main paths? Are the steps executable? Are the expectations observable?
- Adjust: merge/split/add, so that the 10 cases cover the application's 10 most core features
- Finalize the test case list (a table + the details of each case)

**The 10-case table** (a skeleton; fill it in for your application):

| TC# | Case name | Priority | Status |
|-----|-----------|:--------:|:------:|
| TC-01 | Main window launches and displays | P0 | 🟡 to test |
| TC-02 | Menu/toolbar operations | P0 | 🟡 to test |
| TC-03 | The core business dialog | P0 | 🟡 to test |
| ... | ... | ... | ... |
| TC-10 | The core business end-to-end flow | P0 | 🟡 to test |

> See [[framework-fix-verification]] for the conventions on writing verification cases (one case per problem, reusing Qt examples, the README template).

### Loop exit conditions (all must hold)

- ✅ The 10 core test cases are written (with steps + expectations)
- ✅ Human review passed (main paths covered, steps executable, expectations observable)
- ✅ The case list is finalized as a document

### Outputs

- The list of 10 core test cases (a table + a details template per case)

> **⚠️ Gate check**: **do not start manual testing** before the cases are finalized (testing without a list is just random poking).

---

## Phase 3: the manual test / report / fix loop ★ the core

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase 3 in progress: the manual test loop (X/10 passing)`

> **This phase is a loop; you can only move to phase 4 once all 10 cases pass.**

```
┌──────────────────────────────────────────────────────────┐
│  The test loop begins                                     │
│  ↓                                                       │
│  3.1 Take the next untested case (or re-run a failed one) │
│  ↓                                                       │
│  3.2 Operate the real device manually, following the steps│
│  ↓                                                       │
│  3.3 Actual result == expected?                           │
│  ├─ Yes → mark ✅pass → that case is closed              │
│  └─ No ↓                                                 │
│  3.4 Report the problem (symptom + screenshot + hilog +   │
│      stack frames)                                        │
│  ↓                                                       │
│  3.5 Find the root cause (see [[qt-ohos-run-test]] §5     │
│      crash analysis + [[framework-issue-analysis]] call   │
│      chains)                                              │
│  ↓                                                       │
│  3.6 Fix the source (application layer / API replacement /│
│      working around a platform limitation)                │
│  ↓                                                       │
│  3.7 Regress: rebuild + install + retest that case → 3.3  │
│  ↓                                                       │
│  All 10 cases ✅pass?                                     │
│  ├─ No → take the next case → back to 3.1                │
│  └─ Yes → exit the loop ✓                                │
│                                                           │
│  Exit condition: all 10 core cases ✅pass                │
└──────────────────────────────────────────────────────────┘
```

### 3.1-3.2 Execute the case

- Follow the case's steps on the device/emulator (`hdc shell aa start` + manual interaction)
- Record the actual behavior with screenshots/hilog

### 3.3-3.4 Judging results and reporting

| Actual vs. expected | Status | Action |
|---------------------|--------|--------|
| They match | ✅pass | The case is closed; take the next one |
| They don't match | ❌fail | Report the problem (symptom + screenshot + hilog + stack frames) and go to 3.5 |
| Partially matching / unstable | 🟡flaky | Reproduce several times to confirm whether it's a real fail or a timing issue |

### 3.5-3.6 Diagnosis and fixing

- Crashes/exceptions → [[qt-ohos-run-test]] §5 the crash analysis loop + [[framework-issue-analysis]] call chains
- A platform limitation triggered → [[qt-harmonyos-golden-rules]] P1-P5 + the replacements in [[qt-harmonyos-api-mapping]]
- An application-layer logic bug → fix the source
- After fixing, regress (3.7): rebuild + install + retest that case

### Loop exit conditions (all must hold)

- ✅ **All** 10 core cases ✅pass (not 9/10 — all of them)
- ✅ Every failing case's fix has been regression-verified (not just claimed fixed)
- ✅ Flaky cases have been reproduced several times and confirmed to pass consistently

### Outputs

- A test report (pass/fail for all 10 cases + screenshot comparisons)
- A fix list (the source changes per case + the associated problem records)

> **⚠️ Gate check**: **do not proceed to the phase-4 close-out** until all 10 cases pass. A workflow with unresolved failures is incomplete.

---

## Phase 4: close out and capture

> **📋 TODO sync point**: update `<LOCAL_TODO>` — move this task from "📌 In progress" to "✅ Completed", filling in the completion date and a summary of the results

### 4.1 The test report

| TC# | Case name | Final status | Fix iterations | Associated problem |
|-----|-----------|:------------:|:--------------:|--------------------|
| TC-01..10 | ... | ✅ | N | ... |

### 4.2 Capture the problems

- New errors found while fixing → `problems/` (using `_templates/qt-problem.md`) + run `bash _scripts/kb-regen-indexes.sh` to regenerate `problems/_lookup.md` and the other derived indexes
- New API differences → [[qt-harmonyos-api-mapping]]
- New platform limitations → `qt-harmonyos-platform-limits` (captured internally)

### 4.3 Workflow close-out confirmation

- [ ] All 10 core cases ✅pass
- [ ] The test report is written
- [ ] Problems are captured in `problems/` + the indexes are in sync
- [ ] `<LOCAL_TODO>` moved to "✅ Completed"
- [ ] A record appended to `<WORKLOG>`
- [ ] A git commit has been made

---

## Checklist

- [ ] Prerequisite: the run test ([[qt-ohos-run-test]]) passes
- [ ] Phase 1: the source scan is complete, with a list of 15–20 features
- [ ] Phase 2: the 10 core cases are generated, human-reviewed, and finalized
- [ ] Phase 3: all 10 cases ✅pass (including regression on every fix)
- [ ] Phase 4: the test report + captured problems + index sync

---

## Common problem patterns

| Pattern | What you see | Where to look | Related |
|---------|--------------|---------------|---------|
| Case fails with a crash | An action triggers SIGSEGV/SIGABRT | [[qt-ohos-run-test]] §5 crash analysis | run-test |
| Case fails on a platform limitation | chmod/symlink/dlopen fails | [[qt-harmonyos-golden-rules]] P1-P5 | golden-rules |
| Case fails on an unavailable API | QtWebEngine and others are absent on HarmonyOS; QProcess for a UI child process must become startAppProcess/startAbility | [[qt-harmonyos-api-mapping]] §1 | api-mapping |
| A flaky case | Timing/race conditions cause intermittent failures | Reproduce several times + [[framework-issue-analysis]] call chains | framework-issue-analysis |
| A case can't be executed | A prerequisite feature isn't implemented / is blocked | Mark it blocked and go back to [[qt-ohos-run-test]] to fill the gap, or back to migration | run-test |

---

## Supply chain

> See the workflow supply chain, §Application porting (this workflow is the feature-level polish stage after migration)

| Dimension | Details |
|-----------|---------|
| **Upstream source** | An application that completed migration and passed the qt-ohos-run-test run test |
| **Upstream input** | A HarmonyOS application that runs + the application source + a real device/emulator |
| **Downstream recipients** | Commercial Qt customers / internal use (a deliverable application with verified core features) |
| **Deliverables** | The list of 10 core cases + the test report + captured problems |
| **Deliverable path** | No fixed directory (the test assets live with the application project) |
| **Routing rules** | If you find a framework bug → the framework-issue-analysis workflow; for a known problem → check `_lookup` |

---

## Related context

- [[qt-ohos-run-test]] — The run-test workflow (a prerequisite; it must run before you can polish it)
- [[qt-app-harmonyos-migration]] — HarmonyOS migration (the stage before polishing)
- [[framework-fix-verification]] — A reference for verification case conventions
- [[framework-issue-analysis]] — Framework issue analysis (tracing call chains for failing cases)
- [[qt-ohos-project-analyzer-workflow]] — Project analysis (the source scan)
- [[qt-harmonyos-golden-rules]] — The 35 iron rules (P1-P5 platform limitation verification)
- [[qt-harmonyos-api-mapping]] — API replacements (the source scan identifies which APIs to test)
- [[demo-generation]] — Demo generation (case projects can reuse the demo template)
- The workflow supply chain — An overview of the workflow supply chain

---

## Content sources

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | The methodology for generating 10 core cases, the manual test-report-fix loop, and the case template |
| 🔍 Framework source | The source scan keywords (QMainWindow/QDialog/QProcess and so on) |
| 📖 Official documentation | Qt testing practice, HarmonyOS functional verification |
| 📦 KB workflows | run-test (the prerequisite) / framework-fix-verification (case conventions) / framework-issue-analysis (diagnosis) |

### Qt framework versions (validation baseline)

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |

---

## References

- A workflow developed from hands-on experience polishing Qt HarmonyOS ports
- The methodology draws on Qt's internal QA process plus this library's run-test/framework-fix-verification workflows
