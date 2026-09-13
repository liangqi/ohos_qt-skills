---
id: procedural-framework-fix-verification
type: procedural
domain: workflow
tags: [workflow, qt, harmonyos, testing, verification, framework]
created: 2026-06-02
updated: 2026-06-05
status: active
audience: public
refs: [procedural-framework-issue-analysis,semantic-qt-harmonyos-build,semantic-qt-harmonyos-build-run-workflow,semantic-qt-harmonyos-modules]
summary: >
  The framework fix verification workflow: obtain the verification checklist → write the verification project → verify manually → record the results.
  Used to systematically verify that Qt framework bug fixes work.
---

# Framework fix verification

> Once a Qt for HarmonyOS bug has been fixed, follow this process to systematically verify that the fix works and hasn't introduced new problems.

---

## When to use this

- You received a fix verification checklist (usually from the team or from Huawei)
- You need to verify a fix in some Qt module/feature
- Regression verification before a release

---

## Phase 1: obtain the verification checklist

> **📋 TODO sync point**: update the "Progress" column for this task in `<LOCAL_TODO>` → `Phase 1 done: verification checklist obtained`

### 1.1 Confirm the scope

| Item to confirm | Description |
|-----------------|-------------|
| List of fixed problems | The QTBUG number / internal number for each |
| Qt modules involved | QtCore / QtGui / QtWidgets / QtQuick, etc. |
| Target version | Qt 5.12 / Qt 5.15 |
| Target device | Emulator / real device (model) |
| Priority | Which ones must be verified first |

### 1.2 Prepare the verification environment

1. Confirm you've pulled the latest fixed code
2. Rebuild Qt for HarmonyOS (see [[qt-harmonyos-build]])
3. Confirm the target device/emulator is available
4. Confirm hdc connects: `hdc list targets`

---

## Phase 2: write the verification project

> **📋 TODO sync point**: update the "Progress" column for this task in `<LOCAL_TODO>` → `Phase 2 done: verification project written`

### 2.1 Prepare item by item from the checklist

**Principle**: one independent verification case per problem, reusing existing Qt examples where possible.

**Suggested project structure**:
```
verification/
├── CMakeLists.txt          # top level
├── issue-001-window/       # verification for problem 1
│   ├── CMakeLists.txt
│   ├── main.cpp
│   └── README.md           # verification steps and expected results
├── issue-002-input/        # verification for problem 2
│   └── ...
└── ...
```

### 2.2 Conventions for writing verification cases

**Each verification case includes**:

1. **Reproduction code**: the minimal code that triggers the original problem
2. **Verification steps document** (README.md):
   - Build commands
   - How to run it
   - Steps to perform (1, 2, 3, ...)
   - Expected result (what you should see once fixed)
   - Failure signature (what you'd see if the fix doesn't work)

3. **Automated checks** (where applicable):
   - Add asserts in the code to check key state
   - Emit logs for post-hoc confirmation

**Verification case template**:
```markdown
# Verification: [problem title]

## Problem number
QTBUG-XXXXX / internal number

## Build and run
\```bash
# build steps
\```

## Verification steps
1. Launch the application
2. Perform action X
3. Observe Y

## Expected result
- [ ] The window displays normally
- [ ] Clicking the button responds
- [ ] No crashes/exceptions

## Failure signature
- Black window
- Clicks do nothing
- Crash log: ...
```

---

## Phase 3: manual verification

> **📋 TODO sync point**: update the "Progress" column for this task in `<LOCAL_TODO>` → `Phase 3 done: manual verification performed`

### 3.1 Run the verification

**Item by item**:

1. Deploy to the target device:
   ```bash
   hdc file send <hap-file> /data/local/tmp/
   hdc shell bm install -p /data/local/tmp/<hap-file>
   ```
   Or run it straight from DevEco Studio.

2. Follow the verification steps

3. Record the result:
   - ✅ Pass: behavior matches expectations
   - ❌ Fail: the problem is still present
   - ⚠️ Partial pass: fixed in some scenarios but not others
   - 🆕 New problem: the fix introduced a new anomaly

### 3.2 Recording results

**Verification report template**:

| # | Problem | Verification steps | Result | Notes |
|---|---------|--------------------|--------|-------|
| 1 | Black window | Launch the application | ✅ Pass | — |
| 2 | Input doesn't respond | Click the button | ❌ Fail | Still unresponsive |
| 3 | Crash on theme switch | Click to switch | ⚠️ Partial | Dark is OK, light still crashes |

---

## Phase 4: report the results

> **📋 TODO sync point**: update `<LOCAL_TODO>` — move this task from "📌 In progress" to "✅ Completed", filling in the completion date and a summary of the verification results

### 4.1 Summarize the verification results

- Passed: X / total
- The list of failures and an analysis of why they failed
- Newly discovered problems
- Recommendation (does it need to go back for another fix?)

### 4.2 Archive

- Keep the verification project code (for future regressions)
- Archive the verification report
- Update the issue tracking system

---

## Checklist

- [ ] The verification checklist is obtained and the scope confirmed
- [ ] The verification environment is ready (build, device, hdc)
- [ ] Every problem has a corresponding verification case
- [ ] Every case has been manually verified
- [ ] Results are recorded (✅/❌/⚠️/🆕)
- [ ] The verification report is summarized

---

## Supply chain

| Dimension | Details |
|-----------|---------|
| **Upstream source** | ① A verification notice from The Qt Company after a fix ② A verification request from Huawei after a system fix ③ Regression verification after an in-house fix |
| **Upstream input** | The verification checklist (QTBUG numbers + modules involved + target version), and the fixed Qt source/SDK |
| **Downstream recipients** | **The Qt Company (Tqtc)** / the Huawei HarmonyOS system team / internal issue tracking |
| **Deliverables** | The verification report (pass count / failure list / newly discovered problems), and the verification project code (for future regressions) |
| **Deliverable path** | `${DELIVERABLES_ROOT}/verify` (see `ENV.md`) |
| **Routing rules** | None (results go straight back to the upstream party that made the fix) |

---

## Content sources

| Source type | Notes |
|-------------|-------|
| 📄 Huawei official documentation | HarmonyOS hdc CLI commands (hdc file send, hdc shell bm install, hdc list targets) and DevEco Studio deployment |
| 🛠️ Hands-on experience | The core workflow design — trigger conditions, verification project structure, case templates, report format, checklist, and the per-phase process — all come from personal/team practice |

### Qt framework versions (validation baseline)

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |

---

## Related context

- [[framework-issue-analysis]] — The problem localization process (go back to it when verification fails)
- [[qt-harmonyos-build]] — Building
- [[qt-harmonyos-modules]] — Module status (to know which modules changed)
- [[qt-harmonyos-build-run-workflow]] — The full build-and-run process

## References

- A workflow developed from personal Qt framework verification experience; no external documentation source
- The verification checklist methodology draws on Qt's internal QA process
