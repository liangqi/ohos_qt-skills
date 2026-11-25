---
id: fault-C-0004
cid: C-0004
type: cause
title: The Ability destroy window doesn't process N-API TSFN callbacks (the Promise resolve channel is blocked)
nature: undetermined
domain: lifecycle
fault_type: hang
responsible: ohos-runtime
co_responsible: []
component: "HarmonyOS ArkTS runtime × N-API ThreadSafeFunction (Ability destroy window)"
severity: critical
evidence_type: both
status: reported
fix_route: "If classified as defect: the system side processes/drains TSFN callbacks during the destroy window; if classified as limitation: W-0003 becomes the long-term solution"
review_note: "Reply from the partner/system side; TSFN behavior in the destroy window on new system versions; reclassification (the CID stays the same)"
depends_on: []
affects_qt: ["Qt 5.12.12 (613336de)"]
affects_ohos: ["real device (system version not recorded)"]
qoh: []
first_seen: 2026-06-05
review_due: 2026-12-14
created: 2026-09-14
updated: 2026-09-14
tags: [qt, harmonyos, quit, deadlock, TSFN, ThreadSafeFunction, N-API, Promise, handleAbilityOnDestroy, workaround]
audience: public
refs: [episodic-quit-deadlock-tsfn, semantic-qt-harmonyos-lifecycle]
summary: >
  qWindowDestroyPromise's resolve is posted through a TSFN, but HarmonyOS doesn't process TSFN callbacks
  during the Ability destroy phase, so the Promise never resolves and the ArkTS await falls back on a timeout (hangs ~2 minutes).
  nature undetermined (leaning limitation: system behavior that Qt can't permanently fix); reclassify once the system side classifies it;
  workaround W-0003 (polling patch) is verified, tracking ticket T-0001 (partner deliverable) is submitted.
---

# C-0004 The Ability destroy window doesn't process TSFN callbacks

> nature: undetermined (leaning limitation) | responsible: ohos-runtime | status: reported | symptoms: S-0004 | review: 2026-12-14

## Symptoms

### S-0004 Exit hangs for about 2 minutes after qApp->quit() (the Promise never resolves)

After calling `qApp->quit()`, the app hangs for about 2 minutes before exiting. Log signature: after `handleAbilityOnDestroy`
returns the Promise there are **2 minutes 10 seconds without any Qt framework log**, "initial Promise resolved" never appears,
and finally `AbilityStage::onDestroy → _Exit(0)` exits as a fallback.

## Root cause / classification basis

```
qApp->quit() → Qt event loop exits → main() returns
  → invokeInJsThread(terminateAllAbilityInstances) → context.terminateSelf
  → system onDestroy → handleAbilityOnDestroy returns resultPromise → ArkTS await
  ★ qWindowDestroyPromise's resolve is posted via Napi::ThreadSafeFunction::NonBlockingCall()
  ★ the ArkTS runtime doesn't process TSFN callbacks during the await → deferred.Resolve() never runs
  → the Promise stays pending forever → ArkTS waits until timeout (~2 minutes)
```

Note: `delete app` does **not** fix it -- the resolve callback goes through the blocked TSFN channel, which has nothing to do with whether QApplication
is destroyed (verified with an exact repro demo using heap allocation / no delete).

**Classification status**: the system behavior is established empirically; "is this a defect or by design" has no official classification yet.
Leaning `limitation` (not pumping TSFN in the destroy window looks like a runtime design constraint) -- reclassify after the system side replies;
the CID stays the same.

## Responsibility

`ohos-runtime` -- the ArkTS runtime doesn't pump TSFN callbacks in the Ability destroy window; this is system runtime
behavior that Qt can't permanently fix, only work around. A fix (if classified as defect) arrives with a system/SDK version.

## Permanent fix (if classified as defect)

System side: keep processing (or drain) TSFN callbacks during the Ability destroy await window.

## Alternatives and evolution (if classified as limitation)

The W-0003 polling patch becomes the long-term solution; any plugin that posts callbacks / crosses threads / releases dynamic resources during the exit phase
gets defensive handling (following the "atomic variable + parallel polling" approach).

## Workarounds

- **W-0003 (adopted, verified 2026-06-09 on a real device)**: bypass the TSFN --
  1. `std::atomic_bool s_qtAppThreadIdle{true}` (set to false on entering `main()`, true on return);
  2. in `handleAbilityOnDestroy`: if Qt is already idle, call `continueDestroyFlow` directly; otherwise a separate thread
     polls every 100ms and triggers it once idle;
  3. `continueDestroyFlow` uses `compare_exchange_strong` to prevent reentry.

  For the full implementation see [quit-deadlock-tsfn](../episodic/postmortems/quit-deadlock-tsfn.md).
  Retirement condition: once the HarmonyOS version in use is confirmed to process TSFN in the destroy window, remove the polling patch and rerun
  the exit regression tests.

## Tickets

- **T-0001 (partner, submitted 2026-06-09)**: deliverable of ISSUE.md (root cause in Chinese and English) + patches/ +
  ohos-repro/qt-repro reproducible demos (`<WORK_DIR>/quit-deadlock/`; internal path in the
  postmortem page); awaiting classification by the system side.
- Related confirmation (2026-07-13): in the same destroy window, the sensor plugin triggers a crash, avoided by removing it -- also an
  issue of the high-risk Ability destroy exit window (mechanism not investigated in depth; open a new case if sensor functionality must be kept).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-06-08 | Qt 5.12.12 / real device | Exact repro with a heap-allocated QApplication demo | Reproduced; pinned down the TSFN blocking | → diagnosed |
| 2026-06-09 | Qt 5.12.12 / real device | Atomic variable + parallel polling patch | Exits normally, no more hang | → workaround |
| 2026-06-09 | — | ISSUE + patch + demo delivered to the partner (T-0001) | Reported | → reported |

## Related

- Symptoms (S): S-0004
- Workarounds (W): W-0003
- Tickets (T): T-0001
- episodic: [quit-deadlock-tsfn](../episodic/postmortems/quit-deadlock-tsfn.md)
  (full timeline, patch implementation, log evidence)
- semantic: [qt-harmonyos-lifecycle](../semantic/qt-harmonyos-lifecycle.md)
