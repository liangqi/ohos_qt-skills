---
id: fault-C-XXXX
cid: C-XXXX
type: cause
title: <one-sentence cause title (state the cause, not the symptom)>
nature: defect            # defect (will be fixed → T tracking + fix_route) / limitation (by specification → W alternative + evidence/evolution) / undetermined
domain: runtime           # build/deploy/runtime/render/api/input/lifecycle/toolchain/filesystem
fault_type: bug           # bug/crash/build-blocker/hang/gap/regression/caveat/deprecation
responsible: undetermined # qt-port/qt-upstream/ohos-runtime/ohos-toolchain/ohos-ndk/third-party/app/undetermined
co_responsible: []        # optional: the secondary party in combined responsibility
component: "<component/file>"
severity: medium          # blocker/critical/high/medium/low
# Evidence standard in _index §6: defect may not use docs; source only for statically decidable issues;
# Qt framework-side source gets a WARN (add a demo/logs before filing upstream)
evidence_type: logs
status: open              # open/diagnosed/workaround/reported/fix-confirmed/verified/wontfix/watching/closed
fix_route: "<defect: the fix route in one sentence>"
evidence: "<limitation: classification evidence (official docs / empirical platform behavior)>"
evolution: "<limitation: evolution direction and watch points>"
review_note: "<review focus (used by the review output)>"
depends_on: []            # other C nodes this cause's resolution depends on (only when evidenced; no speculative edges)
affects_qt: []            # aligned with the root document's validation baseline; if unsure write "not recorded"
affects_ohos: []
qoh: []                   # optional: related machine-layer error patterns
first_seen: YYYY-MM-DD
review_due: YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
audience: public
refs: []
summary: >
  <One sentence: cause + nature + responsibility + current status + whether there is a W/T.>
---

# C-XXXX <cause title>

> nature: defect | responsible: qt-port | status: open | symptoms: S-XXXX | workarounds: W-XXXX | tickets: T-XXXX | review: YYYY-MM-DD

## Symptoms

### S-XXXX <symptom title>

<The detailed observable behavior of this symptom: verbatim error messages, key log lines, trigger conditions. The symptom itself is a thin record
(_data/symptoms.yaml); the details go here.>

## Root cause / classification basis

<defect: source-level/log-level evidence chain; limitation: specification evidence; undetermined: known boundaries and open classification questions.>

## Responsibility

<Why it belongs to this responsible party; the fix route (which release brings it to you); notes on combined responsibility.>

## Permanent fix (defect)

<The upstream fix / suggested patch; if none, the direction to wait for.>

## Alternatives and evolution (limitation)

<Expand the alternatives referencing W-xxxx; evolution direction and watch points. Delete this section for defect nodes.>

## Workarounds

- **W-XXXX (status, verified date env)**: <the workaround in detail + cost + retirement condition>.

<The workaround record itself lives in _data/workarounds.yaml (targets point to this C); write the detailed steps here,
and W.detail points to this section.>

## Tickets

- **T-XXXX (tracker, number, status)**: <nature of the ticket / summary of replies / fix_version>.

<The ticket record itself lives in _data/tickets.yaml (tracks point to this C); fix_version is required once released,
and build aggregates it into C.fixed_in in _graph.yaml.>

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
|      |                |      |      |         |

## Related

- Symptoms (S):
- Workarounds (W):
- Tickets (T):
- problems / semantic / episodic:
- QOH (machine layer):
- Related causes (C, including depends_on notes):

---

<!-- Entry procedure (faults/_index.md §6):
     ① find/create the S (_data/symptoms.yaml) ② find/create the C (don't create duplicate pages) ③ classify the nature
     ④ register the W (_data/workarounds.yaml, with retire_when) ⑤ register the T (_data/tickets.yaml)
     ⑥ connect the edges (S.causes/W.targets/T.tracks are written in the source files; C.depends_on only when evidenced)
     ⑦ python tools/faults-build.py build (fix ERRORs first)
     ⑧ backfill fault-C-XXXX into the refs of related pages. Leave uncertain fields empty; don't make things up. -->

<!-- S record template (append to _data/symptoms.yaml):
  - id: S-XXXX
    title: "the symptom in one sentence (lookup anchor)"
    domain: input
    severity: high
    status: active            # active/mitigated/resolved
    causes: [C-XXXX]          # with multiple causes add cause_relation: all_of|any_of (default any_of)
    first_seen: YYYY-MM-DD
    refs: [problem-xxx]
-->

<!-- W record template (append to _data/workarounds.yaml):
  - id: W-XXXX
    title: "the workaround in one sentence"
    targets: [C-XXXX]
    status: proposed          # proposed/tested/adopted/retired
    cost: "the cost in one sentence"
    verified:
      date: YYYY-MM-DD
      env: "verification environment"
    retire_when: "retirement condition (what to undo after the official fix/migration)"
    detail: "C-XXXX-slug.md §Workarounds"
-->

<!-- T record template (append to _data/tickets.yaml):
  - id: T-XXXX
    tracker: qt-bug           # qt-bug/ohos-issue/gitee/partner/forum/upstream
    number: "QTBUG-xxxxxx"
    url: "https://..."
    tracks: [C-XXXX]
    status: submitted         # draft/submitted/accepted/dup/wontfix/fixed/released/closed
    filed: YYYY-MM-DD
    fix_version: ""           # required from released on (e.g. "Qt 6.12-beta4", "API 25")
    fix_commit: ""
    last_update: ""
    notes: "nature of the ticket / summary of replies"
-->
