---
id: semantic-qt-harmonyos-code-patterns
type: semantic
domain: tech
tags: [qt, harmonyos, code-patterns, porting, before-after, examples]
created: 2026-06-02
updated: 2026-08-14
status: active
audience: public
refs: [semantic-qt-harmonyos-api-mapping, semantic-qt-harmonyos-porting-workflow, semantic-qt-ohos-extras]
summary: >
  A quick reference of Qt adapter code for HarmonyOS platform capabilities: 14 before/after pairs covering child processes, Want,
  standalone dialogs → tagged subwindows, close event handling, file permission guards, argument parsing,
  platform build configuration, dark mode, drag and drop, monospace fonts, floating windows, share data, porting Qt6→Qt5 with a shim (without touching the original src),
  and database file paths.
---

# The Qt adapter for HarmonyOS platform capabilities: 14 before/after pairs

> Source: [Code Patterns: Before/After Porting Examples](https://wiki.qt.io/Qt_for_HarmonyOS/code_patterns)
> Related: [[qt-harmonyos-api-mapping]], [[qt-harmonyos-porting-workflow]], [[qt-ohos-extras]]
>
> This page maintains only copyable Qt/QtOhosExtras/QPA code rewrites. For the Want and lifecycle semantics, see [[ohos-common-kb/semantic/stage-uiability-lifecycle|The Stage model and the UIAbility lifecycle]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/stage-uiability-lifecycle.md)); for the window/XComponent seam, see [[ohos-common-kb/semantic/arkui-window-xcomponent-model|The ArkUI window and XComponent hosting model]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/arkui-window-xcomponent-model.md)); for file permissions and loader restrictions, see [[ohos-common-kb/semantic/harmonyos-platform-limits|HarmonyOS platform limitations]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-platform-limits.md)); for choosing between bundle and data paths, see [[ohos-common-kb/semantic/application-sandbox-paths|HarmonyOS application sandbox paths and code loading]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/application-sandbox-paths.md)).

## The patterns at a glance

| # | Scenario | The core change |
|---|----------|-----------------|
| 1 | Child processes | QProcess by scenario: keep it when headless / startAppProcess for a Qt UI / startAbility for a non-Qt UI |
| 2 | Launching external applications | QDesktopServices / JNI → startAbility() |
| 3 | Standalone dialogs | A direct show() → tagAsSubWindowOf() |
| 4 | Close event handling | A single closeEvent → distinguishing WindowStage/Ability/Internal |
| 5 | File permission guards | setPermissions → skipped via conditional compilation |
| 6 | Argument parsing | Indexing argv directly → QCommandLineParser |
| 7 | Platform build configuration | qmake lacking an ohos branch → adding ohos {} |
| 8 | Dark mode | A manual palette → ColorThemeMode following the system |
| 9 | Drag and drop | Reading data in dragEnter → only checking MIME, then reading on drop |
| 10 | Monospace fonts | systemFont → registering a bundled .ttf |
| 11 | Floating windows | None → setShowWindowAsFloatWindowHint() |
| 12 | Sharing data | None → ShareKit integration |
| 13 | Porting Qt6→Qt5 with a shim | Qt6-only APIs / unavailable third-party libraries → replaced by a standalone shim layer (without touching the original src) |
| 14 | Database file paths | A relative filename → a writable absolute sandbox path from QStandardPaths |

---

## Pattern 1: child processes → choose by scenario (not one-size-fits-all)

On desktop/Android you start a child process with `QProcess`. On HarmonyOS you choose based on the scenario — there's no one-size-fits-all answer.

> For the four-scenario decision tree (keep QProcess when headless / startAppProcess for a Qt UI / startAbility for a non-Qt UI / startNoUiChildProcess for supervised headless work), see [[qt-harmonyos-api-mapping]] §1 Process management.

**Before (desktop/Android)**
```cpp
#include <QProcess>

void MainWindow::runWorker() {
    QProcess proc;
    proc.start("worker", {"--input", inputFile});
    proc.waitForFinished();
}
```

**After (HarmonyOS) — headless: leave QProcess alone**
```cpp
// A headless compute child process: QProcess stays as-is
void MainWindow::runWorker() {
    QProcess proc;
    proc.start("worker", {"--input", inputFile});
    proc.waitForFinished();
}
```

**After (HarmonyOS) — headless but needing native supervision (a .so child process)**
```cpp
#include <QtOhosExtras/qohosappcontext.h>

void MainWindow::runWorker() {
    QtOhosExtras::QOhosAppContext::startNoUiChildProcess(
        "libWorker.so",
        QStringList{"--input", inputFile}
    );
}
```

> **The key constraints**: a `startNoUiChildProcess` child must be compiled as a `.so` shared library, deployed into `entry/libs/<arch>/`, and it **must not** create a `QApplication`/GUI. If it's just headless computation, **prefer leaving QProcess alone**.
> See the description of startNoUiChildProcess in [[qt-ohos-extras]], and the decision tree in [[qt-harmonyos-api-mapping]] §1.

---

## Pattern 2: launching an external application → start an Ability

On desktop you use `QDesktopServices::openUrl()`; on Android you construct an Intent through JNI. Qt's HarmonyOS adapter uses `QOhosWant` + `startAbility()`.

**Before (desktop)**
```cpp
QDesktopServices::openUrl(QUrl("https://example.com"));
```

**Before (Android)**
```cpp
QAndroidJniObject intent("android/content/Intent");
// ... complex JNI construction
```

**After (HarmonyOS)**
```cpp
QtOhosExtras::QOhosWant want;
want.uri = "https://example.com";
want.action = "ohos.want.action.viewData";
QtOhosExtras::startAbility(want);
```

> See [[qt-ohos-extras]] for the full parameter documentation of QOhosWant and startAbility().

---

## Pattern 3: a standalone dialog → a tagged subwindow

In Qt's QPA adapter, a parentless standalone `QDialog` maps to a new main window; when you want subwindow semantics you must tag it — see [[qt-harmonyos-api-mapping]].

**Before (desktop)**
```cpp
void MainWindow::showSettings() {
    SettingsDialog *dlg = new SettingsDialog();
    dlg->setAttribute(Qt::WA_DeleteOnClose);
    dlg->show();
}
```

**After (HarmonyOS)**
```cpp
void MainWindow::showSettings() {
    SettingsDialog *dlg = new SettingsDialog();
    // The key step: tag it as a subwindow of the current main window
    QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(dlg, this->windowHandle());
    dlg->setAttribute(Qt::WA_DeleteOnClose);
    dlg->show();
}
```

> **Note**: a parentless dialog that doesn't call `tagWindowOrWidgetAsSubWindowOf()` becomes a standalone main window, without the expected subwindow hierarchy and modality semantics.

---

## Pattern 4: close event handling — distinguishing the reason

Qt's adapter maps window closes, Ability lifecycle destruction, and internal closes all onto `closeEvent`, so you must handle them by root cause.

**Before (desktop)**
```cpp
void MainWindow::closeEvent(QCloseEvent *event) {
    if (unsavedChanges()) {
        int ret = QMessageBox::question(this, "Save?",
            "Unsaved changes. Save before closing?",
            QMessageBox::Save | QMessageBox::Discard | QMessageBox::Cancel);
        if (ret == QMessageBox::Save) { save(); event->accept(); }
        else if (ret == QMessageBox::Discard) { event->accept(); }
        else { event->ignore(); }
    }
}
```

**After (HarmonyOS)**
```cpp
void MainWindow::closeEvent(QCloseEvent *event) {
    auto cause = QtOhosExtras::getCloseEventRootCause(event);

    if (cause == QtOhosExtras::CloseEventRootCause::WindowStageClose) {
        // The user closed the window → ask about saving normally (full interaction)
        if (unsavedChanges()) {
            int ret = QMessageBox::question(this, "Save?",
                "Unsaved changes. Save before closing?",
                QMessageBox::Save | QMessageBox::Discard | QMessageBox::Cancel);
            if (ret == QMessageBox::Save) { save(); event->accept(); }
            else if (ret == QMessageBox::Discard) { event->accept(); }
            else { event->ignore(); }
        }
    } else if (cause == QtOhosExtras::CloseEventRootCause::AbilityClose) {
        // The system is reclaiming the Ability → autosave silently; don't show a dialog
        if (unsavedChanges()) autoSave();
        event->accept();
    } else {
        // InternalClose → just accept
        event->accept();
    }
}
```

> **The core principles**:
> - `WindowStageClose` — the user closed the window deliberately, so a full QMessageBox interaction is fine
> - `AbilityClose` — the system is reclaiming the Ability and the user isn't in the foreground, so autosave quickly and never show a dialog
> - `InternalClose` — triggered internally by the program; just accept

---

## Pattern 5: file permission guards

The platform permission model comes from the common knowledge base; Qt code uses conditional compilation to avoid making a successful `QFile::setPermissions()` a prerequisite.

**Before (cross-platform)**
```cpp
QFile file(path);
file.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
```

**After (HarmonyOS-aware)**
```cpp
QFile file(path);
#ifndef Q_OS_OHOS
file.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
#endif
```

> Calling `setPermissions()` on HarmonyOS fails or produces undefined behavior. Guard it with `#ifndef Q_OS_OHOS`.

---

## Pattern 6: argument parsing → QCommandLineParser

On HarmonyOS, `argv[0]` is the application library path rather than an executable path, and a Want parameter may occupy `argv[1]`. Don't assume where your arguments are — use `QCommandLineParser`. See the argument-passing section of [[qt-harmonyos-api-mapping]].

**Before (desktop)**
```cpp
int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    QString configFile = argv[1]; // assumes argv[1] is the config file
    // ...
}
```

**After (HarmonyOS-aware)**
```cpp
int main(int argc, char *argv[]) {
    QApplication app(argc, argv);

    QCommandLineParser parser;
    parser.addOption({"config", "Config file", "file"});
    parser.process(app);
    QString configFile = parser.value("config");
    // ...
}
```

> **The key constraint**: never index `argv[N]` directly for your own arguments. `QCommandLineParser` is the cross-platform-safe approach.

---

## Pattern 7: platform build configuration → add the ohos branch

In a qmake project file, the Linux condition `unix:!android:!macx` wrongly matches ohos, so you need to exclude it explicitly and add an ohos branch. For build details, see [[qt-harmonyos-porting-workflow]].

**Before (.pro)**
```qmake
win32 {
    SOURCES += platform_win.cpp
}
unix:!android:!macx {
    SOURCES += platform_linux.cpp
}
android {
    SOURCES += platform_android.cpp
}
```

**After (with OHOS added)**
```qmake
win32 {
    SOURCES += platform_win.cpp
}
unix:!android:!macx:!ohos {
    SOURCES += platform_linux.cpp
}
android {
    SOURCES += platform_android.cpp
}
ohos {
    QT += ohosextras
    SOURCES += platform_ohos.cpp
}
```

> **Note**:
> - The `unix` branch must have `:!ohos` appended to exclude HarmonyOS, or ohos will match the unix branch too
> - The `ohos` branch must include `QT += ohosextras` to use the QtOhosExtras APIs

---

## Pattern 8: dark mode support → follow the system

On desktop you implement a dark theme by setting a QPalette by hand. On HarmonyOS you follow the system's dark setting through `QOhosAppContext` and respond to its change signal.

**Before (desktop)**
```cpp
QApplication::setStyle("fusion");
QPalette darkPalette;
darkPalette.setColor(QPalette::Window, QColor(53, 53, 53));
darkPalette.setColor(QPalette::WindowText, Qt::white);
// ... set each color role by hand
qApp->setPalette(darkPalette);
```

**After (HarmonyOS)**
```cpp
#include <QtOhosExtras/qohosappcontext.h>

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);

    auto *ctx = QtOhosExtras::QOhosAppContext::instance();
    ctx->setColorThemeMode(
        QtOhosExtras::QOhosAppContext::ColorThemeMode::FollowSystemSetting);

    MainWindow w;
    QObject::connect(ctx, &QOhosAppContext::darkThemeActiveChanged,
        [&w](bool dark) { w.updateTheme(dark); });
    w.show();
    return app.exec();
}
```

> `FollowSystemSetting` tracks the system's light/dark switch automatically; the `darkThemeActiveChanged(bool)` signal fires on each switch, letting you update your custom styling in the slot.

---

## Pattern 9: drag and drop → read the data later

On HarmonyOS the drag's MIME data may not be available during `dragEnterEvent`; the actual content can only be read in `dropEvent`.

**Before (desktop)**
```cpp
void Widget::dragEnterEvent(QDragEnterEvent *event) {
    if (event->mimeData()->hasText()) {
        QString text = event->mimeData()->text(); // reads the data directly
        if (isValidData(text))
            event->acceptProposedAction();
    }
}
```

**After (HarmonyOS)**
```cpp
void Widget::dragEnterEvent(QDragEnterEvent *event) {
    if (event->mimeData()->hasText()) {  // only check the MIME type
        event->acceptProposedAction();
        // Don't read the actual text() data here on OHOS
    }
}

void Widget::dropEvent(QDropEvent *event) {
    QString text = event->mimeData()->text(); // read the actual data on drop
    processData(text);
}
```

> **The core principle**: `dragEnterEvent` should only do type checks like `hasText()` / `hasUrls()`; read the actual content in `dropEvent`. This is because HarmonyOS's drag-and-drop protocol transfers data asynchronously.

---

## Pattern 10: monospace fonts → bundle a TTF

HarmonyOS provides no monospace font, and `QFontDatabase::systemFont(QFontDatabase::FixedFont)` returns an ordinary font. Bundle your own `.ttf` and register it with `addApplicationFont()`.

**Before (desktop)**
```cpp
QFont monoFont = QFontDatabase::systemFont(QFontDatabase::FixedFont);
editor->setFont(monoFont);
```

**After (HarmonyOS)**
```cpp
#ifdef Q_OS_OHOS
int fontId = QFontDatabase::addApplicationFont(":/fonts/NotoSansMono-Regular.ttf");
QStringList families = QFontDatabase::applicationFontFamilies(fontId);
QFont monoFont(families.first());
#else
QFont monoFont = QFontDatabase::systemFont(QFontDatabase::FixedFont);
#endif
editor->setFont(monoFont);
```

> **Deployment steps**:
> 1. Put `NotoSansMono-Regular.ttf` into your project's resource file (`.qrc`)
> 2. Reference it with the `:/fonts/` prefix
> 3. `addApplicationFont()` returns a fontId; use `applicationFontFamilies()` to get the actual family name

---

## Pattern 11: floating windows (a HarmonyOS-only capability)

HarmonyOS supports floating windows, a concept desktop platforms don't have. Enable it with `setShowWindowAsFloatWindowHint()`.

**New (HarmonyOS only)**
```cpp
#include <QtOhosExtras/qohoswindowutils.h>

void MainWindow::openFloatingNote() {
    NoteWidget *note = new NoteWidget();
    QtOhosExtras::setShowWindowAsFloatWindowHint(note, true);
    note->setAttribute(Qt::WA_DeleteOnClose);
    note->resize(300, 400);
    note->show();
}
```

> **Note**: floating windows need the `ohos.permission.SYSTEM_FLOAT_WINDOW` permission, which third-party applications usually can't get. This function has no effect on desktop.

---

## Pattern 12: sharing data (a HarmonyOS-only capability)

Share a file to other system applications through ShareKit. Desktop has no equivalent.

**New (HarmonyOS only)**
```cpp
#include <QtOhosExtras/qohossharekit.h>
#include <QtOhosExtras/qohosuiabilitycontext.h>

void MainWindow::shareFile(const QString &filePath) {
    auto record = QtOhosExtras::ShareKit::createFileRecord(QFileInfo(filePath));
    record->setTitle(QFileInfo(filePath).fileName());

    auto ability = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
    ability->shareDataWithShareKit({record}, nullptr);
}
```

> `createFileRecord()` builds a share record from a `QFileInfo`, and `shareDataWithShareKit()` brings up the system share sheet. The second argument is a callback; passing `nullptr` means you don't care about the result.

---

## Pattern 13: a Qt6 application → porting to Qt5 OHOS with a shim (without touching the original src)

> When porting an application targeting Qt6 to Qt 5.15 OHOS, replace the Qt6-only APIs and unavailable third-party libraries (qcoro's C++20 coroutines, exiv2, and so on) with a **standalone shim layer**, **without modifying the application's original src/**. Drawn from the vooki-image-viewer HarmonyOS port.

**The layout** (a scenario-two OhosExampleApp variant):
```
<app>/                     # the original repository, untouched
├── src/...                # the original source
└── OhosExampleApp/        # the shim layer + the OHOS entry point
    ├── CMakeLists.txt     # replaces original .cpp files with shim .cpp files (excluding the originals, adding the shims)
    ├── main.cpp           # extern "C" int main
    ├── ImageLoaderShim.cpp      # replaces src/processing/ImageLoader.cpp
    ├── Application.cpp          # a stub: Qt6's new QLibraryInfo API → Qt5
    ├── MetadataExtractorStub.cpp # disables EXIF (exiv2 isn't available)
    ├── ohos_compat.h            # shims for facilities missing from the OHOS NDK libc++, such as std::ranges
    ├── qcoro_shim/              # a minimal qcoro Task/Future coroutine skeleton
    └── exiv2_stub/exiv2/exiv2.hpp  # an exiv2 placeholder header
```

**The CMakeLists replacement pattern** (using shims instead of the original .cpp files, with the include path pointing at ../src so the shims can reference the original headers):
```cmake
# Exclude the original files containing Qt6-only APIs
set(OHOS_SOURCES
    main.cpp
    ImageLoaderShim.cpp        # replaces ../src/processing/ImageLoader.cpp
    Application.cpp            # a stub
    MetadataExtractorStub.cpp  # a stub
)
# Q_OBJECT headers referenced by a shim through ../src must be listed explicitly in add_library
# (otherwise AUTOMOC won't generate/link the moc across directories → undefined vtable/staticMetaObject)
set(OHOS_HEADERS
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/processing/Application.h
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/processing/MetadataExtractor.h
)
add_library(Ohos<App> SHARED ${OHOS_SOURCES} ${OHOS_HEADERS} ...)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/../src)
```

**The shim .cpp pattern** (removing Qt6-only calls and degrading the logic):
```cpp
// ImageLoaderShim.cpp — replaces ImageLoader.cpp
#include "processing/ImageLoader.h"
// Qt6: QImageReader::setAllocationLimit(512); // no such API in Qt 5.15, and since it's only a memory cap, omitting it is safe
QImage ImageLoader::load(const QString &path) { /* implemented with the Qt5 APIs */ }
```

**Where it applies and its limits**:
- Qt6-only APIs (such as `QImageReader::setAllocationLimit` or the new `QLibraryInfo` path API) → replace or degrade with a shim
- Unavailable third-party libraries (exiv2/qcoro) → stub placeholders (the feature degrades but it compiles; that feature is unavailable at runtime)
- Things missing from the OHOS NDK libc++ (`std::ranges`) → `ohos_compat.h` provides a min-max shim
- **The principle**: shims live only in the OhosExampleApp/ layer and the original src/ is untouched — which makes upstream syncing easy and isolates the OHOS-specific logic
- **When it doesn't apply**: if the application's core functionality depends heavily on Qt6-exclusive modules (such as QtQuick3D or QtMultimedia6's new APIs), a shim can't substitute, and you need to evaluate a real migration or declare it blocked

> The AUTOMOC/AUTOUIC cross-directory trap: a Q_OBJECT header referenced by a shim through `../src` must be listed explicitly in `add_library` (otherwise AUTOMOC won't generate/link the moc across directories → undefined vtable/staticMetaObject); when your .ui files live in a separate subdirectory, set `CMAKE_AUTOUIC_SEARCH_PATHS`.

---

## Pattern 14: database file paths → a writable absolute sandbox path

A Qt application's CWD may be in a read-only bundle or somewhere unexpected. SQLite and configuration files should use the writable directory Qt maps through `QStandardPaths::writableLocation(AppLocalDataLocation)` rather than a hard-coded platform path on this page; that API works on desktop too, so no `#ifdef` is usually needed.

**Before (desktop-friendly but breaks on OHOS)**
```cpp
QSqlDatabase db = QSqlDatabase::addDatabase("QSQLITE");
db.setDatabaseName("myapp.db");   // a bare filename, relying on the CWD being writable
if (!db.open()) {
    QMessageBox::information(nullptr, "Error", "Cannot create the local database!");
    exit(-1);
}
```

**After (HarmonyOS-aware, unified cross-platform)**
```cpp
#include <QStandardPaths>
#include <QDir>

QSqlDatabase db = QSqlDatabase::addDatabase("QSQLITE");
QString dataDir = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
if (dataDir.isEmpty()) dataDir = QDir::currentPath();   // fallback
QDir().mkpath(dataDir);
db.setDatabaseName(dataDir + QDir::separator() + "myapp.db");
if (!db.open()) {
    qWarning() << "DB open failed:" << db.lastError().text() << "path:" << db.databaseName();
    QMessageBox::information(nullptr, "Error",
        QString("Cannot create the local database!\nPath: %1\nError: %2").arg(db.databaseName(), db.lastError().text()));
    exit(-1);
}
```

> **The key constraints**:
> - On OHOS, `AppLocalDataLocation` maps to `preferencesDir` (a writable el2 sandbox where file IO is allowed and only `.so` dlopen is rejected — so a `.db` there is safe; see [[qt-harmonyos-platform-limits]] §dlopen)
> - `exit(-1)` on OHOS is intercepted by `libappspawn_helper.z.so` and converted into a `SIGABRT` cppcrash (`LastFatalMessage: Unexpected call: exit(-1)`); use `QCoreApplication::exit()` if you want a silent exit
> - **A separate driver plugin problem**: even with the right path, if `libqsqlite.so` isn't deployed into `libs/<abi>/sqldrivers/`, `open()` still returns false (a null driver, never touching the filesystem) — see [[qt-harmonyos-project-structure]] §6.2 + [runtime-fail-sqlite-open-database](../problems/runtime-fail-sqlite-open-database.md)
> - On desktop, it's worth adding `QCoreApplication::setOrganizationName()/setApplicationName()` so the path has a sensible `<App>` segment (on OHOS the path is determined by the bundleName, so it makes no difference)

---

## Porting checklist

When porting for real, work through these in order:

1. **The build system** — have you added the `ohos` branch and `QT += ohosextras` to qmake/CMake? (Pattern 7)
2. **The process model** — do you use QProcess? → by scenario: keep it when headless / startAppProcess for a Qt UI / startAbility for a non-Qt UI / startNoUiChildProcess when supervision is needed (Pattern 1)
3. **External invocations** — do you use QDesktopServices / JNI? → switch to startAbility (Pattern 2)
4. **Windows/dialogs** — is every standalone top-level window tagged as a subwindow? (Pattern 3)
5. **Lifecycle** — does closeEvent distinguish WindowStage / Ability / Internal? (Pattern 4)
6. **The filesystem** — are the setPermissions calls guarded by conditional compilation? (Pattern 5)
7. **Argument passing** — do you rely on argv positions? → switch to QCommandLineParser (Pattern 6)
8. **UI adaptation** — dark mode (Pattern 8), drag and drop (Pattern 9), monospace fonts (Pattern 10)
9. **HarmonyOS enhancements** — do you need floating windows (Pattern 11) or system sharing (Pattern 12)?

---

## References

- [Qt for HarmonyOS Code Patterns (Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS/code_patterns) — the original before/after examples
- [[qt-harmonyos-api-mapping]] — API compatibility mappings (argv, QProcess, the window model)
- [[qt-harmonyos-porting-workflow]] — The porting workflow and checklist
- [[qt-ohos-extras]] — The QtOhosExtras module API reference
