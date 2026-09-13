---
id: procedural-qt-bug-report-generation
type: procedural
domain: tools
tags: [bug-report, workflow]
created: 2026-08-01
updated: 2026-08-12
status: active
audience: public
refs: [procedural-qt-bug-report-sample, procedural-framework-issue-analysis, semantic-qt-harmonyos-golden-rules]
summary: >
  The bug report generation workflow: extract information from the conversation context or an existing problem page → fill in the embedded template → self-check reproducibility (a HARD gate) →
  produce one of two forms (form A, a complete deliverable for Huawei / form B, a condensed version for an issue tracker). External partners can learn to write a bug report from this page plus
  the sample page alone; the template structure is embedded here and doesn't depend on any internal template file.
---

# Generating a Qt for HarmonyOS bug report

> Follow this process to generate a structured bug report when a Qt developer/partner hits an SDK problem (a crash / odd behavior / an interface that doesn't match the documentation) and needs to report it, or when an internal team needs to formally deliver a confirmed HarmonyOS system problem to Huawei.
> **This page is self-contained**: external partners can learn to write a bug report from this page plus the [[procedural-qt-bug-report-sample]] sample page alone. The template structure is embedded in §Template structure and depends on no internal template file.

---

## When this applies

- **External reporting**: a Qt developer/partner hits an SDK problem (a crash / odd behavior / an interface mismatch) and wants to report it to the Qt for HarmonyOS maintenance team — when a Qt framework problem or a HarmonyOS system problem is identified in conversation, choose **form B** (the condensed version: copy, fill in, and paste into an issue tracker or email)
- **Internal delivery**: the maintenance team has completed its analysis through the bug-triage workflow and needs to formally deliver a confirmed HarmonyOS system problem to Huawei — choose **form A** (the complete deliverable, with the in-depth analysis sections + a pure-HarmonyOS demo + a logs directory)
- **Promoting captured KB knowledge**: there's already a problem page in the KB (`problems/<type>-<slug>.md`) that needs promoting into a reportable bug report — mechanically copy the problem's fields into the template and add the analysis sections; the result can flow back in either direction

---

## Inputs

### What the reporter provides (5 mandatory items)

| # | Mandatory item | Description | Difficulty |
|---|----------------|-------------|:----------:|
| 1 | **A Qt reproduction demo** | The project you already have, as long as it triggers the problem — it doesn't need minimizing | Easy |
| 2 | **A faultlog** | Captured with the single hdc command given in §Template structure | Easy |
| 3 | **The reproduction environment (six items)** | OS version / SDK version / Qt version + commit / device model / toolchain version / build mode | Easy |
| 4 | **Reproduction steps** | ≤3 steps, from launching the application to the problem appearing | Easy |
| 5 | **Urgency** | P0 blocking / P1 severe / P2 normal / P3 minor | Easy |

### Optional for the reporter

| Optional item | Description | When you're unsure |
|---------------|-------------|--------------------|
| An initial attribution | Where the problem lies (the Qt framework / the HarmonyOS system / the application layer) | Just write "unclear"; it won't block anything |
| What you've already tried | Which troubleshooting steps you've already taken | Leave it blank |
| Documentation discrepancies | Any mismatches you found between the documentation and the actual behavior | Leave it blank |

> **The principle**: for the hard fields (problem attribution, documentation comparison), just write "unclear" — it won't block anything. The internal team fills these in during form A's in-depth sections.

### What the internal team fills in (from bug-triage phases two/three)

| In-depth section | Content | Source |
|------------------|---------|--------|
| Call chain tracing | The complete call chain from the Qt layer down to the system interface | bug-triage phase three §3.1 |
| System interface behavior | The system interface's input parameters, return values, and how they compare to what the docs say | bug-triage §3.4 |
| Direct-call verification | The result of calling the system interface directly, bypassing Qt; includes the **in-callback synchronous query method, the match=0 smoking gun** (see below) | bug-triage §3.8 |
| The official documentation comparison table | A dimension-by-dimension comparison of what the docs describe vs. the actual behavior | bug-triage §3.5 |
| A pure-HarmonyOS reproduction demo | The `ohos-repro/` directory, proving the problem has nothing to do with Qt | bug-triage §4.3 |

> **The in-callback synchronous query method (the match=0 smoking gun)**: when the value a system callback reports looks suspiciously inconsistent with the actual state, query the actual state **synchronously, inside that callback**, using the system's own API, and compare it to the reported value. Three layers of cross-validation make it airtight: ① **synchronicity** — the query immediately follows the reported-value log inside the callback, with the same timestamp and no delay, ruling out "the caller queried too late"; ② **the same object** — you query the exact object pointer the callback was handed; ③ **cross-checking with an independent callback** — compare against the value another independent system callback reports; if that disagrees with this callback's reported value but agrees with your synchronous query, your query is correct. `match=0` (the reported value ≠ the actual state) is a **smoking gun for a system bug**: the value the system reported in the callback simply wasn't what the object had at the time.

### Mechanically copying from a KB problem page (if one exists)

If the KB already has a corresponding problem page, the following fields can be copied mechanically into the template without rewriting:

| problem page field | Where it goes in the template |
|--------------------|-------------------------------|
| `summary` | → Problem overview |
| `environment` | → Reproduction environment |
| `error_message` | → Error log |
| `error_code` | → Error log (appended after the log) |
| `symptoms` | → Actual behavior |
| `severity` | → Urgency (mapping critical→P0, high→P1, medium→P2, low→P3) |
| `keywords` | → Problem overview (as keyword annotations) |
| The body's `## Error message` | → Error log |
| The body's `## Scenario` | → Reproduction steps |
| The body's `## How to verify` | → Expected behavior / actual behavior |

---

## Outputs (two forms)

> The template has two parts: **part (A)** = the basic information the reporter must fill in; **part (B)** = the in-depth analysis the internal team adds.

### form A — the complete deliverable

Render both parts (A) and (B) in full, producing a delivery directory:

```
${DELIVERABLES_ROOT}/<issue-name>/
├── SYSTEM_ISSUE_REPORT.md    → The complete report (all of (A)+(B) rendered)
├── ohos-repro/               → The pure-HarmonyOS reproduction demo (the core deliverable)
├── qt-repro/                 → The Qt reproduction demo (supporting evidence)
├── logs/                     → The key log files
└── README.md                 → A deliverables overview
```

The recipient: **the Huawei HarmonyOS system team**. This corresponds to the heavyweight version in bug-triage §4.2.

### form B — the condensed issue version

Render only part (A) plus part (B) compressed into a single "initial analysis" paragraph, producing a single document:

- Paste it into an issue tracker (GitCode / Gitee / GitHub) body
- Or send it as the body of an email

The recipient: **an external partner filing quickly** or **the maintenance team's initial routing**.

---

## Steps

### 1. Choose the form

| Scenario | Form | Rationale |
|----------|------|-----------|
| An external partner reporting, copy-and-fill | **form B** | Condensed; doesn't require in-depth analysis skills |
| Internal analysis is complete and it's being delivered to Huawei | **form A** | Complete, with the in-depth sections + a pure-HarmonyOS demo |

### 2. The reporter fills in the 5 mandatory items

Fill in each field per the field tables in §Template structure:

- **The reproduction environment (six items)**: fill in the table, marking any missing item "unknown"
- **The symptom**: expected behavior + actual behavior, with screenshots if you have them
- **The error log**: captured with the single hdc command in the template (see §Template structure → capturing the faultlog)
- **Reproduction steps + a Qt demo**: ≤3 steps, with the demo project or code snippet attached
- **Urgency**: P0/P1/P2/P3

> For the hard fields (problem attribution, documentation comparison), just write "unclear" — it won't block anything; the internal team fills these in at form A's step 5.

### 3. Run the completeness self-check (a HARD gate)

All four of these must be ticked before anything moves downstream; **if any one isn't, send it back to be completed**:

- [ ] **HARD** All six environment items are present (OS/SDK/Qt commit/device/toolchain/build mode)
- [ ] **HARD** The reproduction steps are ≤3 steps
- [ ] **HARD** Expected / actual / log are all complete (not just "it broke" with no specifics)
- [ ] **HARD** A demo is attached (a project or a code snippet)

> Failing this gate means downstream can't judge reproducibility, so it must go back. Don't proceed to step 4.

### 4. Fill in the missing information and clarification points (the internal back gate)

List every ambiguity in the template **explicitly** and clear them all before sending, achieving "**no going back to ask**":

| Check | What to do |
|-------|------------|
| An environment item marked "unknown" | Fill it in, or note "doesn't affect reproduction" |
| An ambiguous reproduction step | Ask about the trigger conditions and write it precisely |
| A vague expected/actual description | Make it concrete ("the window doesn't display" → "after calling setSize, the window is still 0x0") |
| The log doesn't line up with the symptom | Note which log line corresponds to which symptom |

> **The principle**: every "unclear" and ambiguity is cleared before sending. form B may keep a few "unclear"s (the condensed version is more tolerant); form A must clarify all of them.

### 5. (A) The recipient fills in the in-depth sections

form A only. The following in-depth sections require Qt source knowledge and the ability to call N-API directly, and come from bug-triage phases two/three:

| In-depth section | What to do | The key method |
|------------------|------------|----------------|
| **Call chain tracing** | Trace from the demo's entry API through the Qt source to the system interface call site | Focus on `src/plugins/platforms/ohos/` (the QPA plugin layer) and `qtohosextras/` |
| **System interface behavior** | Add logs before and after the system interface call, recording the input parameters and return values | Use a consistent `[OHOS-BUG-TRIAGE]` prefix and filter with `hdc shell hilog \| grep "[OHOS-BUG-TRIAGE]"` |
| **Documentation comparison** | Compare the documented description against the actual behavior dimension by dimension | Documentation sources: the [HarmonyOS Native API](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/native-apis-overview) and the [Ability framework](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ability-kit) |
| **Direct-call verification** | Bypass Qt and call the system interface directly to confirm the problem reproduces independently of Qt | Includes the **in-callback synchronous query method, the match=0 smoking gun** (see the explanation in §Inputs → what the internal team fills in) |
| **A pure-HarmonyOS demo** | Reproduce the problem with the least possible native HarmonyOS code | Four principles: ① minimal ② standalone ③ runnable ④ contrasting (see below) |

> **The four principles for a pure-HarmonyOS demo**:
> 1. **Minimal** — include only the system interface calls needed to trigger the problem
> 2. **Standalone** — no dependency on Qt or any third-party library
> 3. **Runnable** — provide a complete DevEco Studio project that can be built and deployed directly
> 4. **Contrasting** — where there's a known-correct expected behavior, show both the correct and the anomalous case side by side in the demo

### 6. (A) Run the deliverables checklist + ★ human verification

form A only. The deliverables must pass a **human review** before being submitted to Huawei:

- [ ] SYSTEM_ISSUE_REPORT.md is created with both (A) and (B) complete
- [ ] The pure-HarmonyOS reproduction demo (ohos-repro/) builds and runs standalone
- [ ] The Qt reproduction demo (qt-repro/) is tidied up
- [ ] The key logs are collected and annotated (marking anomalies on the key lines with `>>>`)
- [ ] Every file is in `${DELIVERABLES_ROOT}/<issue-name>/`
- [ ] The README.md deliverables overview is created
- [ ] ★ **Human verification is complete**: the deliverables have been reviewed by a human, and the root cause determination is signed off by a human

> **The lesson from issue #774**: AI-produced deliverables — the reproduction demo, diagnostic patches, the root cause determination — must all be confirmed by a human before going out. An AI self-check can't substitute for human verification: the AI may falsely report "reproduced successfully", miss a typo in a patch, or claim something was confirmed when the log never actually showed it. **The submission action (sending it outward) is performed by a human, not automatically by the AI.**

### 7. Promote it into a KB problem page (if it should be captured)

To capture a bug report back into a KB problem page, make the following mechanical conversions:

| Conversion | In the bug report | In the problem page |
|------------|-------------------|---------------------|
| type | `bugreport` | `problem` |
| id prefix | `bug-report-<slug>` | `problem-<slug>` |
| Bug-only fields | The report number/reporter/urgency and so on | Delete them (a problem page has no such fields) |
| frontmatter comments | May have `# explanatory` comments | Use bare values and delete the comments |
| Location | The delivery directory | `problems/` |

After converting:
1. Move it into the `problems/` directory
2. Run `bash _scripts/kb-regen-indexes.sh` to regenerate `problems/_lookup.md`, `_index/_map.md`, and the other derived indexes (they're rebuilt automatically from the frontmatter; no entries or summaries need adding by hand)
3. Keep all the other fields (summary/environment/error_message/symptoms/severity/keywords + the body sections) as-is

> The converted problem page's 8 fields (id/summary/refs/tags/audience/status/type/updated) align with the `_templates/qt-problem.md` baseline, which means it passes the 25-item gate.

---

## Template structure (embedded, self-contained)

> The template structure below is embedded directly in this page. External partners don't need access to any internal template file — just fill this in.

### Metadata (at the top of the report)

| Field | form A | form B | Notes |
|-------|:------:|:------:|-------|
| Report number | ✅ | Optional | form A: `OHOS-ISSUE-YYYY-NNN`; form B: the issue tracker numbers it automatically |
| Report date | ✅ | ✅ | `YYYY-MM-DD` |
| Reporter | ✅ | ✅ | Name / ID |
| Urgency | ✅ | ✅ | P0 blocking / P1 severe / P2 normal / P3 minor |

### The reproduction environment (six items, mandatory in both forms)

| Item | Example value |
|------|---------------|
| ① OS version | HarmonyOS 5.0.1 |
| ② SDK version | HarmonyOS SDK 5.0.0 (API Level 12) |
| ③ Qt version + commit | Qt 5.15.16 @ 962aa625 |
| ④ Device model | Mate 60 Pro / the emulator |
| ⑤ Toolchain version | DevEco Studio 5.0 / hvigor 4.0 / clang 15 |
| ⑥ Build mode | debug / release |

### Capturing the faultlog (a single command)

```bash
hdc shell hilog -x | grep -iE "fatal|crash|exception|<bundleName>" > faultlog.txt
```

> If you need the native crash dump file:
> ```bash
> hdc shell ls -lt /data/log/faultlog/temp/ | head -5
> hdc file recv /data/log/faultlog/temp/<the newest file> ./
> ```

### The section skeleton

**form A's complete structure** (all of (A)+(B)):

```
# HarmonyOS system problem report

## Basic information
[The metadata table: report number/date/reporter/urgency]

## Reproduction environment
[The six-item environment table]

## Problem overview
[One paragraph: what action → what anomaly]

## Expected behavior
[How the interface/feature should behave, per the official documentation or common sense]

## Actual behavior
[The anomaly observed, with log/screenshot evidence]

## Reproduction steps
1. [Step 1]
2. [Step 2]
3. [Step 3]
(≤3 steps)

## Error log
[The faultlog captured with hdc, with anomalies on the key lines marked >>>]

## Initial attribution
[Where you think the problem lies; write "unclear" if you're not sure]

--- everything below is part (B), the in-depth analysis, form A only ---

## Root cause analysis

### Call chain tracing
[The complete call chain from the Qt layer to the system interface, noting the parameter conversions at each step]

### System interface behavior
[The system interface's input parameters, return values, and how they compare to what the docs say]
[The hilog output after adding logging, filtered on the [OHOS-BUG-TRIAGE] prefix]

### Direct-call verification
[The result of calling the system interface directly, bypassing Qt]
[Including the in-callback synchronous query method's match=0 smoking gun (where applicable):
 synchronicity + the same object + cross-checking with an independent callback → match=0 = a smoking gun for a system bug]

## Comparison with the official documentation
| Dimension | What the docs say | The actual behavior | The difference |
|-----------|-------------------|---------------------|----------------|
| [Dimension 1] | [What the docs say] | [What actually happens] | [An explanation of the difference] |

## The pure-HarmonyOS reproduction demo
[A description of the ohos-repro/ directory: build and run steps + expected vs. actual]
[The four principles: minimal/standalone/runnable/contrasting]

## Impact assessment
[The scope and severity of this problem's impact on Qt for HarmonyOS]

## Recommendations
[Suggestions for Huawei: the fix direction you'd like, or a temporary workaround]
```

**form B's condensed structure** (all of part (A) + part (B) compressed into one paragraph):

```
## Reproduction environment
[The six-item environment table]

## Problem overview
[One paragraph]

## Expected behavior
[What should happen]

## Actual behavior
[The actual anomaly + logs/screenshots]

## Reproduction steps
1. [Step 1]
2. [Step 2]
3. [Step 3]
(≤3 steps)

## Error log
[The faultlog, with key lines marked >>>]

## Initial analysis
[Part (B) compressed into one paragraph: the call chain highlights + the system interface behavior highlights +
 the direct-call verification conclusion + the documentation discrepancy highlights. Write "unclear" if there's no in-depth analysis.]
```

---

## Checklist

### General checks (both forms)

- [ ] The form is chosen (A or B)
- [ ] The 5 mandatory items are filled in (the six environment items / the symptom / the log / the steps + demo / the urgency)
- [ ] **The HARD gate passes**: all six items present + ≤3 steps + expected/actual/log complete + a demo attached
- [ ] Ambiguities and "unclear"s are listed explicitly
- [ ] The template structure is complete (filled in per the §Template structure skeleton)

### Additional checks for form A

- [ ] The in-depth sections are complete (call chain / system interface behavior / direct-call verification / documentation comparison / the pure-HarmonyOS demo)
- [ ] The delivery directory structure is complete (SYSTEM_ISSUE_REPORT.md + ohos-repro/ + qt-repro/ + logs/ + README.md)
- [ ] ★ Human verification is complete, and the submission is performed by a human

### Additional checks for form B

- [ ] The initial analysis is compressed into one paragraph (or says "unclear")
- [ ] It can be pasted straight into an issue tracker / email body

---

## Related context

- [[procedural-qt-bug-report-sample]] — The bug report sample page (a complete form A example to learn from)
- [[framework-issue-analysis]] — The Qt framework-internal issue analysis workflow (the source of step 5's call chain tracing method; switch to it when the problem is determined to be a Qt framework issue)
- The internal triage workflow — Verification and analysis of HarmonyOS system problems for commercial Qt (the source of form A's in-depth sections; §4.2 the SYSTEM_ISSUE_REPORT.md specification, §4.6 the checklist, §3.8 the in-callback synchronous query smoking gun)
- [[qt-harmonyos-golden-rules]] — The iron rules quick reference (scan before reporting to avoid known pitfalls)

---

## Supply chain

| Dimension | Details |
|-----------|---------|
| **Upstream source** | ① SDK problems reported by external Qt developers/partners ② System problems confirmed through the internal bug-triage workflow ③ Existing KB problem pages |
| **Upstream input** | The conversation context (problem description/screenshots/code snippets) + a faultlog + the reproduction environment + a Qt demo + optionally, fields from a problem page |
| **Downstream recipients** | form A → the Huawei HarmonyOS system team; form B → an issue tracker / email |
| **Deliverables** | form A: the complete `<issue-name>/` directory; form B: a single document (.md or the issue body) |
| **Deliverable path** | form A: `${DELIVERABLES_ROOT}`; form B: an issue tracker or email |

---

## Relationship to other workflows

| Scenario | Workflow to use |
|----------|-----------------|
| An external SDK problem report needing a bug report | **This process**, form B |
| Internal analysis of a system problem is complete and it's going to Huawei | **This process**, form A (with the in-depth sections from the internal triage workflow) |
| It turns out to be a Qt framework problem (not a system problem) | Switch to [[framework-issue-analysis]] (packaging and submitting an upstream issue) |
| It turns out to be an application-layer problem | Give the customer fix recommendations |
| An existing KB problem page needs promoting into a bug report | **This process**, step 7's mechanical conversion |

---

## Content sources

| Source type | Notes |
|-------------|-------|
| 💼 Hands-on experience | The workflow design, the HARD gate, the no-going-back-to-ask principle, and the human-verification lesson from issue #774 |
| 🛠️ Framework source | The call chain tracing method (inherited from framework-issue-analysis) and the system interface logging convention (inherited from bug-triage) |
| 📄 Huawei official documentation | The HarmonyOS API documentation reference ([developer.huawei.com](https://developer.huawei.com/consumer/cn/doc/)) |

### Qt framework versions (validation baseline)

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |
