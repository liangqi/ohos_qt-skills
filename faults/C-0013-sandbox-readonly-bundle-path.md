---
id: fault-C-0013
cid: C-0013
type: cause
title: The OHOS sandbox bundle install path is read-only, so desktop-style currentPath/applicationDirPath file writes fail (the app calls exit(1) → SIGABRT)
nature: limitation
domain: filesystem
fault_type: crash
responsible: ohos-runtime
co_responsible: []
component: "HarmonyOS application sandbox filesystem specification (read-only bundle) × QDir::currentPath / QCoreApplication::applicationDirPath"
severity: critical
evidence_type: logs
status: wontfix
evidence: "Application sandbox specification: the bundle install directory is read-only and the writable area is under /data/storage/el2/base/... (mapped by QStandardPaths); ohos-common-kb diagnostic page runtime-write-to-readonly-bundle-path (holds across frameworks); evidenced by the crash stack in the source page (SIGABRT ← exit(1) ← createNewConfig failing to write a read-only path)"
evolution: "— (the specification is stable: a read-only bundle is part of the sandbox security model; the writable-area semantics haven't changed)"
fix_route: ""
review_note: "Whether the read-only bundle specification has changed; whether the app's other write points (plog/QSettings/temporary files) have all moved to the writable area"
depends_on: []
affects_qt: ["Qt 5.15.16 (evidenced in the source page; the specification itself is independent of the Qt version)"]
affects_ohos: ["HarmonyOS 6.0 (evidenced in the source page; a read-only bundle is an all-version sandbox specification)"]
qoh: []
first_seen: 2026-07-09
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [harmonyos, sandbox, readonly, bundle, qstandardpaths, qdir, sigabrt, exit, config, limitation, workaround]
audience: public
refs: [problem-runtime-crash-sandbox-readonly-path, semantic-qt-harmonyos-platform-limits]
summary: >
  In the OHOS sandbox, QDir::currentPath()/applicationDirPath() return the read-only bundle path; after the app
  fails to write config/log files there it calls exit(1) → a delayed SIGABRT crash. limitation/ohos-runtime
  (sandbox specification, wontfix); alternative W-0011 (add a Q_OS_OHOS branch to path lookup and use
  QStandardPaths::AppDataLocation instead) is verified on a real device and merged into FRequest (commit 8a8ba95).
---

# C-0013 The OHOS sandbox bundle install path is read-only; writing config/logs triggers an exit(1) crash

> nature: limitation | responsible: ohos-runtime | status: wontfix | symptoms: S-0012 | workarounds: W-0011 | tickets: none yet | review: 2026-12-15

## Symptoms

### S-0012 App crashes with SIGABRT a few seconds after startup (exit(1); the stack points at a failed config file write)

The verbatim error (source page [runtime-crash-sandbox-readonly-path](../problems/runtime-crash-sandbox-readonly-path.md)):

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

Build/install/launch all succeed, and it crashes after running for a few seconds; the SIGABRT (not SIGSEGV) is triggered by the application code itself calling
`exit(1)`. Any Qt app that writes files using desktop-style paths on OHOS can be affected
(not just FRequest).

## Root cause / classification basis

The crash chain (source page):

```
getAppPath() → QDir::currentPath() → read-only bundle path
  → ConfigFileFRequest(configPath) → config file doesn't exist → createNewConfig()
    → doc.save_file(configPath) → write fails (read-only)
      → exit(1) → SIGABRT
```

HarmonyOS application sandbox specification: **the bundle install path is read-only** -- `QDir::currentPath()` and
`QCoreApplication::applicationDirPath()` point to a read-only area in the OHOS sandbox; the writable area is
`/data/storage/el2/base/...` (mapped by `QStandardPaths`). This is a **platform limitation**, not a
defect -- the path semantics are decided by the sandbox security model; there is no fix path of "allowing bundle writes", only
switching to the writable area. For general diagnosis, ohos-common-kb `runtime-write-to-readonly-bundle-path`
is authoritative (holds across frameworks).

## Responsibility

`ohos-runtime` (sandbox filesystem specification). The application side, out of desktop habit, treats the executable directory as writable
(to write config/logs) -- per the platform specification this is something the **application must adapt to** (disposition: Must adapt for HarmonyOS), not a Qt
framework problem (QDir faithfully returns the platform path).

Difference from C-0008: C-0008 is "file permissions and links are part of the packaging contract; runtime chmod/symlink are forbidden";
this one is "the bundle install path is read-only and writes fail" -- **two different rules of the same application sandbox filesystem specification**,
with different root causes, each recorded separately (cross-linked in §Related).

## Alternatives and evolution (limitation)

- **W-0011 (adopted)**: add a `Q_OS_OHOS` branch to the path lookup function that returns
  `QStandardPaths::writableLocation(AppDataLocation)` or another writable path (see §Workarounds).
- **Evolution**: none (the specification is stable). Watch points: extensions of the sandbox writable-area semantics and the QStandardPaths mapping
  (e.g. the resource directory mapping, QTBUG-146626).

## Workarounds

- **W-0011 (adopted, verified 2026-07-09 on a real device)**:

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

  OHOS writable paths (recorded in the source page):
  - `AppDataLocation` → `/data/storage/el2/base/haps/entry/files/`
  - `CacheLocation` → `/data/storage/el2/base/haps/entry/cache/`
  - `TempLocation` → `/data/storage/el2/base/haps/entry/temp/`

  Key points: ① make sure `<QStandardPaths>` is included; ② `mkpath()` guarantees the directory exists (it may not on the first
  run); ③ audit the other write points too (the plog log appender, QSettings,
  temporary files, etc. that also use the path from getAppPath()).

  Cost: every file write point has to be audited and reworked; cross-platform branches to maintain.
  Retirement condition: not expected to retire (wontfix: the read-only bundle specification is stable); if the platform ever allows write semantics
  for the application directory, go back to the native QDir paths.

## Tickets

None yet (the sandbox path specification is already covered by the official Qt platform limitations page and the ohos-common-kb general diagnosis;
no separate Qt-side behavior record ticket is needed for now).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-07-09 | Qt 5.15.16 / HarmonyOS 6.0 / HUAWEI MateBook 14 | Located via the crash stack (source page error message) + fix: getAppPath() gets a Q_OS_OHOS branch returning AppDataLocation (FRequest commit 8a8ba95) | Verified on a real device: the crash is gone (source page evidence: real-device verification screenshot) | → workaround |
| 2026-07-09 | — | Classification: the read-only bundle install path is a sandbox specification (the source page's "OHOS sandbox limitation" conclusion + the ohos-common-kb general diagnostic page) | Classification holds; no fix path, long-term reliance on path adaptation | → wontfix |

## Related

- Symptoms (S): S-0012
- Workarounds (W): W-0011
- Tickets (T): none yet
- problems: [runtime-crash-sandbox-readonly-path](../problems/runtime-crash-sandbox-readonly-path.md) (error lookup, fix code, list of writable paths, results record)
- semantic: [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md) (QStandardPaths constraints and standard path mapping)
- Related causes (C, including depends_on notes): C-0008 (cross-linked -- sibling rules of the same application sandbox filesystem specification: C-0008 forbids runtime chmod/symlink (permissions/links are part of the packaging contract), this one forbids writes to the read-only bundle area; parallel rules, no depends_on dependency)
