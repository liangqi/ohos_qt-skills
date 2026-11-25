---
id: fault-C-0011
cid: C-0011
type: cause
title: theMainThread and QCoreApplication::instance()->thread() point to different QThreads (the QtMainThread thread-local is cleared and rebuilt)
nature: undetermined
domain: runtime
fault_type: crash
responsible: undetermined
co_responsible: []
component: "qtbase corelib qcoreapplication.cpp (sendThroughApplicationEventFilters Q_ASSERT / theMainThread) × qthread_unix.cpp QThreadData::current() × OHOS QPA qohosjsmain.cpp (QtMainThread creation and init lambda)"
severity: high
evidence_type: source
status: diagnosed
fix_route: "If classified as app: document the main() constraint; if classified as qt-port: QPA constructor checks theMainThread==currentThread + better guard logging; if classified as ohos-runtime/ohos-ndk: fixed with a system or NDK release"
review_note: "The three hypotheses for the trigger path are unresolved (app calls Qt APIs before QApplication / Qt internally clears the thread-local / OHOS thread_local behavior); reclassify after adding probe logs (the CID stays the same); evidence is source location only, demo/logs are required before filing or reclassifying; Release builds don't crash, so it is easily under-reported"
depends_on: []
affects_qt: ["Qt 5.15.16 (tqtc/harmonyos-5.15.16)"]
affects_ohos: ["not recorded (partner-reported case; device/system version not kept)"]
qoh: [QOH028]
first_seen: 2026-06-13
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [qt, harmonyos, threading, qcoreapplication, Q_ASSERT, theMainThread, QtMainThread, thread-local, dual-thread, debug-build, undetermined]
audience: public
refs: [problem-ohos-mainthread-mismatch, semantic-qt-harmonyos-overview]
summary: >
  In Debug builds, a mouse click event triggers a Q_ASSERT in QCoreApplicationPrivate::sendThroughApplicationEventFilters:
  theMainThread (set to QAdoptedThread_A by the first QThreadData::current() in the init lambda) and
  QCoreApplication::instance()->thread() (QAdoptedThread_B) point to different QThreads, showing that the QtMainThread's
  thread-local currentThreadData was cleared and rebuilt in between; the trigger has not been located. undetermined (three hypotheses: app misuse /
  qt-port thread defense / ohos-runtime thread_local); the mechanism is located in the source (diagnosed), W-0009 (QApplication-first
  constraint) is only proposed, no tracking ticket.
---

# C-0011 theMainThread doesn't match instance()->thread()

> nature: undetermined | responsible: undetermined | status: diagnosed | symptoms: S-0010 | workarounds: W-0009 (proposed) | tickets: none yet | review: 2026-12-15

## Symptoms

### S-0010 QWidget app Debug build crashes on mouse click (sendThroughApplicationEventFilters Q_ASSERT)

- Crashes when dispatching mouse click/touch events, triggering `Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread())` (`QCoreApplicationPrivate::sendThroughApplicationEventFilters()`, qcoreapplication.cpp:1160);
- Debug builds always crash, Release builds don't (the Q_ASSERT is compiled out -- the problem is masked and easily under-reported);
- printing `QThread::currentThread()`, the event-sending thread and the receiving thread, they **all appear to be** the Qt main thread; but `mainThread()` (theMainThread=QAdoptedThread_A) is **not equal to** `QCoreApplication::instance()->thread()` (QAdoptedThread_B);
- scope: all QWidget apps (Debug builds); an actual crash case reported by a partner.

## Root cause / classification basis (source-level call chain; mechanism located, trigger path undetermined)

Mechanism:

```
OHOS dual-thread model: ArkTS UI thread (lifecycle/NAPI callbacks) + QtMainThread (Qt event loop/user main())
  → SingleThreadExecutor creates "QtMainThread" (qohossinglethreadexecutor.cpp:108-135)
  → the init lambda runs QThread::currentThread() on QtMainThread
    → the first QThreadData::current() sets theMainThread = QAdoptedThread_A (qthread_unix.cpp:224-225)
  → user main() runs on QtMainThread → QApplication construction → QObject → QThreadData::current()
  → normally: returns the same QAdoptedThread_A (instance()->thread() == theMainThread ✓)
  → actually: returns QAdoptedThread_B ≠ theMainThread
    → shows that the thread-local currentThreadData was cleared and rebuilt between the init lambda and QApplication construction
  → event dispatch: the guard in notify_helper (:1213) passes, but the Q_ASSERT in sendThroughApplicationEventFilters
    (:1160) fails -- the two checks differ only in memory order, so in a normal single-thread scenario one can't pass while the other fails
```

Three hypotheses for the trigger path (all unresolved):

1. The user calls some Qt APIs in main() **before** constructing QApplication (calls such as `qDebug`, QObject/QSettings construction, `QThread::currentThread()` that trigger `QThreadData::current()`) -- the partner **has confirmed their code does this**, but it hasn't been verified that removing them makes the crash go away;
2. some Qt internal initialization path unexpectedly clears/rebuilds the thread-local data;
3. behavior differences of the OHOS/musl `thread_local` implementation in particular scenarios.

Classification status: the mechanism is located in the source; **nature and responsibility are undetermined** -- reclassify once the evidence is in; the CID stays the same.

Evidence form: `source` (source file:line call chain analysis + the verbatim Q_ASSERT from the partner-reported crash case); **no archived faultlog stack, no minimal repro demo** -- the diagnostic steps in the problem page (three probe prints + checking calls before main()) are designed but their output was not archived. This is a runtime behavior anomaly (not statically decidable), so source is only a transitional record: demo/logs are required before filing or reclassifying.

## Responsibility

`undetermined` -- the three hypotheses map to three layers and dispositions:

| Hypothesis | If it holds | Disposition |
|------|--------|---------|
| ① app calls Qt APIs before QApplication | responsible=app | Application usage issue |
| ② Qt internal initialization clears the thread-local | responsible=qt-port / qt-upstream | Qt issue |
| ③ OHOS thread_local behavior differs | responsible=ohos-runtime / ohos-ndk | System issue |

The only established fact is "the partner confirmed there are Qt API calls before QApplication"; causality is unverified, which is not enough to assign responsibility to app. Path to reclassification: add the three probe logs per the problem page's diagnostic steps (at the assertion / in the init lambda / after QApplication construction) → pin down the caller that clears/rebuilds the thread-local → reclassify (the CID stays the same).

## Permanent fix (if classified as defect)

- Hypothesis ②: the Qt 5.15 OHOS branch checks `theMainThread == QThread::currentThread()` in the `QOhosPlatformIntegration` constructor (a defensive check); the `notify_helper()` guard is upgraded to a detailed error log instead of a direct Q_ASSERT;
- hypotheses ①③: respectively, an application-side fix / confirming the system-side thread_local behavior.

## Alternatives and evolution (if classified as a usage constraint)

If it is finally classified as "a usage constraint of the OHOS dual-thread architecture": document the main() constraint (QApplication must be the first Qt API call) and promote W-0009 to a long-term rule; land the QPA defensive check as hardening at the same time.

## Workarounds

- **W-0009 (proposed, not verified)**: make sure `QApplication` is the **first** Qt API call in main() -- before constructing QApplication, don't call any Qt API that triggers `QThreadData::current()` (`qDebug`, QObject/QSettings construction, `QThread::currentThread()`, etc.; types such as QString that don't touch thread data are safe):

  ```cpp
  int main(int argc, char *argv[])
  {
      QApplication app(argc, argv);   // the first Qt call
      // only use other Qt APIs after this
      return app.exec();
  }
  ```

  Cost: existing Qt calls before it in main() must be reordered; this targets hypothesis ①, and with the root cause undetermined it is not guaranteed to work.
  Retirement condition: once the root cause is confirmed and permanently fixed (or classified as a constraint and formally documented), drop the temporary constraint and rerun the Debug build click test.

## Tickets

- None yet. Not reported -- the evidence doesn't meet the filing gate (demo/logs must be added first).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-06-13 | Qt 5.15.16 (tqtc/harmonyos-5.15.16) / OHOS (partner-reported case, device not recorded) | Source-level call chain analysis: the guard-passes / assert-fails contradiction → the theMainThread mismatch mechanism | Mechanism located: theMainThread (QAdoptedThread_A) ≠ instance()->thread() (QAdoptedThread_B); the thread-local is cleared and rebuilt, trigger undetermined | → diagnosed |

(Source for the historical facts: [ohos-mainthread-mismatch](../problems/ohos-mainthread-mismatch.md) (created 2026-06-13, updated 2026-07-04, status: open); when the editor merges, register the review reproduction in the first row of this table per the gate.)

## Related

- Symptoms (S): S-0010
- Workarounds (W): W-0009 (proposed)
- Tickets (T): none yet
- problems: [ohos-mainthread-mismatch](../problems/ohos-mainthread-mismatch.md) (diagnostic steps, source reference table, ArkTS lifecycle → C++ callback mapping)
- semantic: [qt-harmonyos-overview](../semantic/qt-harmonyos-overview.md)
- QOH (machine layer): QOH028 (mainthread_mismatch_assert)
- Related causes (C): none
