---
domain: faults
updated: 2026-09-14
counts:
  symptoms: 7
  causes: 8
  workarounds: 6
  tickets: 4
description: >
  The fault base (graph model): symptom S × cause C (defect/limitation) × workaround W × upstream tracking ticket T.
  The single source of truth is _data/*.yaml and the C pages; _graph.yaml and _registry.md are
  rebuilt automatically by tools/faults-build.py (automatic evolution). This page is the spec: entities/edges/state machines, fields,
  entry and review rules, tool usage.
---

# faults — the fault base (graph model, evolving automatically)

> Positioning in one sentence: `problems/` answers "how do I fix this error"; `faults/` answers "what is the root cause of this symptom,
> who owns it, is it a defect that will be fixed or a limitation you can't get around, has it been fixed, how do you live with it until the permanent fix/alternative, and where is the upstream ticket".
> **The problem is essentially a graph**: one application-layer behavior (S) may hang off a Qt SDK defect (C-defect, waiting for a fix,
> followed up by a T tracking ticket and its fix_version), or off a HarmonyOS platform limitation (C-limitation, with no
> "fix", only a W alternative), or it may be produced by several causes combined.

## 1. Positioning and division of labor

| Carrier | What it records | Granularity | How to look things up |
|------|--------|------|---------|
| `problems/` | Symptom → root cause → solution for a single error (one page per error) | Error message | Look up `_lookup.md` by error code/error text |
| `faults/` (this base) | **The symptom × cause × workaround × ticket graph** | See §2 | Look up by **behavior** in `_registry.md` §Symptom index or `_graph.yaml` |
| `semantic/qt-harmonyos-platform-limits.md` | Platform limitations confirmed by Qt officially (with QTBUGs) | Platform capability | By limitation entry |
| `knowledge/adaptation/blockers.yaml` | Module/capability-level blocker classification (used by assess) | Taxonomy | Machine layer |
| `episodic/postmortems/` | Full postmortems of problem analyses | Event | By summary |
| `TODO.local.md` | "Things I need to do" | Task | Personal to-dos (gitignored) |

Relationship: once error text hits a problems page, if the root cause is external, follow the `fault-C-xxxx` in that page's `refs`
into the fault graph; in reverse, a C page points back to the in-depth content via `refs`. **problems doesn't duplicate tracking status,
and faults doesn't duplicate solution steps (detailed steps live in the C page body or the problems page; W records reference them through the detail pointer).**

## 2. Graph model (four entity types + four edge types)

### Entities

| Entity | ID | Form (source of truth) | Content |
|------|----|-------------|------|
| **symptom** | `S-xxxx` | Inline record: `_data/symptoms.yaml` | A cluster of symptoms a developer can observe: title/domain/severity/status/causes/first_seen/refs |
| **cause** | `C-xxxx` | Its own page: `C-xxxx-slug.md` (the frontmatter is the source; the body is the in-depth record) | Root cause evidence chain, responsibility, permanent fix/alternative, version verification log |
| **workaround** | `W-xxxx` | Inline record: `_data/workarounds.yaml` | The workaround, cost, verification (date+env), **retirement condition**, pointer to detailed steps (detail) |
| **ticket** | `T-xxxx` | Inline record: `_data/tickets.yaml` | Upstream ticket (QTBUG-xxx / Huawei issue / partner deliverable), status, **fix version fix_version**, fix commit |

A limitation's "alternative" is a W (`targets` pointing to that C); a defect's "workaround" is also a W.
One C can have several W (alternative options), and several T (one on the Qt side + one on the Huawei side).

### Edges

| Edge | Direction | Declared in (source of truth) | Meaning |
|----|------|-----------|------|
| `causes` | S→C | `causes` in symptoms.yaml | The symptom is produced by the cause; with multiple causes, `cause_relation`: `any_of` (default) / `all_of` (they only produce it combined) |
| `targets` | W→C | `targets` in workarounds.yaml | The workaround acts on that cause |
| `tracks` | T→C | `tracks` in tickets.yaml | The ticket follows up on that cause |
| `depends_on` | C→C | `depends_on` in the C page frontmatter | Resolving this cause is blocked by another cause/limitation (**only connect when evidenced**; no speculation) |
| `manifests` | C→S | **Derived** (build infers it from causes) | Reverse-lookup index, generated automatically in _graph.yaml |

### Classifying the cause (nature) -- the watershed between "fix" and "work around"

| nature | Meaning | Resolution path | Key fields |
|--------|------|---------|---------|
| `defect` | A defect, **will be fixed** | Fix lifecycle: T filed → T.fix_version → fix-confirmed → local verification → W retired | `fix_route`, T.fix_version |
| `limitation` | A HarmonyOS specification/platform limitation, **won't be "fixed"** | Alternative (W) + watching the evolution | `evidence` (classification evidence), `evolution` (evolution direction) |
| `undetermined` | Pending classification | Reclassify after the upstream reply, **the CID stays the same** (history is not erased); the entry records the reclassification evidence | — |

Decision rule: go by **whether the behavior of the layer where the root cause lives can change** -- an implementation error in the Qt adaptation layer/SDK/compiler is a
defect; the platform being specified that way (sandbox, permission model, API deprecation, capability not offered) is a limitation.
When unsure, record `undetermined` first and reclassify once the classification evidence is in.

## 3. Responsibility (C.responsible)

| Value | Meaning | Fix route |
|----|------|-------------|
| `qt-port` | The Qt HarmonyOS adaptation layer (the tqtc/harmonyos branches, the libqohos QPA, QtOhosExtras, the glue templates) | The next Qt OHOS SDK / harmonyos branch |
| `qt-upstream` | A defect in official Qt mainline (exists across platforms) | An official Qt release (fix the trunk first, then cherry-pick to the harmonyos branches) |
| `ohos-runtime` | HarmonyOS system behavior (ArkTS runtime, NAPI, window management, IMF, graphics) | A system OTA / new API version |
| `ohos-toolchain` | DevEco Studio / hvigor / hdc / signing tools | A DevEco update |
| `ohos-ndk` | OHOS LLVM/clang, musl, libcxx-ohos, sysroot | An SDK/NDK update |
| `third-party` | A third-party library/graphics stack itself (Mesa/ZINK, etc.) | A third-party library release |
| `app` | An application-side code problem | Fix it yourself (in principle no C is created; only for contrast) |
| `undetermined` | Responsibility not assigned | — |

Responsibility goes by **the layer where the root cause lives**; `co_responsible` records the secondary party in combined responsibility (e.g. C-0005 × C-0006).

### Disposition (a derived view -- the developer's view of "what to do when you hit it")

**Computed automatically** from nature × responsible (derived by `faults-build.py`; not stored in the source of truth, no double-writing),
and output in `_registry.md` §By disposition and the `disposition` field of `_graph.yaml`:

| disposition | Label | Computation rule | Meaning |
|---|---|---|---|
| `must-adapt` | **Must adapt for HarmonyOS** | nature=limitation | This is how the platform/SDK is specified (sandbox, permission model, API deprecation, loader limitations, module scope); change your own code, there is no upstream fix to wait for |
| `qt-defect` | **Qt issue** | nature=defect and responsible ∈ qt-port/qt-upstream | Wait for a Qt fix / local patch / file a QTBUG |
| `system-defect` | **System issue** | nature=defect and responsible ∈ ohos-runtime/ohos-ndk/ohos-toolchain | Wait for a system/SDK/toolchain release or file a ticket with Huawei |
| `app-usage` | **Application usage issue** | responsible=app | Application misuse/a problem in its own code, not a framework problem -- change the application code |
| `third-party` | **Third-party library issue** | nature=defect and responsible=third-party | A defect in the third-party library itself (wait for a third-party release/switch libraries) |
| `undetermined` | Pending classification | Everything else (nature=undetermined, etc.) | Falls into one of the categories above automatically once upstream classifies it |

## 4. State machines (one per entity type)

### C.status (cause progression; single-valued, forward only, except for regressions)

```
open → diagnosed → workaround → reported → fix-confirmed → verified → closed
         │             │
         └──► wontfix ─┘   (upstream explicitly won't fix / by design → the normal end state for a limitation)
limitation only: watching (classified + the evolution direction is clear; watching the platform/upstream pace, no local fix action)
any state ──► closed (duplicate / obsolete / out of scope)
regression: verified / wontfix → open (note the regression in the version verification log; the CID stays the same)
```

| status | defect meaning | limitation meaning |
|--------|------------|----------------|
| `open` | Found; root cause/responsibility not yet determined | Found; no specification evidence yet |
| `diagnosed` | Root cause and responsibility determined | Confirmed that this is how the specification is (evidence in place) |
| `workaround` | A workaround (W) is verified to work | An alternative (W) is recorded and verified |
| `reported` | A T is following it upstream | — (evolution requests can be recorded as a T) |
| `fix-confirmed` | T.released/fix_version in place, pending local verification | — (when platform evolution offers a new path, use watching as the transition) |
| `verified` | Verified locally with a release containing the fix | Migrated per the evolution direction; the alternative is promoted |
| `wontfix` | Upstream explicitly won't fix | **The normal end state**: this is the specification; long-term reliance on the alternative |
| `watching` | — (not used for defects) | Watching the evolution |
| `closed` | Record closed (retirement steps done) | Same |

### W.status (workaround lifecycle)

```
proposed (suggested, not verified) → tested (verified) → adopted (adopted as the main option) → retired (retired)
```

- The `verified` field (date + env) records the most recent verification; it may be omitted if there is no record (don't invent one).
- `retire_when` is required: what to undo once the official fix/migration lands -- it is the basis for the "automatic evolution" retirement check.

### T.status (tracking ticket lifecycle)

```
draft (draft) → submitted (filed) → accepted (accepted) → fixed (merged)
             → released (shipped in a release; fix_version required) → closed
branches: dup (duplicate) / wontfix (rejected)
```

- `fix_version` is the authoritative source for the **fix version** (e.g. "Qt 6.12-beta4", "API 25");
  build aggregates the fix_version of released tickets into C.fixed_in in `_graph.yaml`.
- `tracker`: `qt-bug` / `ohos-issue` / `gitee` / `partner` (partner deliverable) / `forum`.

### S.status (symptom, independently observable)

`active` (still hit when no workaround is applied) / `mitigated` (gone with the workaround) / `resolved` (the root cause is fixed or migrated).

### Chain completeness (the closed-loop rule) -- deciding "temporarily resolved" and propagating gaps upward

For a cause to count as **temporarily resolved (needing no further handling)**, depending on its classification/responsibility it must meet the following (`faults-build.py`
derives `chain_state` + `gaps`, machine-enforced):

| Classification/responsibility | Condition for temporarily resolved | Gap decision |
|---|---|---|
| defect × external responsibility (qt-port/qt-upstream/ohos-*/third-party) | **W(adopted) and T(tracked)** -- both are required | Workaround but no ticket = `missing-ticket`; ticket but no workaround = `missing-workaround`; both missing = `both-missing` |
| limitation (Must adapt for HarmonyOS) | **W(adopted)** -- there must be an adopted adaptation/alternative | No upstream ticket to track (record-keeping T don't affect the decision) |
| defect × app (Application usage issue) | **W(adopted)** | The fix is on you, no ticket needed; after verifying the changed usage it can go straight to closed (permanent fix) |
| undetermined | **W(adopted)** (work around first while awaiting classification) | Once classified as an external defect, a T becomes a hard requirement (review reminds you) |

**Permanent fix** (`root-resolved`): C.status has entered fix-confirmed/verified/closed -- no W/T completeness needed
(at that point the W should be retired per retire_when).

**Gaps propagate upward**: an S's claim of resolution is bounded by the aggregate of its causes -- if any cause has a gap, the symptom is not closed
(the S's `gaps` = the union of its causes' gaps; `chain_state` takes the worst). Machine-enforced (check):

- S.status=resolved but the chain has gaps → **ERROR** (downstream is not closed, so upstream may not claim full resolution; downgrade to
  mitigated/active);
- S.status=mitigated but no adopted W backs it → **ERROR** (a mitigation claim must be backed by an adopted workaround,
  otherwise mark it active);
- C.status=workaround but the chain is not closed → **WARN** (it claims to be temporarily resolved but has gaps per the closed-loop rule --
  usually a missing T: the workaround is in place, the ticket is to be filed/tracked);
- if the gap is a missing T and the C already has a **scheduled placeholder ticket** (T.status=draft with `planned_filing` set) →
  downgraded to **INFO**: the gap still exists and the chain still counts as not closed (`chain_state` unchanged); this only separates "nobody
  owns it" from "scheduled, to be filed". Once the ticket is actually filed, set T.status to `submitted` and fill in the number,
  and the INFO disappears automatically.

Where it is reported: `chain_state`/`gaps` on the S/C nodes in `_graph.yaml`; in `_registry.md`, the "Chain closure" statistics row +
the "Closure" column of the symptom index + **§Not closed** (grouped as missing ticket/missing workaround/both missing, with W/T/symptoms); and the
"Not closed (to be filled)" section of the `review` subcommand.

## 5. File layout and fields (single source of truth → derived artifacts)

```
faults/
├── _data/
│   ├── symptoms.yaml      source of truth: S records + causes edges
│   ├── workarounds.yaml   source of truth: W records + targets edges
│   └── tickets.yaml       source of truth: T records + tracks edges
├── C-xxxx-slug.md         source of truth: C pages (all frontmatter fields + depends_on edges; the body is the in-depth record)
├── _drafts/               collaborative draft area (not in the graph, not validated by check): _template.md submission checklist
│   └── draft-YYYYMMDD-slug.md   contributor submissions (awaiting the editor's review, see §6)
├── _graph.yaml            derived artifact: machine-readable full graph (rebuilt by build, don't edit by hand)
├── _registry.md           derived artifact: the registry (rebuilt by build, don't edit by hand)
├── _index.md / _template.md   this spec / C page template
```

**After changing any source of truth, run `python tools/faults-build.py build`** -- the graph, the registry, the counts, the reverse-lookup
index (manifests) and the aggregate overview (workaround_state / fixed_in / tickets) are all rebuilt automatically.

### C page frontmatter fields

| Field | Required | Notes |
|------|:---:|------|
| `id` / `cid` | ✅ | `fault-C-XXXX` / `C-XXXX` (the file name must start with `C-XXXX-`) |
| `type` | ✅ | Always `cause` |
| `title` | ✅ | A one-sentence **cause** title (not the symptom) |
| `nature` | ✅ | `defect / limitation / undetermined` |
| `domain` | ✅ | `build / deploy / runtime / render / api / input / lifecycle / toolchain / filesystem` |
| `fault_type` | ✅ | `bug / crash / build-blocker / hang / gap / regression / caveat / deprecation` |
| `responsible` / `co_responsible` | ✅/ | See §3 |
| `component` | ✅ | The specific component/file |
| `severity` | ✅ | `blocker / critical / high / medium / low` |
| `evidence_type` | ✅ | `demo / logs / both / source / docs` (§6, evidence standard; enforced by check) |
| `status` | ✅ | See §4 |
| `fix_route` | defect | The fix route in one sentence (used by the registry) |
| `evidence` / `evolution` | limitation | Classification evidence / evolution direction (at least one; enforced by check) |
| `review_note` | ✅ | Review focus (used by the review output) |
| `depends_on` | ✅ | Other C it depends on (`[]` if none; only when evidenced) |
| `affects_qt` / `affects_ohos` | ✅ | Affected versions (aligned with the root document's validation baseline; if unsure write "not recorded") |
| `qoh` |  | Related machine-layer error patterns |
| `first_seen` / `review_due` | ✅ | First seen / review due |
| `created` / `updated` / `tags` / `audience` / `refs` / `summary` | ✅ | Repo-wide conventions |

There are **no longer** `workaround / upstream_* / fixed_in_* / manifests` fields -- they are expressed by the W and T entities
and aggregated by build (avoiding double-write drift).

### S / W / T record fields

See the header comments of `_data/*.yaml` (with full field descriptions and state machines); the format follows the repo's
`tools/qt_ohos/yaml_lite.py` subset (2-space indentation, flow lists, **no inline dicts**).

### C page body sections

Symptoms (one subsection per S) → Root cause / classification basis → Responsibility → Permanent fix (defect) or
Alternatives and evolution (limitation) → Workarounds (referencing W + detailed steps of the best option) → Tickets
(referencing T) → **Version verification log** (append-only table) → Related (S/W/T/problems/semantic/C).

## 6. Entry rules (graph-aware procedure)

### Evidence standard and repro demo authoring principles (the problem confirmation gate)

**Hearsay/guesses without evidence may not be classified as Qt framework problems.** Anything classified as an external root cause (especially
Qt framework-side problems with `nature=defect` and `responsible ∈ {qt-port, qt-upstream}`) must hold
one of the kinds of evidence in the table below, declared by the required C page field **`evidence_type`** and machine-enforced by `check`:

| evidence_type | Meaning | Applies to |
|---|---|---|
| `demo` | **Repro demo**: a minimal reproducible ohos project (seven authoring principles below) | Preferred for runtime behavior anomalies |
| `logs` | **Debug logs + stack**: key hilog lines, cppcrash/jscrash faultlog backtraces, probe logs, verbatim build errors, isolation test output | Required when a demo can't be produced; or alongside the demo |
| `both` | demo + logs | The strongest evidence |
| `source` | **Source file:line reference chain** (static evidence) | **Only for statically decidable issues** (API semantics/macro branches/missing headers, etc., where the source is conclusive); a Qt framework-side defect with source gets a WARN: add a demo/logs before filing upstream |
| `docs` | Official documentation/specification links | **limitation only** -- a defect may not be classified from documentation alone |

**Machine-enforced (`check`, ERROR)**:

1. a `defect`'s evidence_type may not be `docs`;
2. a `limitation`'s evidence_type ∈ {docs, source, logs} (a demo is not classification evidence for a specification);
3. a `defect`/`undetermined` cause with a **tracked upstream ticket** (T.status ∈ filed and tracked, and tracker ∈ qt-bug / ohos-issue / gitee /
   partner) must have evidence_type ∈ {demo, logs, both}
   -- matching the **reproducibility HARD gate** of `procedural/qt-bug-report-generation.md`:
   tickets without reproducible material are not filed;
4. a Qt framework-side defect with `source` → WARN (add a minimal demo or runtime logs before filing upstream).

**The seven repro demo authoring principles** (for the project setup see `procedural/demo-generation.md`; for framework problem
analysis see `procedural/framework-issue-analysis.md` phase 1, repro demo generation):

1. **Minimal**: only the minimal code path that triggers the problem; a single-file main is preferred; strip business code,
   third-party dependencies and resources.
2. **Self-contained and buildable**: a complete ohos project; self-check the four steps before submitting -- builds, installs, launches,
   the symptom appears.
3. **Determinism first**: stable repro > intermittent; for intermittent problems state the trigger loop and the frequency (e.g. "1-2 times in 50 focus
   switches"), backed by logs.
4. **Contrast**: state "expected vs actual"; when possible, attach a contrast showing the same code behaving normally on a desktop platform (Linux/Windows),
   proving it is a platform difference and not a code bug.
5. **Clean root cause**: don't depend on third-party libraries not ported to HarmonyOS; if a dependency is unavoidable, first narrow the problem down to the smallest unit
   with isolation tests/probes (see the IMEPROBE probe method and the isolation test method).
6. **Carry diagnostic output**: build key log points (qDebug/probes) into the demo, turning "the symptom appears" into
   "the logs are readable" -- which also satisfies the logs evidence requirement.
7. **Record versions**: the README states the Qt kit source and commit, the OHOS API/device, the build commands, and the
   repro steps (consistent with the draft's "environment triple").

**Hard demo requirements for Qt framework-side problems** (`nature=defect` and `responsible ∈ qt-port /
qt-upstream`; must be checked before filing an upstream ticket; matches the deliverable spec of `procedural/qt-bug-report-generation.md`):

1. **Single-file main.cpp**: all repro logic is concentrated in **one main.cpp** -- the ohos project template
   (the QAbility glue shell) contains no business code, so the problem code is visible at a glance and can be pasted straight into the qt-bug
   report; for cross-platform defects reproducible on desktop, the same main.cpp is the desktop version (build and run directly with qmake/cmake,
   so Qt reviewers can verify quickly).
2. **Repro steps written out**: the demo comes with a README (or draft §3) giving **numbered steps down to the action level**
   (e.g. "① launch → ② click the input field → ③ type the pinyin ji continuously → ④ choose a candidate to commit") + the expected
   result of each step + the final expected vs actual. **A demo without repro steps is considered unfinished** -- the editor/
   upstream can only confirm the repro by following the steps one by one.

**The degraded path without a demo**: when a demo truly can't be produced (intermittent, depends on specific hardware/accounts, system-level windows)
→ the `logs` evidence must include the full "logs + stack + collection environment" triple, and the C page body states "no demo, classified from the
logs"; the editor may ask for more during review.

### Direct entry procedure (by the maintainer)

1. **Find/create the symptom S first**: search `_registry.md` §Symptom index by behavior -- if an S exists, reuse it
   (one symptom with several causes is common); otherwise append a record to `_data/symptoms.yaml`.
2. **Locate the cause C**: search the existing C (for the same root cause with several symptoms, just add an edge; **no duplicate pages**); only for a genuinely new
   root cause copy `_template.md` to create a C page with the next CID.
3. **Classify the nature**: defect / limitation / undetermined; a limitation must have either a W (alternative)
   or an evolution.
4. **Register the workaround W**: append to `_data/workarounds.yaml` (with retire_when); write the detailed steps in the
   C page body and point W.detail to them.
5. **Register the tracking ticket T**: for anything filed upstream, append to `_data/tickets.yaml` (number/link/status);
   Qt ticket numbers look like QTBUG-xxxxxx; on the Huawei side, record by tracker type.
6. **Connect edges + backfill**: S.causes / W.targets / T.tracks are written in their own source files; C page depends_on
   only when evidenced; add `fault-C-XXXX` to the `refs` of the related problems/semantic pages.
7. **Run `python tools/faults-build.py build`**: the derived artifacts are rebuilt; **ERRORs reported by check must be fixed first**
   (full validation of IDs/enums/edges/dates/refs/limitation evidence, etc.).
8. **Don't make things up**: if a version number, ticket number or date is uncertain, write "not recorded" or leave it empty.

**No nodes for**: environment configuration errors; pure environment installation problems.
**Application usage issues** ("wrong usage"/bugs in the application itself): a **thin C page** may be created (`responsible=app` →
disposition = Application usage issue) -- complete frontmatter, a lean body (root cause = the point of misuse, fix_route = change the usage),
with the in-depth content left in the problems page; the goal: make "this is not a framework problem" a searchable, reviewable conclusion.
**Orphan symptoms**: a behavior whose root cause hasn't been located can get an S first (causes empty for now) to drive further analysis.

### Collaborative draft mode (contributor submits → editor merges)

The maintainer enters things directly per the procedure above; **contributors** (team members, or issues on the public repo transcribed by the maintainer)
go through the draft channel: `faults/_drafts/draft-YYYYMMDD-slug.md` (the template is the submission checklist, see
`_drafts/_template.md`). The draft format is loose and **doesn't consume S/C/W/T ids** -- numbering and splitting into the four entities are done by
the editor at merge time; `check`/`build` don't validate `_drafts/` (files with a `_` prefix are templates/notes, not drafts).

**Contributor submission checklist** (drafts missing required items are sent straight back by the editor):

| Level | Content |
|------|------|
| Required | ① **Verbatim symptom**: error messages/key log lines (not paraphrased) + trigger/repro steps + date and scenario first seen |
| Required | ② **Environment triple**: Qt version and kit source (commit/installer) / OHOS API·system·device / build method |
| Required* | ③ **Evidence (the problem confirmation gate, see §6, evidence standard)**: a repro demo (required for defect/undetermined behavior anomalies, written per the seven principles) **or** debug logs + stack (hilog / cppcrash·jscrash faultlog / probe logs / verbatim build errors) -- *for limitations (specification/deprecation), official documentation/specification links instead |
| Required | ④ **Duplicate check statement**: checked `problems/_lookup.md` (errors) and `_registry.md` §Symptom index (symptoms), with the conclusion |
| Suggested | ⑤ preliminary root cause (source location/log inference) ⑥ workaround and its cost ⑦ upstream ticket number/link ⑧ attachments (faultlog/screenshots) ⑨ self-assessed severity |

**The editor's merge gate** (six steps, all leaving a trace; "the repro demo must be tested + human review" is a hard requirement):

1. **Duplicate check**: the symptom/cause already has an S/C → send back to be rewritten as "a supplement to the existing node" (add an edge/a W/a T/a verification
   record), **no duplicate pages**;
2. **Repro test** (graded by nature):
   - `defect` / `undetermined` (behavior anomalies): **must test** -- build and run the draft demo and confirm the symptom
     exists. The demo doesn't build → `returned` (send back to fix the demo); it builds and runs but the symptom doesn't appear →
     `returned` (send back for more environment information; **not merged unless reproduced**);
   - `limitation` (specification/deprecation): verify the official documentation/specification link and applicable versions (demo optional);
3. **Human verification**: the root cause evidence chain (source references are accurate/logs support it), the nature classification, the responsible layer,
   severity calibration, version/date/ticket-number facts (leave blank rather than invent), W usability and retire_when,
   **sanitization** (public edition: company/project names, internal paths, consistent with `audience: public`);
4. **Repro trace**: the **first row** of the merged C page's "Version verification log" **records the editor's reproduction** (date/environment/
   action = reviewed and reproduced the demo/conclusion); a contributor's workaround verified by the editor is recorded as `tested`, unverified
   as `proposed`;
5. **promote**: split the draft → S/C/W/T source-of-truth records (assign ids) → delete the draft file
   (git history + the verification log are the archive); rejected/returned drafts are kept with
   `reviewer`/`review_result` filled in;
6. **build gate**: `python tools/faults-build.py build` (zero ERRORs) + backfill `fault-C-XXXX` into the `refs` of the related
   problems/semantic pages.

**Draft state machine** (the draft frontmatter `status`, independent of the four entities' state machines):

```
draft (newly submitted) → in-review (under the editor's review) → promoted (merged, file deleted)
                                    ├→ returned (sent back: missing required items/demo doesn't build/repro failed/duplicate found)
                                    └→ rejected (not accepted: a bug in the app itself/wrong usage/duplicate; the file is kept to prevent resubmission)
```

## 7. Automatic evolution (tool: `tools/faults-build.py`)

| Command | What it does |
|------|------|
| `python tools/faults-build.py build` | Validate the sources of truth → rebuild `_graph.yaml` + `_registry.md` (including the reverse-lookup index and aggregate overview); refuses to generate if there are ERRORs |
| `python tools/faults-build.py check` | Consistency gate (exit 1 = has ERRORs): ID format/uniqueness, enums, edge targets exist, required C page fields and file names, date format, fault-* in refs exist, limitation evidence, **evidence standard** (defect may not use docs, limitation restricted to docs/source/logs, a defect with a tracked upstream ticket must have demo/logs/both, warning for Qt-side source) |
| `python tools/faults-build.py review` | Review scan: lists due/overdue entries by review_due + review focus + carried workarounds + tickets + status progression reminders + **list of drafts awaiting review (_drafts/)** |
| `python tools/faults-build.py all` | build + check |

**Status progression lint (WARN; humans decide the facts, the tool only reminds)**:

- C.status=workaround but no tested/adopted W → reminder;
- C.status=reported but no tracked T → reminder;
- T is fixed/released but C hasn't advanced to fix-confirmed → **reminder to advance**;
- T.released but fix_version empty → ERROR;
- S.status=mitigated but no adopted W / released T behind it → reminder;
- a Qt framework-side defect with only source evidence → reminder to add a demo/logs (required before filing upstream).

**Review triggers** (any of): a Qt OHOS SDK / harmonyos branch update (the root document's validation baseline table is bumped);
a HarmonyOS SDK / DevEco update; the quarterly routine `review` run finds due entries.

**Review actions**: verify per `procedural/framework-fix-verification.md` → append the result to the C page's
"Version verification log" → update C.status / T.status / W.status (retired) / S.status →
rebuild with `build` → once a defect is `verified`, carry out the **retirement steps** (remove the application-side workaround, add a
"fixed in version X" note to related pages, set W to retired) → `closed`.

**Upgrade check**: before switching Qt/OHOS versions, check `_registry.md` §By version baseline -- the causes still active on the target version
+ the list of W that must be carried along.

**Reclassification** (undetermined → defect/limitation): the CID stays the same; append the evidence to the C page's "classification basis",
and `build` syncs the nature field in `_graph.yaml`.

## 8. Indexes and links

- `_registry.md` (derived artifact): the symptom index main entry (with the **closure gap column**) / **Not closed (chain completeness to be filled)** / **By disposition (Must adapt for HarmonyOS · Qt issue · System issue · Application usage issue...)** /
  defects / undetermined / limitations / W list / T list / relationship overview / by version baseline / reviews due / resolved.
- `_graph.yaml` (derived artifact): the machine-readable full graph (nodes + edges + aggregates + reverse-lookup index, one file, one load;
  parser `tools/qt_ohos/yaml_lite.py`).
- `_design.html`: a one-page design overview diagram of the fault base (for presentation; not a knowledge page; not touched by build).
- Index layer: `_map.md`, `_dashboard.md`, `_task-routing.md` (routing code **[R]**) are hooked up;
  `_tags.md` picks up the C page tags when the indexes are regenerated.
- Machine-layer extension: when a `knowledge/errors/QOH*.yaml` matches and a related C exists, the diagnostic output can append
  "known root cause C-XXXX (nature), workaround in W-xxxx"; the C page registers it in reverse with `qoh: [QOH001]`.
- Upstream issues are produced via `procedural/qt-bug-report-generation.md`; after filing, backfill the T record.
- Collaboration entry point: contributors to the public repo provide, via an issue, the same checklist information as `_drafts/_template.md`; the maintainer
  transcribes it into a draft that goes through §6, collaborative draft mode (see `CONTRIBUTING.md`).
