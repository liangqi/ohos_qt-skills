---
id: problem-runtime-crash-sandbox-readonly-path
type: problem
domain: runtime
tags: [ohos, sandbox, file-write, sigabrt, exit, qstandardpaths, getapppath]
created: 2026-07-09
updated: 2026-08-14
status: solved
severity: critical
audience: public
refs: [fault-C-0013, procedural-qt-ohos-run-test, semantic-qt-harmonyos-platform-limits]
summary: >
  In the OHOS sandbox, QDir::currentPath()/applicationDirPath() return read-only paths,
  so writing a configuration file or log fails, the application calls exit(1), and it crashes with SIGABRT.
  Fix: use QStandardPaths::writableLocation(AppDataLocation) to get a writable path.
leader_summary: >
  Fixed the configuration-file write crash caused by OHOS sandbox read-only paths, producing a general path-fix pattern.
impact: [Migration efficiency]
deliverables: [problem record, source fix]
evidence: [FRequest commit 8a8ba95, crash log, on-device verification screenshot]

error_message: >
  Signal:SIGABRT(SI_TKILL) from exit(1)
  #03 ConfigFileFRequest::createNewConfig()+1884
  #04 ConfigFileFRequest::ConfigFileFRequest(QString const&)+84
  #05 MainWindow::MainWindow(QWidget*)+376
  doc.save_file() fails on read-only path → exit(1) → SIGABRT
error_code: ""
keywords: [SIGABRT, exit, sandbox, read-only, writable, QStandardPaths, AppDataLocation, QDir, currentPath, config file, OHOS]
symptoms: "The application crashes a short while after launch (SIGABRT); the crash stack shows exit(1) being called after a configuration-file write failure"
environment: "Qt 5.15.16 OHOS / HarmonyOS 6.0 / HUAWEI MateBook 14"
---

# OHOS sandbox read-only path causes a configuration-file write crash

> For the platform-level "writing to a read-only bundle path" diagnosis, the authority is the common knowledge base's [[ohos-common-kb/problems/runtime-write-to-readonly-bundle-path|Runtime write fails: the target is on a read-only bundle path]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/problems/runtime-write-to-readonly-bundle-path.md)). This page keeps the Qt/FRequest-specific searchable error text, the `QDir`/`QStandardPaths` root cause, and the fix.

## Error message

```
Signal:SIGABRT(SI_TKILL)@0x... from exit(1)
LastFatalMessage:[appspawn_server.c:69]Unexpected call: exit(1)
Tid:QtMainThread
#00 raise+216
#01 abort+24
#02 exit+144
#03 ConfigFileFRequest::createNewConfig()+1884
#04 ConfigFileFRequest::ConfigFileFRequest(QString const&)+84
#05 MainWindow::MainWindow(QWidget*)+376
#06 main+180
```

## Scenario

The Qt HarmonyOS port builds, installs, and launches successfully, but crashes a few seconds into running. The crash is a SIGABRT (not a SIGSEGV), triggered by the application code deliberately calling `exit(1)`.

## Cause

**An OHOS sandbox restriction**: the paths returned by `QDir::currentPath()` and `QCoreApplication::applicationDirPath()` in the OHOS sandbox are read-only. Writing a configuration file or log file under those paths fails.

**The crash chain**:
```
getAppPath() → QDir::currentPath() → read-only path
  → ConfigFileFRequest(configPath) → the config file doesn't exist → createNewConfig()
    → doc.save_file(configPath) → the write fails (read-only)
      → exit(1) → SIGABRT
```

**A related problem**: the plog log appender also uses `getAppPath()` to write log files and fails in the same way.

## Solution

Add a `Q_OS_OHOS` branch to your path-resolution function that returns a writable sandbox path:

```cpp
#include <QStandardPaths>

QString getAppPath(){
#ifdef Q_OS_MAC
    // ... macOS logic ...
#elif defined(Q_OS_OHOS)
    // OHOS sandbox: app binary dir is read-only, use writable app data dir
    QString dataPath = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);
    QDir().mkpath(dataPath);
    return dataPath;
#else
    return QDir::currentPath();
#endif
}
```

**Writable OHOS paths**:
- `QStandardPaths::AppDataLocation` → `/data/storage/el2/base/haps/entry/files/`
- `QStandardPaths::CacheLocation` → `/data/storage/el2/base/haps/entry/cache/`
- `QStandardPaths::TempLocation` → `/data/storage/el2/base/haps/entry/temp/`

## Notes

- This is a general OHOS sandbox problem, not specific to FRequest. Any Qt application that writes files using `QDir::currentPath()` or `applicationDirPath()` may be affected
- Make sure the `QStandardPaths` header is included when applying the fix
- `mkpath()` ensures the directory exists (it may not on first run)
- Check other file-write sites too, such as the plog log path and QSettings paths

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Fixed the configuration-file write crash caused by OHOS sandbox read-only paths, producing a general path-fix pattern |
| Scope of impact | Every Qt application that writes files on OHOS |
| Deliverables | problem record + the FRequest source fix |
| Evidence | FRequest commit 8a8ba95, crash log, on-device verification screenshot |
| How to reuse | Apply directly whenever you see SIGABRT + exit(1) + a file-write failure in the stack |

## Related

- [[qt-harmonyos-platform-limits]] — OHOS platform limitations (sandbox filesystem)
- [[procedural-qt-ohos-run-test]] — The run-test workflow
