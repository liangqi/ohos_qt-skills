---
id: problem-runtime-crash-null-pointer-entry-shim
type: problem
domain: runtime
tags: [qt, harmonyos, null-pointer, sigsegv, entry-shim, main-cpp, crash]
created: 2026-07-08
updated: 2026-07-10
status: solved
severity: critical
audience: public
refs: [semantic-qt-harmonyos-build-run-workflow, procedural-qt-ohos-run-test]
summary: >
  The OHOS entry shim (main.cpp) skips the original login flow and passes nullptr straight to MainWindow;
  downstream, initSet() has no null check, causing a SIGSEGV. Fix: add if-null guards plus safe defaults for business pointers.
leader_summary: >
  Fixed the null-pointer crash caused by the OHOS entry shim skipping the initialization flow, and distilled it into an entry-shim design pattern.
impact: [Migration efficiency]
deliverables: [problem record, source fix]
evidence: [RedisView on-device verification commit, crash log]
error_message: >
  Signal:SIGSEGV(SEGV_MAPERR)@0x0000000000000040  probably caused by NULL pointer dereference
  #00 QString::QString(QString const&)
  #01 RedisCluster::getConnectName() const
  #02 MainWidget::initSet(RedisCluster*)
  #03 MainWidget::MainWidget(RedisCluster*, QWidget*)
  #04 MainWindow::mainWidget()
  #05 MainWindow::init(RedisCluster*)
  #06 MainWindow::MainWindow(RedisCluster*, QWidget*)
  #07 main+224
error_code: ""
keywords: [SIGSEGV, NULL pointer, nullptr, entry shim, main.cpp, OHOS, MainWindow, initSet]
symptoms: "The application crashes about a second after launch (a C++ SIGSEGV); the QtMainThread stack frames show a null-pointer dereference"
environment: "Qt 5.15.16 OHOS / HarmonyOS 6.0 / HUAWEI MateBook 14"
---

# The OHOS entry shim passes nullptr, crashing business code on a null pointer

## Error message

```
Reason:Signal:SIGSEGV(SEGV_MAPERR)@0x0000000000000040  probably caused by NULL pointer dereference
Fault thread info:
Tid:57608, Name:QtMainThread
#00 pc 000000000015ec68 libOhosRedisView.so(QString::QString(QString const&)+32)
#01 pc 00000000001c3638 libOhosRedisView.so(RedisCluster::getConnectName() const+52)
#02 pc 00000000001cb55c libOhosRedisView.so(MainWidget::initSet(RedisCluster*)+996)
#03 pc 00000000001caeb0 libOhosRedisView.so(MainWidget::MainWidget(RedisCluster*, QWidget*)+472)
#04 pc 000000000017ebfc libOhosRedisView.so(MainWindow::mainWidget()+48)
#05 pc 00000000001769fc libOhosRedisView.so(MainWindow::init(RedisCluster*)+192)
#06 pc 00000000001768e0 libOhosRedisView.so(MainWindow::MainWindow(RedisCluster*, QWidget*)+132)
#07 pc 000000000016eab4 libOhosRedisView.so(main+224)
```

## Scenario

The Qt HarmonyOS port builds, installs, and loads `libqohos.so` successfully, but crashes in the C++ layer about a second after launch.

## Cause

**The original application flow**: `AppMain.cpp` → show `LoginDialog` → the user enters Redis connection details → create a `RedisCluster` object → pass it to `MainWindow`.

**The OHOS entry shim** (`OhosExampleApp/main.cpp`): to simplify HarmonyOS porting verification, it skips the login dialog and passes `nullptr` directly:

```cpp
// OhosExampleApp/main.cpp
MainWindow w(nullptr);  // ← passing a null pointer
w.show();
return app.exec();
```

**The crash chain**:
```
main(nullptr)
  → MainWindow::init(nullptr)        // _redisClient = nullptr
    → MainWindow::mainWidget()        // new MainWidget(nullptr)
      → MainWidget::initSet(nullptr)  // _redisClient = nullptr
        → _redisClient->getConnectName()  // ← dereferences nullptr → SIGSEGV
```

Line 111 of `initSet()` calls `_redisClient->getConnectName()` directly with no null check. The offset 0x40 corresponds to the offset of the `_ConnectName` (QString) member in the `RedisCluster` class.

## Solution

Add a null guard for `_redisClient` in `MainWidget::initSet()`:

```cpp
_redisClient = redisClient;
if(_redisClient) {
    _strConnectName = _redisClient->getConnectName();
    _isClusterMode = _redisClient->getClusterMode();
    _isReplicationMode = _redisClient->getReplicationMode();
    _isCustomMode = _redisClient->getCustomMode();
    // ... the existing initialization logic ...
    _vClients = _redisClient->getClients(false);
    _vMasterClients = _redisClient->getClients(true);
} else {
    _strConnectName = "";
    _isClusterMode = false;
    _isReplicationMode = false;
    _isCustomMode = false;
    _idbNums = 16;
}
```

## A general troubleshooting method

For every migration project that uses an OHOS entry shim:

1. **Check the arguments main.cpp passes**: if the original `main()` created an object via a dialog/config file before passing it to MainWindow, then everything downstream must be guarded when the shim passes `nullptr`
2. **Find every dereference site**: `grep "_redisClient->" *.cpp` to see which ones are on the startup path (constructors/init functions)
3. **Separate the startup path from the interaction path**: only dereferences on the startup path need immediate guards; those in slot functions can wait until the user acts

## Notes

- This is a general problem pattern for OHOS entry shims, not specific to RedisView
- Any project whose original application relies on an "initialize first, then create the window" flow needs null guards in the shim
- The long-term fix: implement a minimal initialization flow in the shim (for example, reading connection details from a config file)

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Fixed the null-pointer crash caused by the OHOS entry shim skipping initialization, and distilled it into a general design pattern |
| Scope of impact | Every Qt HarmonyOS porting project that uses the entry-shim pattern |
| Deliverables | problem record + source fix |
| Evidence | RedisView on-device verification commit |
| How to reuse | Apply directly when you see an entry shim + SIGSEGV + business-code stack frames |

## Related

- [[qt-harmonyos-build-run-workflow]] — The build-and-run workflow
