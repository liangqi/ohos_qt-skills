---
id: episodic-quit-deadlock-tsfn
type: episodic
domain: postmortem
tags: [bug, quit, deadlock, TSFN, ThreadSafeFunction, handleAbilityOnDestroy, Promise, N-API, HarmonyOS]
created: 2026-06-09
updated: 2026-07-13
status: active
audience: public
refs: [semantic-qt-harmonyos-lifecycle]
summary: >
  Exit deadlock retrospective: <STAKEHOLDER> (<PRODUCT>) hangs for ~2 minutes after qApp->quit().
  Root cause: HarmonyOS doesn't process N-API ThreadSafeFunction callbacks during the Ability destruction phase,
  so qWindowDestroyPromise's resolve callback is never executed and the Promise never resolves.
  Fix: an external patch bypasses the TSFN mechanism using an atomic variable + parallel polling; verified effective.
  Related confirmation: the sensor plugin triggers a crash during the exit flow, and a partner confirmed that removing it avoids the issue (2026-07-13).
---

# Exit deadlock: the handleAbilityOnDestroy Promise never resolves after qApp->quit()

## Problem overview

| Item | Details |
|------|---------|
| External party | <PRODUCT> |
| Symptom | After calling `qApp->quit()`, the application hangs for about 2 minutes before exiting |
| Qt version | 5.12.12 (tqtc/harmonyos-5.12.12, commit 613336de) |
| Device | A real device |
| Root cause | The HarmonyOS ArkTS runtime doesn't process TSFN callbacks during the Ability destruction phase |
| Fix | An external patch: an atomic variable + parallel polling, bypassing TSFN |

## Timeline

| Date | Phase | Output |
|------|-------|--------|
| 2026-06-05 | Received the external report | An initial triage plan (TROUBLESHOOTING_GUIDE.md) |
| 2026-06-05 | The root cause the external party confirmed | A WINDOW_DESTROYED timing problem + patch code |
| 2026-06-08 | In-depth log analysis | Confirmed that TSFN callback blocking is the real root cause |
| 2026-06-08 | Demo reproduction | Reproduced exactly with a heap-allocated QApplication (never deleted) |
| 2026-06-09 | Deliverables assembled | <WORK_DIR>/quit-deadlock/ (ISSUE.md + patch + demo) |

## Root cause analysis

### The surface symptom

After `main()` returns, `handleAbilityOnDestroy` returns a Promise to the ArkTS framework, but the Promise never resolves, so the ArkTS framework's await times out (~2 minutes).

### The initial misdiagnosis

We initially believed the root cause was **QApplication not being destructed properly** (heap-allocated and never deleted), so the `QOhosView::destroyed` signal never fired and `qWindowDestroyPromise` stayed pending forever.

**Correction**: even when `delete app` runs before `main()` returns — so QOhosView is destructed correctly, the destroyed signal fires, and `resolveQWindowDestroyPromiseFunc` is called — **the resolve is still dispatched to the JS thread through `Napi::ThreadSafeFunction::NonBlockingCall()`**. And HarmonyOS doesn't process those TSFN callbacks during the Ability destruction phase.

### The real root cause

```
qApp->quit()
  → the Qt event loop exits → main() returns
  → exit handler: invokeInJsThread(terminateAllAbilityInstances)
  → JS thread: context.terminateSelf → the system starts destroying the Ability
  → system: onDestroy → handleAbilityOnDestroy
  → handleAbilityOnDestroy obtains qWindowDestroyPromise
  → initialPromise.onFinally(callback) is registered
  → returns resultPromiseDeferred->Promise() → ArkTS awaits it

  ★ The deadlock point:
    qWindowDestroyPromise's resolve is dispatched through TSFN
    → the ArkTS runtime doesn't process TSFN callbacks while awaiting
    → deferred.Resolve() is never executed
    → initialPromise stays pending forever
    → onFinally never fires
    → resultPromise never resolves
    → ArkTS times out → AbilityStage::onDestroy → _Exit(0)
```

### The key log evidence

```
19:07:35.002  [JS thread]  handleAbilityOnDestroy → returning Promise for id='0'
19:07:35.003  [JS thread]  Tagging JS Window as closing (from: WINDOW_DESTROYED)
    ⚠️ No Qt framework logs at all for the next 2 minutes 10 seconds
    ❌ "initial Promise resolved" — never appears
    ❌ "Qt: requested Qt app quit" — never appears
    ❌ "Qt: end waiting" — never appears (the 5-second timeout mechanism never starts)
19:09:45.013  [JS thread]  QAbilityStage::onDestroy()
19:09:45.035  [JS thread]  AbilityStage::onDestroy: calling _Exit(0)
```

## How to reproduce

**Core design**: heap-allocate QApplication and never delete it.

```cpp
int main(int argc, char *argv[]) {
    auto *app = new QApplication(argc, argv);  // heap-allocated, never deleted
    // ... create the main window ...
    QTimer::singleShot(5000, []() { qApp->quit(); });
    mainWindow->show();
    int ret = app->exec();
    // app is never deleted
    return ret;
}
```

**Key finding**: `delete app` **does not fix** this problem. The resolve callback is dispatched through TSFN and blocked by the ArkTS runtime, regardless of whether QApplication is destructed.

## The fix

### The external patch (verified effective)

**Core idea**: bypass TSFN and detect the Qt thread's state directly with an atomic variable + parallel polling.

1. Add `std::atomic_bool s_qtAppThreadIdle{true}`
2. Set it to `false` when `main()` starts and `true` when `main()` returns
3. In `handleAbilityOnDestroy`:
   - If `s_qtAppThreadIdle.load() == true` → go straight to `continueDestroyFlow`
   - Start a parallel polling task: a separate thread checks every 100 ms, and when Qt is idle → `continueDestroyFlow`
4. `continueDestroyFlow` uses `compare_exchange_strong` to prevent running twice

### Why it works

- It doesn't rely on TSFN callbacks (bypassing the blocked channel)
- Atomic variables are safe across threads and don't need the JS thread to do anything
- The parallel polling runs on a separate thread, unaffected by the ArkTS runtime

## Lessons learned

1. **Don't assume `delete app` solves every exit problem** — the root cause may be lower-level runtime behavior
2. **What's *missing* from a log can be more diagnostic than what's present** — the absence of three key log lines pointed straight at the deadlock
3. **Cross-thread communication mechanisms (TSFN) can stop working during specific system lifecycle phases** — this is a HarmonyOS-specific limitation
4. **A reproduction demo must match the real scenario exactly** — a stack-allocated QApplication doesn't reproduce it; it must be heap-allocated
5. **Deliverables submitted to Tqtc must include a demo that reproduces the problem** — now an iron rule in the workflow

## Related crash confirmation: the sensor plugin triggers a crash during the exit flow

> Confirmed with a partner on 2026-07-13. Like the quit-deadlock above, it's a problem on the exit path during the Ability destruction phase, so it's captured on this page.

| Item | Details |
|------|---------|
| External party | The same partner as the quit-deadlock above |
| Symptom | A crash during the application's exit flow |
| Root cause | A sensor plugin integrated into the application (origin unconfirmed: the Qt Sensors module backend / the partner's own / third-party — not investigated further) crashes during the exit phase |
| Verification | The partner confirmed: removing the sensor plugin makes the crash disappear |
| Confirmation date | 2026-07-13 |

### Conclusion

Confirmed with the partner: **the crash stops once the sensor plugin is removed**.

- The crash occurs in the application's exit flow, in the same high-risk exit window (the Ability destruction phase) as the quit-deadlock above
- The quit-deadlock already showed that HarmonyOS doesn't pump TSFN callbacks during Ability destruction, and several normally-working paths fail or misbehave in that window; a crash triggered by the sensor plugin in that window is the same class of exit-phase problem
- The sensor plugin's exact origin wasn't investigated further — removing it avoids the issue, and the partner accepted that solution

### To do (if the sensor functionality needs to be kept)

- Investigate the specific mechanism by which this sensor plugin crashes during the exit phase: destruction order / leftover TSFN callbacks / backend hardware resource release timing, following this page's exit-path analysis
- The exit phase is a high-risk window on HarmonyOS + Qt: any plugin that dispatches callbacks, crosses threads, or releases dynamic resources should be handled defensively in that window (following this page's "atomic variable + parallel polling to bypass TSFN" approach)

## Deliverables

```
<WORK_DIR>/quit-deadlock/
├── ISSUE.md              # Bilingual (Chinese/English) root cause analysis
├── patches/
│   └── 0001-*.patch      # The external patch (git diff format)
├── demo/
│   ├── ohos-repro/       # The complete OHOS project (buildable and deployable)
│   └── qt-repro/         # The desktop version (for code review)
└── README.md             # Deliverables overview
```

## Related context

- The framework issue analysis workflow
- [[qt-harmonyos-lifecycle]] — Lifecycle in detail
- External logs: `<log-dir>/destroyError20260608_*.log`
- Demo source: `<demos-dir>/quit-signal-repro/`
