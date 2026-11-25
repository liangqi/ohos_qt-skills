---
# Draft frontmatter: the format is loose; contributors only need to change status/submitted/submitter;
# reviewer/review_result are filled in by the editor.
status: draft              # draft (newly submitted) / in-review (under review) / returned (sent back) / rejected (not accepted)
submitted: YYYY-MM-DD
submitter: "<name/nickname/anonymous>"
contact: "<optional: issue link/email>"
reviewer: ""               # filled in by the editor
review_result: ""          # filled in by the editor: e.g. "promoted 2026-XX-XX (S-XXXX/C-XXXX)" / "returned: demo doesn't build" / "rejected: a bug in the app itself"
---

# Draft: <one-sentence symptom title (in the words a developer would use)>

> This template is the **contributor submission checklist**. Drafts missing required items are sent straight back by the editor; the format is free (Markdown is fine),
> and you don't need to know the S/C/W/T data model -- **numbering and splitting are done by the editor at merge time**.
> Check for duplicates before submitting: `problems/_lookup.md` (errors) and `faults/_registry.md` §Symptom index (symptoms).

## 1. Symptom [required]

- **Observable behavior (verbatim error messages / key log lines, don't paraphrase)**:
- **Trigger conditions / repro steps**:
- **First seen** (date + scenario/project):

## 2. Environment [required]

- **Qt version and kit source** (prebuilt SDK / self-built; note the commit or installer version):
- **OHOS API version / system version / device**:
- **Build method** (CMake / hvigor / CLI / DevEco):

## 3. Evidence [required -- the problem confirmation gate: classifying an issue as Qt framework-side requires A or B (or both); hearsay without evidence is not accepted]

> For platform limitations (limitation, e.g. "the sandbox forbids symlink", "an API is deprecated"), fill in **C2 official documentation/specification link and applicable versions** instead; no demo needed.

**A. Repro demo (preferred for runtime behavior anomalies)** -- the seven authoring principles + the hard requirements for Qt framework-side issues are in `faults/_index.md` §6:
- How to get it (repo link / attachment path / archive location):
- Self-checked: ☐ builds  ☐ installs and launches  ☐ symptom appears  ☐ logs are readable (key log points built into the demo)
- **Hard requirements for Qt framework-side issues (defect attributed to the Qt adaptation layer/upstream)**: ☐ the repro logic is concentrated in a **single main.cpp** (the ohos project is just a glue shell, no business code)  ☐ **repro steps are written out** (numbered down to the action level + expected result per step + expected vs actual)
- **Expected behavior vs actual behavior**:

**B. Debug logs + stack (required when there is no demo, or alongside the demo)**:
- Key hilog lines / cppcrash·jscrash faultlog backtrace / probe logs / verbatim build errors (paste verbatim, don't paraphrase):
- Collection environment and time window:

**C. Static/documentation evidence (restricted use)**:
- C1 source file:line reference chain (**only for statically decidable issues such as API semantics/macro branches/headers**):
- C2 official documentation/specification link and applicable versions (limitation only):

## 4. Preliminary root cause [optional, fill in if available]

- Location / evidence chain (source location, log inference, isolation tests):

## 5. Workaround / alternative [optional]

- How you worked around it + the cost (lost functionality/rebuild/downgrade...):

## 6. Upstream ticket [optional]

- QTBUG / Huawei issue / deliverable link and current status:

## 7. Duplicate check [required, tick]

- ☐ Checked `problems/_lookup.md`: ☐ no similar error  ☐ exists, but this entry adds new information: ______
- ☐ Checked `faults/_registry.md` §Symptom index: ☐ no matching symptom  ☐ exists, but the cause/workaround is new information: ______

## 8. Attachments and self-assessment [optional]

- Attachments (faultlog / screenshots / screen recording paths):
- Self-assessed severity (blocker/critical/high/medium/low) and why:

---

<!-- Editor's merge gate (see faults/_index.md §6, collaborative draft mode; everything leaves a trace):
     ① Duplicate check: S/C already exists → send back to become a supplement to the existing node; no duplicate pages
     ② Repro test (graded by nature):
        - defect/undetermined: the draft demo must be tested (doesn't build → send back to fix the demo; repro fails → send back for environment details; not merged unless reproduced)
        - limitation: verify the official documentation/specification link and applicable versions
     ③ Human verification: the evidence chain is factual / nature classification / responsible layer / severity calibration /
        version·date·ticket-number facts (leave blank rather than invent) / W usability and retirement condition / sanitization (public edition)
     ④ Repro trace: the first row of the merged C page's "Version verification log" records the editor's reproduction (date/environment/conclusion);
        a contributor's workaround verified by the editor is recorded as tested, unverified as proposed
     ⑤ promote: split into S/C/W/T source-of-truth records (assign ids) → delete the draft file (git history + verification log are the archive)
     ⑥ python tools/faults-build.py build (zero ERRORs) + backfill fault-C-XXXX into the refs of related pages -->
