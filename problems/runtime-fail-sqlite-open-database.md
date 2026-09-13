---
id: problem-runtime-sqlite-open-database
type: problem
domain: runtime
tags: [runtime, sqlite, qsqlite, sqldrivers, QSqlDatabase, driver-not-loaded, relative-path, QStandardPaths, filesystem, dlopen, appspawn, exit-sigabrt]
created: 2026-07-07
updated: 2026-07-07
status: solved
audience: public
summary: "The application shows \"cannot create the local database\" at startup and then exits with a native cppcrash (QSQLITE driver not loaded / relative path)"
severity: high

# ====== Search keywords (for fast agent matching) ======
error_message: >
  Cannot create the local database!
  QSqlDatabase: QSQLITE driver not loaded
  unable to open database file
  LastFatalMessage: [appspawn_server.c:69]Unexpected call: exit(-1)
  Reason: Signal:SIGABRT(SI_TKILL)
  #03 libOhosChessGame.so(Database::Database()+352)
error_code: ""
keywords: [QSQLITE, libqsqlite, sqldrivers, QSqlDatabase, driver not loaded, setDatabaseName, relative path, QStandardPaths, AppLocalDataLocation, exit(-1), SIGABRT, cppcrash]
symptoms: "On launch the application shows a QMessageBox reading \"Cannot create the local database!\" and then exits (actually a native cppcrash); the Login window never appears"

# ====== Problem details ======
environment: "Qt 5.12.12 OHOS SDK (CMAKE_PREFIX_PATH=<QT5_12_OHOS_SDK>), the ChessClient HarmonyOS port (scenario two, wrapped in OhosExampleApp), a HUAWEI MateBook Fold device, bundleName=com.example.chessgame"
refs: [semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-code-patterns]
related_problems: [problem-runtime-qpa-plugin-not-found, problem-runtime-dlopen-writable-path, problem-build-hvigor-native-skip]
---

# QSqlDatabase open() failure crashes at startup (a dual root cause: undeployed driver + a relative path)

## Error message

### What the user sees
On launch the application shows a `QMessageBox` reading "Cannot create the local database!", and after clicking OK the application disappears.

### The faultlog (cppcrash-com.example.chessgame-20260707084730)
```
LastFatalMessage: [appspawn_server.c:69]Unexpected call: exit(-1)
Reason: Signal:SIGABRT(SI_TKILL)
#00 raise
#01 abort
#02 libappspawn_helper.z.so(exit+144)
#03 libOhosChessGame.so(Database::Database()+352)   ← where exit(-1) is called
#04 Database::GetInstance()+80
#05 Login::loadStatusFromDB()+40
#06 Login::Login(QWidget*)+332
#07 main+96
#08..#45 libqohos.so (the Qt OHOS bootstrap)
```

### Key diagnostic signals
- `grep "qsqlsqlite|sqldrivers|QSqlDriver"` over the crashed process's memory map yields **no matches** — the Qt driver .so was never dlopen'd into the process (only the native system `libsqlite.z.so` is present, which Qt can't use)
- On disk, `entry/libs/arm64-v8a/` contains only `styles/libqohosstyle.so` — there's **no `sqldrivers/` directory and no `libqsqlite.so`**
- `db->lastError().text()` (added while fixing) = `"Driver not loaded"`

## Scenario

Porting an open-source Qt Widgets application (the ChessClient chess game) to HarmonyOS. The original desktop `.pro` uses `QT += sql`, and `database.cpp` calls `setDatabaseName("ChineseChess.db")` (a bare filename) in a singleton constructor and calls `exit(-1)` if `open()` fails. When `Login` is constructed it calls `Database::GetInstance()`, instantiating it for the first time → `open()` fails → the message box appears → `exit(-1)`, all before `a.exec()` (early in startup).

The build succeeds and the HAP installs and launches (the QPA plugin loads, and it gets far enough to show the QMessageBox), but database initialization crashes.

## Cause

**Two root causes coexist and both must be fixed:**

### Root cause 1 (the triggering one, high): the QSQLITE driver plugin isn't deployed
`OhosExampleApp/CMakeLists.txt` already does `find_package(Qt5 ... Sql)` + `target_link_libraries(... Qt5::Sql ...)` (linking the main `libQt5Sql.so`, which is in the HAP), but **the `libqsqlite.so` driver plugin isn't deployed**.

- The nature of the driver: `Qt5Sql_QSQLiteDriverPlugin.cmake` declares `add_library(Qt5::QSQLiteDriverPlugin MODULE IMPORTED)` + `PLUGIN_LOCATION=sqldrivers/libqsqlite.so` — a **dynamic MODULE plugin** that `QFactoryLoader` dlopens at runtime from the `sqldrivers/` subdirectory.
- It's not a NEEDED dependency: neither `libQt5Sql.so` nor the business library has any `libqsqlite` reference in its strings, so CMake/HVigor **won't package it automatically**.
- The SDK has no static sqlite `.a`, so the `Q_IMPORT_PLUGIN` static path isn't viable.
- For comparison: `libqohosstyle.so` → `styles/` and `libqsvg.so` → `imageformats/` are both copied manually (iron rule B7); `sqldrivers/` was simply overlooked.

**The decisive logic**: when the driver is missing, the first thing `QSqlDatabase::open()` does is check `d->driver`, find it empty, and **return false with `lastError="Driver not loaded"` — it never calls `sqlite3_open` or touches the filesystem at all**. So root cause 2 (the path) never even got started in this run: changing only the path without deploying the driver leaves the crash unchanged.

### Root cause 2 (a latent second failure, medium): setDatabaseName uses a relative path
`setDatabaseName("ChineseChess.db")` is just a filename, which relies on the process's CWD being writable. OHOS applications are loaded as shared libraries (iron rule L2: `argv[0]` is the .so path), and the CWD usually lands in the read-only `el1/bundle` area (the faultlog shows `libOhosChessGame.so` coming from `/data/storage/el1/bundle/libs/arm64/`). Once the driver is deployed, this defect surfaces as the second failure — SQLite `CANTOPEN(14)`/`EACCES`.

### The crash mechanism (not a root cause)
OHOS's `libappspawn_helper.z.so` intercepts `exit(-1)` and treats it as an "Unexpected call", converting it into `raise(SIGABRT)` → `abort()` and producing a cppcrash (which is why the user sees a native crash rather than a silent exit).

## Solution

### 1. Deploy the QSQLITE driver plugin (the priority; consistent with iron rule B7)

```bash
mkdir -p <project>/HarmonyOS/entry/libs/arm64-v8a/sqldrivers/
cp <Qt_SDK>/plugins/sqldrivers/libqsqlite.so \
   <project>/HarmonyOS/entry/libs/arm64-v8a/sqldrivers/libqsqlite.so
```

⚠️ **In the OHOS SDK the driver file is named `libqsqlite.so`, not desktop's `libqsqlsqlite.so`** (verified against `PLUGIN_LOCATION` in `Qt5Sql_QSQLiteDriverPlugin.cmake`).

**No CMake changes are needed** — `target_link_libraries` does nothing for a dynamic plugin of this class, and the SDK has no static `.a`, so `Q_IMPORT_PLUGIN` isn't viable. Optionally, add an `add_custom_command(POST_BUILD)` at the end of `CMakeLists.txt` to copy it automatically and prevent regressions:

```cmake
add_custom_command(TARGET <app> POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E make_directory
    ${CMAKE_CURRENT_SOURCE_DIR}/../HarmonyOS/entry/libs/arm64-v8a/sqldrivers
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
    ${CMAKE_PREFIX_PATH}/plugins/sqldrivers/libqsqlite.so
    ${CMAKE_CURRENT_SOURCE_DIR}/../HarmonyOS/entry/libs/arm64-v8a/sqldrivers/libqsqlite.so
  COMMENT "Deploy qsqlite driver plugin to HAP libs/sqldrivers/")
```

### 2. Change database.cpp to a writable absolute sandbox path (also required)

```cpp
#include <QStandardPaths>
#include <QDir>
#include <QSqlError>
// ...
QString dataDir = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
if (dataDir.isEmpty()) dataDir = QDir::currentPath();   // fallback
QDir().mkpath(dataDir);
db->setDatabaseName(dataDir + QDir::separator() + "ChineseChess.db");
if (!db->open()) {
    qWarning() << "[DB] open failed:" << db->lastError().text() << "path:" << db->databaseName();
    QMessageBox::information(nullptr, "Error",
        QString("Cannot create the local database!\nPath: %1\nError: %2").arg(db->databaseName(), db->lastError().text()));
    exit(-1);  // optionally change to QCoreApplication::exit(-1) to avoid the SIGABRT cppcrash
}
```

On OHOS, `AppLocalDataLocation` maps to `preferencesDir` (a writable sandbox under `/data/storage/el2/` where file IO is allowed and only `.so` dlopen is rejected — so a `.db` there is safe). On desktop it returns `~/.local/share/<Org>/<App>`, so the same code works without `#ifdef`.

### 3. (Optional) set the application/organization name in main.cpp

```cpp
QCoreApplication::setOrganizationName("MyOrg");
QCoreApplication::setApplicationName("MyApp");
```
On desktop this gives the path a sensible `<App>` segment; on OHOS the path is determined by the bundleName, so it makes no difference.

## Verification

```bash
# 1. The driver is in the bundle (read-only el1)
hdc shell find /data/storage/el1/bundle -name 'libqsqlite*'
# 2. Launch the application: no more "cannot create the local database", and Login displays normally
# 3. The db file is created in the writable sandbox
hdc shell find /data/storage/el2 -name 'ChineseChess.db'
# 4. qWarning diagnostics (they go to stderr by default and don't reach hilog; redirect them)
hdc shell hilog | grep -iE 'QSqlDatabase|QSQLITE|driver|open'
# 5. No new cppcrash
hdc shell faultloggerd
```

After the fix, `cppcrash-com.example.chessgame` no longer appears (the `exit(-1)` branch is never taken). This fix has been verified on a real device.

## Notes

- **Linking the library ≠ deploying the driver**: `target_link_libraries(Qt5::Sql)` only deploys `libQt5Sql.so`; the `libqsqlite.so` driver is a separate runtime dlopen plugin that must be copied into `sqldrivers/` (the same pattern as `libqohosstyle.so` → `styles/` and `libqsvg.so` → `imageformats/`).
- **The two kinds of open() failure are indistinguishable**: the original code showed a fixed message on `open()` failure without printing `lastError()`, so "driver not loaded" and "path not writable" looked identical. When fixing, always include `lastError().text()` in the message box/qWarning — "Driver not loaded" = a driver problem, "unable to open database file" = a path problem.
- **The boundary of the dlopen restriction**: `dlopen()` rejecting writable el2 paths (platform limitation P3) applies **only to loading .so files**; it doesn't prevent writing the database file itself into the el2 sandbox. The driver .so must go in `entry/libs/` (mapped read-only into el1 after installation, where dlopen is permitted).
- **Filename difference**: the OHOS SDK has `libqsqlite.so`; desktop has `libqsqlsqlite.so`. Use the actual filename when copying from the SDK.
- **Static built-in ruled out**: scanning this SDK's `libQt5Sql.so` strings for `qsqlite` gives 0 matches, so the driver isn't statically built in (if it were, the plugin wouldn't need deploying — but the OHOS SDK doesn't do that).
- **A build cache trap**: after deploying the driver and changing the source, if the hvigor incremental build is a no-op (artifact mtimes unchanged, `.cxx`/`build` not rebuilt), clear `.hvigor` + `.cxx` + `build` and do a full sync/rebuild with the environment set (`DEVECO_SDK_HOME` + `JAVA_HOME`) — see [build-hvigor-native-skip](build-hvigor-native-skip.md).

## Related

- [[qt-harmonyos-golden-rules]] — Rules B7 (copy the style manually) / B12 (copy the SQL driver manually) / L2 (argv is the library path)
- [[qt-harmonyos-project-structure]] — §6.2 the manual-copy table (including libqsqlite.so)
- [[qt-harmonyos-platform-limits]] — §dlopen rejects writable paths (.so only) / §QStandardPaths constraints
- [[qt-harmonyos-code-patterns]] — Pattern 14 (a writable sandbox path for the database file)

### Related problems

- [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) — The same "plugin not deployed" pattern (the QPA libqohos.so)
- [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) — The boundary of the dlopen restriction (.so files can't live in el2, but a .db can)
- [build-hvigor-native-skip](build-hvigor-native-skip.md) — Clearing caches when the post-fix rebuild is a no-op

> 📋 Back to the [error quick-reference table](_lookup.md)
