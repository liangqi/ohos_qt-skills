---
id: problem-ohos-mainthread-mismatch
type: problem
domain: runtime
tags: [ohos, threading, qcoreapplication, assertion, qthread, mainthread, theMainThread, startup-lifecycle]
created: 2026-06-13
updated: 2026-07-04
status: open
audience: public
severity: high
error_message: "Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread()) in QCoreApplicationPrivate::sendThroughApplicationEventFilters (triggered by a mouse click in a debug build)"
refs: [fault-C-0011, semantic-qt-harmonyos-overview]
summary: >
  A mouse click on OHOS crashes on the Q_ASSERT in QCoreApplication::sendThroughApplicationEventFilters,
  because theMainThread and QCoreApplication::instance()->thread() point at different QThread objects.
  It's related to OHOS's dual-thread architecture (the ArkTS UI thread vs. QtMainThread) and Qt API calls made before QApplication is constructed.
---

# OHOS QCoreApplication::notify thread assertion crash (theMainThread mismatch)

> **Error type**: a runtime crash (a Q_ASSERT in a debug build)
> **Affected versions**: Qt 5.15 for OHOS (branch tqtc/harmonyos-5.15.16)
> **Scope**: every QWidget application (debug builds)

---

## Error message

```
Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread());
```

Crash location: `qtbase/src/corelib/kernel/qcoreapplication.cpp`, in `QCoreApplicationPrivate::sendThroughApplicationEventFilters()`.

Trigger: dispatching a mouse click (or another input event).

---

## Symptoms

1. A mouse click/touch triggers the crash
2. The Q_ASSERT fails in debug builds; release builds don't crash (Q_ASSERT is compiled out)
3. Printing `QThread::currentThread()`, the sending thread, and the receiving thread **all appear** to be the Qt main thread
4. But `mainThread()` **doesn't equal** `QCoreApplication::instance()->thread()`

---

## Root cause analysis

### The assertion failure mechanism

After the guard in `notify_helper()` passes, the Q_ASSERT in `sendThroughApplicationEventFilters()` fails:

```cpp
// the guard (qcoreapplication.cpp:1213) - passes
receiver->d_func()->threadData.loadRelaxed()->thread.loadAcquire() == mainThread()

// the assertion (qcoreapplication.cpp:1160) - fails
receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread()
```

The two checks are almost identical (differing only in the loadRelaxed/loadAcquire ordering), and in a normal single-threaded scenario the guard passing while the assertion fails should be impossible.

**The key finding**: `mainThread()` returns `QCoreApplicationPrivate::theMainThread`, which points at a **different QThread object** than `QCoreApplication::instance()->thread()`.

### How theMainThread is set

`theMainThread` is set by the **first** thread to call `QThreadData::current()` (qthread_unix.cpp:224-225):

```cpp
if (!QCoreApplicationPrivate::theMainThread.loadAcquire())
    QCoreApplicationPrivate::theMainThread.storeRelease(data->thread.loadRelaxed());
```

### The OHOS dual-thread architecture

Qt for OHOS uses a **dual-thread model**:

| Thread | Native thread name | Purpose |
|--------|--------------------|---------|
| The ArkTS UI thread | (the system default) | Runs ArkTS lifecycle callbacks and NAPI callbacks |
| QtMainThread | "QtMainThread" | Runs the Qt event loop, the user's main(), and QPA event dispatch |

**Initialization order** (the normal flow):

```
ArkTS UI thread:
  AbilityStage.onCreate()
    ↓
  Ability.onCreate() → setupQtApplication()
    ↓ setupQtApplicationImpl() registers handleDefaultQAbilityInstanceStartup
  handleAbilityOnCreate()
    ↓ handleDefaultQAbilityInstanceStartup()
    ↓ makeQtThreadWithMainFuncLauncher()
    ↓ SingleThreadExecutor creates the native "QtMainThread"
    ↓ the init lambda runs on "QtMainThread":
    ↓   QThread::currentThread() → theMainThread = QAdoptedThread_A
    ↓   initQtThreadState()
    ↓ blocks waiting for init to finish
    ↓ s_qtAppThreadMainFuncLauncher(args) → dispatches main() onto QtMainThread

QtMainThread:
  the user's main()
    ↓ QApplication(argc, argv)
    ↓ QObject construction → QThreadData::current() → thread = QAdoptedThread_A
    ↓ instance()->thread() == theMainThread ✓
    ↓ app.exec() → the event loop
```

### The crash scenario

When `theMainThread` (QAdoptedThread_A) differs from `QCoreApplication::instance()->thread()` (QAdoptedThread_B),
it means QThreadData's thread-local `currentThreadData` was cleared and recreated between the init lambda and QApplication's construction.

**Possible triggers**:
1. The user called some Qt API in `main()` **before** constructing `QApplication` (the user has confirmed this is the case)
2. Some Qt internal initialization path unexpectedly clears/recreates the thread-local data
3. Behavioral differences in the OHOS/Bionic `thread_local` implementation in certain scenarios

---

## OHOS glue-code lifecycle reference

Based on the template bundled with the Qt source (`<QT_SRC>/qtbase/src/harmonyos/templates`; the old `ohostemplateforqtapplication_*.zip` is retired):

### ArkTS lifecycle → C++ callback mapping

| Stage | ArkTS callback | C++ NAPI handler | Thread it runs on |
|-------|----------------|------------------|-------------------|
| Process startup | `QAbilityStage.onCreate()` | `handleAbilityStageOnCreate()` | ArkTS UI |
| Application initialization | `QAbilityStage.onNewProcessRequest()` | `setupQtApplication()` → `setupQtApplicationImpl()` | ArkTS UI |
| Ability creation | `QAbility.onCreate()` | `handleAbilityOnCreate()` → registers the Ability instance → `handleDefaultQAbilityInstanceStartup()` | ArkTS UI |
| Qt thread creation | (triggered internally by the previous step) | `makeQtThreadWithMainFuncLauncher()` → creates "QtMainThread" + the init lambda | **QtMainThread** |
| Window creation | `QAbility.onWindowStageCreate()` | `handleAbilityOnWindowStageCreate()` → `loadWindowStageContentPage()` | ArkTS UI |
| The user's main() | (scheduled onto the Qt thread) | `s_qtAppThreadMainFuncLauncher()` → dispatched to QtMainThread | **QtMainThread** |

### Key files

| File | Role |
|------|------|
| `entry/src/main/ets/qabilitystage/QAbilityStage.ets` | The AbilityStage entry point; calls `setupQtApplication` |
| `entry/src/main/ets/qability/QAbility.ets` | The Ability lifecycle; calls the various NAPI callbacks |
| `entry/src/main/ets/pages/MainWindowNativeNode.ets` | The main window's XComponent definition |
| `entry/src/main/ets/common/QtAppConstants.ets` | Application constants (APP_LIBRARY_NAME and so on) |

### Thread safety essentials

- **NAPI callbacks on the ArkTS UI thread must not use Qt APIs directly** (creating QObjects, calling QThread::currentThread(), and so on)
- Every Qt operation must be dispatched to QtMainThread through `invokeInQtThread()`
- The Qt types used by the C++ code in `setupQtApplication()` (`setupQtApplicationImpl`) — QString, QMap, QJsonDocument, and so on — don't trigger `QThreadData::current()`

---

## Diagnostic steps

### Step 1: confirm whether theMainThread differs from instance()->thread()

At the assertion site (the start of `sendThroughApplicationEventFilters` in `qcoreapplication.cpp`), add:

```cpp
auto *mt = QCoreApplicationPrivate::theMainThread.loadRelaxed();
auto *appThread = QCoreApplication::instance() ? QCoreApplication::instance()->thread() : nullptr;
auto *cur = QThread::currentThread();
qCritical("[THREAD-DEBUG] theMainThread=%p appThread=%p currentThread=%p",
          mt, appThread, cur);
qCritical("[THREAD-DEBUG] theMainThread == appThread? %d", mt == appThread);
qCritical("[THREAD-DEBUG] pthread_self=%lu", (unsigned long)pthread_self());
```

### Step 2: log theMainThread in the init lambda

In the init lambda in `qohosjsmain.cpp` (around line 737), add:

```cpp
auto *currentThread = QThread::currentThread();
QThread *mainThread = QCoreApplicationPrivate::theMainThread;
qCritical("[INIT-DEBUG] currentThread=%p theMainThread=%p pthread=%lu",
          currentThread, mainThread, (unsigned long)pthread_self());
```

### Step 3: check immediately after QApplication is constructed

In the user's main(), right after constructing QApplication, add:

```cpp
QApplication app(argc, argv);
qCritical("[APP-DEBUG] theMainThread=%p app.thread()=%p currentThread=%p pthread=%lu",
          QCoreApplicationPrivate::theMainThread.loadRelaxed(),
          app.thread(),
          QThread::currentThread(),
          (unsigned long)pthread_self());
```

### Step 4: look for Qt API calls before QApplication in main()

Inspect the user's main() function and find every Qt API call made before `QApplication` is constructed:

```cpp
int main(int argc, char *argv[])
{
    // ❌ Any of the following could trigger QThreadData::current() before QApplication
    qDebug() << "starting";           // qDebug → may trigger it
    QString s = "hello";              // safe (QString doesn't touch thread data)
    QObject obj;                      // ❌ constructing a QObject triggers QThreadData::current()
    QSettings settings;               // ❌ constructing QSettings may trigger it
    QThread::currentThread();         // ❌ triggers it directly

    QApplication app(argc, argv);     // ← theMainThread should be set before this point
    // ...
}
```

---

## Solution

### The short-term fix

**Make `QApplication` the first Qt API call in main()**:

```cpp
int main(int argc, char *argv[])
{
    // ✅ QApplication must be the first Qt call
    QApplication app(argc, argv);

    // only then use other Qt APIs
    qDebug() << "starting";
    // ...
    return app.exec();
}
```

### Longer-term recommendations

1. **Add a defensive check in the QPA plugin**: verify `theMainThread == QThread::currentThread()` when `QOhosPlatformIntegration` is constructed
2. **Document the main() constraint**: state explicitly that on OHOS, `QApplication` must be the first Qt API call in main()
3. **Consider strengthening** the guard check in `notify_helper()` in the Qt 5.15 OHOS branch, logging more detail instead of a bare Q_ASSERT

---

## Source references

| File:line | Description |
|-----------|-------------|
| `qtbase/src/corelib/kernel/qcoreapplication.cpp:534-539` | The definition of `theMainThread` and `mainThread()` |
| `qtbase/src/corelib/kernel/qcoreapplication.cpp:1157-1177` | `sendThroughApplicationEventFilters()`, containing the Q_ASSERT |
| `qtbase/src/corelib/kernel/qcoreapplication.cpp:1202-1217` | `notify_helper()`, containing the guard check |
| `qtbase/src/corelib/kernel/qcoreapplication.cpp:475-477` | The `theMainThread` check in the `QCoreApplicationPrivate` constructor |
| `qtbase/src/corelib/thread/qthread_unix.cpp:207-228` | `QThreadData::current()` setting `theMainThread` |
| `qtbase/src/corelib/thread/qthread.cpp:900-914` | The alternative `QThreadData::current()` implementation |
| `qtbase/src/plugins/platforms/ohos/qohosjsmain.cpp:712-771` | `makeQtThreadWithMainFuncLauncher()` |
| `qtbase/src/plugins/platforms/ohos/qohosjsmain.cpp:784-851` | `handleDefaultQAbilityInstanceStartup()` |
| `qtbase/src/plugins/platforms/ohos/qohossinglethreadexecutor.cpp:108-135` | `SingleThreadExecutor` creating "QtMainThread" |
| `qtbase/src/plugins/platforms/ohos/qohosplatformintegration.cpp:152` | `m_mainThread = QThread::currentThread()` |

---

## Content sources

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | A real crash reported by a partner, with a source-level call chain analysis |
| 🔍 Framework source | The Qt 5.15 OHOS branch's qcoreapplication.cpp, qthread_unix.cpp, and QPA plugin |
| 📄 Glue-code template | The ArkTS lifecycle in the template bundled with the Qt source (`qtbase/src/harmonyos/templates`) |
