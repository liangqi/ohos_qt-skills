---
id: fault-C-0003
cid: C-0003
type: cause
title: Detach→Attach race at the moment of an IME focus switch commits the first character to the old focus object
nature: defect
domain: input
fault_type: bug
responsible: qt-port
co_responsible: []
component: "Qt 6.12-beta3 libqohos qohosinputcontext.cpp (focus switch timing)"
severity: medium
evidence_type: logs
status: open
fix_route: "Same component as C-0002; submit together with its fix (check the focus object's ImEnabled before commit)"
review_note: "Verify together with C-0002 (next Qt 6.12 kit)"
depends_on: []
affects_qt: ["Qt 6.12-beta3 (libqohos)"]
affects_ohos: ["HarmonyOS PC (Huawei IME)"]
qoh: []
first_seen: 2026-09-12
review_due: 2026-12-14
created: 2026-09-14
updated: 2026-09-14
tags: [qt, harmonyos, ime, focus, detach, attach, race, lost-character, bug]
audience: public
refs: [fault-C-0002, problem-runtime-ohos-ime-reset-detach]
summary: >
  At the moment of a focus switch (Detach→Attach race) the first letter is committed to the old focus object (the new field is not yet
  connected), showing up as an occasionally lost first character. defect, provisionally qt-port; not fully located (probe timing evidence, no source-level
  isolated repro), no workaround.
---

# C-0003 Detach→Attach race at the moment of an IME focus switch

> nature: defect | responsible: qt-port | status: open | symptoms: S-0003 | review: 2026-12-14

## Symptoms

### S-0003 First character occasionally lost after switching focus between input fields

Intermittent: the first character typed after an input field gains focus is lost. IMEPROBE probe timing evidence: at the moment of the focus switch,
`previewText raw=[j]` is immediately followed by `commit pending=[j]` -- the first letter is committed to the **old**
focus object (at that moment `pushText left=[]` is empty; the new field is not connected yet).

## Root cause / classification basis

Detach→Attach race: the commit target focus object and the IMF callback timing are out of sync.
**Not fully located** (timing evidence captured; no source-level isolated repro yet).

## Responsibility

Provisionally `qt-port` (both the component and the race are inside the IME bridge of the Qt ohos plugin; if it later turns out to be an IMF callback timing
problem, reclassify as ohos-runtime; the CID stays the same).

## Permanent fix (defect, approach)

Before commit, check the focus object's ImEnabled query result; if it doesn't match, discard or buffer the text for later delivery.

## Workarounds

- None (the user retypes the lost character).

## Tickets

- Not reported. Same component as [C-0002](C-0002-ime-reset-detach.md); suggest combining them into one issue
  and filing them together.

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-09-12 | Qt 6.12-beta3 / HarmonyOS PC | IMEPROBE probe timing observation | Captured timing evidence of the lost first character | → open |

## Related

- Symptoms (S): S-0003
- Workarounds (W): none
- Tickets (T): none yet
- problems: [runtime-ohos-ime-reset-detach](../problems/runtime-ohos-ime-reset-detach.md)
  §Known unfixed issue
- Related causes (C): [C-0002](C-0002-ime-reset-detach.md) (same component; the main bug is fixed locally)
