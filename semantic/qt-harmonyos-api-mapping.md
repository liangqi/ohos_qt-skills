---
id: semantic-qt-harmonyos-api-mapping
type: semantic
domain: tech
tags: [qt, harmonyos, api, mapping, porting, qprocess, window, filesystem, sharing, context-menu, touch]
created: 2026-06-02
updated: 2026-08-15
status: active
audience: public
refs: [semantic-qt-harmonyos-api, semantic-qt-harmonyos-code-patterns, semantic-qt-ohos-extras]
summary: >
  The Qt API adapter mapping table for HarmonyOS platform capabilities: 13 categories of before/after comparisons — process management, inter-application communication,
  window management, close events, the filesystem, launch arguments, drag and drop, theme and appearance, time zones, threading,
  sharing, application continuation, and long-press context menus. Each category has a mapping table and code examples.
---

# HarmonyOS platform capabilities → the Qt API adapter mapping table

> This document collects 13 categories of Qt API adapter and before/after code. The platform concepts come from the common knowledge base: for Stage/UIAbility, Want, and launchType, see [[ohos-common-kb/semantic/stage-uiability-lifecycle|The Stage model and the UIAbility lifecycle]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/stage-uiability-lifecycle.md)); for the Window/XComponent/focus seam, see [[ohos-common-kb/semantic/arkui-window-xcomponent-model|The ArkUI window and XComponent hosting model]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/arkui-window-xcomponent-model.md)); for the file, loader, threading, and time zone limitations, see [[ohos-common-kb/semantic/harmonyos-platform-limits|HarmonyOS platform limitations]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-platform-limits.md)). This page maintains only the Qt APIs, QtOhosExtras/QPA, and the Qt code rewrites.

---

## 1. Process management

To start a child process or external program on HarmonyOS, choose your approach based on "does the child have a UI?" and "is it a Qt program?" — **there's no one-size-fits-all answer**. The old KB's blanket claim that "QProcess is unavailable/not recommended" was inaccurate (corrected 2026-07-21 based on domain expertise; see "Source and correction" at the end of this section).

**The decision tree**:

| Child process scenario | Recommended approach | Notes |
|---|---|---|
| **No UI** (a background/compute task) | `QProcess` **works**; leave it as-is | ★ You can fork/exec a headless binary inside the HarmonyOS sandbox; no need to change QProcess |
| A UI + a Qt program | `QtOhosExtras::startAppProcess()` / `startNewAbilityInstance()` | Use the Qt extras interfaces to run the child as a UI-bearing Ability |
| A UI + a non-Qt program | `QtOhosExtras::startAbility(want)` | Launch any Ability through the Want model (including system/third-party applications) |
| No UI but needing native HarmonyOS supervision | `QtOhosExtras::QOhosAppContext::startNoUiChildProcess(libName, args)` | The child runs as a `.so` supervised by the Child Process Manager, with no `QApplication`/GUI pipeline |

| Other platform API | HarmonyOS replacement | Notes |
|---|---|---|
| `QProcess::start(program)`, no UI | `QProcess` works as-is | ★ A headless child process doesn't need QProcess replaced |
| `QProcess::start(program)`, a UI and Qt | `QtOhosExtras::startAppProcess(name, want)` / `startNewAbilityInstance(widget)` | Use the extras interfaces to start a UI-bearing Qt child |
| `QProcess::start(program)`, a UI and non-Qt | `QtOhosExtras::startAbility(want)` | Launch the target Ability through the Want model |
| `QProcess::start(program)`, no UI but supervised | `QtOhosExtras::QOhosAppContext::startNoUiChildProcess(libName, args)` | A native HarmonyOS .so child process (the Child Process Manager) |
| `QProcess::startDetached(program)` | `QtOhosExtras::startAppProcess(name, want)` | Starts a new application process |
| `QProcess` for a GUI child | `QtOhosExtras::startAbility(want)` / `startAppProcess()` | A UI-bearing child uses Ability/Want or the extras interfaces; you can't start a GUI with a bare QProcess |
| `system()`, `popen()`, `exec*()` | Headless computation can keep using them; with a UI, switch to `startAbility`/`startAppProcess` | No longer a blanket "unavailable" |

### Before

```cpp
QProcess proc;
proc.start("worker", {"--task", "compute"});
proc.waitForFinished();
QString output = proc.readAllStandardOutput();
```

### After

Headless (keep QProcess; no change needed):

```cpp
// QProcess stays as-is — a headless compute child process runs fine inside the HarmonyOS sandbox
QProcess proc;
proc.start("worker", {"--task", "compute"});
proc.waitForFinished();
```

Headless but with native HarmonyOS supervision (needing a .so child process):

```cpp
#include <QtOhosExtras/qohosappcontext.h>

QtOhosExtras::QOhosAppContext::startNoUiChildProcess(
    "libWorker.so",
    QStringList{"--task", "compute"}
);
// The child is loaded as a .so library and supervised by the Child Process Manager (no GUI pipeline)
```

> **Source and correction** (2026-07-21): this section used to say "QProcess is unavailable or not recommended in all cases". Corrected from domain expertise — **QProcess works for headless child processes**, and blanket-replacing it with `startNoUiChildProcess` is misleading. `startNoUiChildProcess` is HarmonyOS's native .so supervision mechanism (an alternative, for when you need process supervision), not the only replacement for QProcess. Source: a user (a domain expert); cross-reference [[qt-harmonyos-dev-guide]]'s `uiless_child_process` (that wiki page describes the native supervision mechanism, not a prohibition on QProcess).

> **QFileDialog works natively**: QFileDialog needs no `#ifdef` alternative on OHOS — the platform plugin `QOhosPlatformIntegrationPlugin` has built-in native file dialog support, and `getSaveFileName`/`getOpenFileName` can be used directly. See [ohos-qfiledialog-native-support](../problems/ohos-qfiledialog-native-support.md).

---

## 2. Inter-application communication

On HarmonyOS, Qt uses QtOhosExtras' Want adapter for calling other applications and opening URLs; the Want matching semantics themselves are maintained in the common knowledge base.

| Other platform API | HarmonyOS replacement | Notes |
|---|---|---|
| `QDesktopServices::openUrl(url)` | `startAbility(want)` with `want.uri` | Implicit matching; the system picks a suitable application |
| `QDesktopServices::openUrl(mailto:)` | `startAbility(want)` with an action | Set `want.action` to the corresponding action |
| `xdg-open` / `ShellExecute` | `startAbility(want)` | Use the Want model uniformly |
| D-Bus calls | Not available on OHOS | Use Want-based IPC |
| `QProcess` to launch other apps | `startAbility(want)` | Explicit or implicit matching of the target Ability |

### Before

```cpp
QDesktopServices::openUrl(QUrl("https://example.com"));
```

### After

```cpp
#include <QtOhosExtras/qohoswant.h>

QtOhosExtras::QOhosWant want;
want.uri    = "https://example.com";
want.action = "ohos.want.action.viewData";
QtOhosExtras::startAbility(want);
```

---

## 3. Window management

Qt's QPA maps the platform window hierarchy onto `QWindow`/`QWidget`. A standalone `QDialog` (with no parent) becomes a new main window in that adapter, so it must be explicitly tagged as a subwindow.

| Other platform API | HarmonyOS behavior / replacement | Notes |
|---|---|---|
| A standalone `QDialog()` | Becomes a new main window | Set a `transientParent` or use `tagWindowOrWidgetAsSubWindowOf()` |
| `Qt::Popup` | Falls back to subwindow mode automatically | Generally works |
| `setMask()` on the main window | Not supported | Use a subwindow or custom painting instead |
| `showFullScreen()` on the 1st window | Not supported at launch | Call it after the window is shown |
| `showMinimized()` on a subwindow | Not supported | Only the main window can be minimized |
| `hide()` on the main window | Falls back to minimizing | Use `showMinimized()` instead |
| `Qt::WindowStaysOnTopHint` | Main window only, and only in PC mode | No effect on mobile |
| `Qt::ApplicationModal` | Subwindow scenarios only | Not supported for the main window |

### Before

```cpp
QDialog *dlg = new QDialog();   // no parent
dlg->exec();
```

### After

```cpp
// Option 1: set a parent
QDialog *dlg = new QDialog(mainWindow);
dlg->exec();

// Option 2: tag it explicitly as a subwindow
#include <QtPlatformHeaders/QOhosFunctions>
QDialog *dlg = new QDialog();
QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(dlg, mainWindow);
dlg->exec();
```

---

## 4. Close event handling

The Qt adapter maps both a user closing a window and system lifecycle callbacks onto `closeEvent()`, so you must handle them differently based on the root cause.

| Other platform behavior | HarmonyOS behavior | Notes |
|---|---|---|
| `closeEvent()` means the user closed it | It may be a system lifecycle callback | Check the root cause |
| `event->ignore()` prevents closing | Works in level 1 scenarios | Level 2 (a forced system reclaim) has a time limit |

### After

For handling closeEvent by root cause (distinguishing WindowStageClose / AbilityClose / InternalClose), see [[qt-harmonyos-lifecycle]] §the three levels of close interception.

---

## 5. The filesystem

Below is how the platform's sandbox/loader limitations manifest in Qt's file APIs; the platform-level causes and evidence boundaries come from the common knowledge base.

| Other platform API | HarmonyOS behavior | Notes |
|---|---|---|
| `QFile::setPermissions()` on an existing file | A no-op (a silent failure) | Wrap it in `#ifndef Q_OS_OHOS` |
| `QFile::link()` / `symlink()` | Returns `EACCES` | Copy the file instead |
| `QFileInfo::isFile()` on system paths | Returns `false` | Combine `exists()` + `isExecutable()` to decide |
| `QStandardPaths::findExecutable()` | Can't find system executables | System binaries aren't visible inside the sandbox |
| `QStandardPaths::PublicShareLocation` | Returns an empty string | That path doesn't exist |
| `dlopen()` from writable paths | Rejected (`EINVAL`) | `.so` files can only be loaded from the application's lib directory |
| `chmod()`, `fchmod()` | Not supported | File permissions inside the sandbox are managed by the system |

### Before

```cpp
QFile file("data.bin");
file.open(QIODevice::WriteOnly);
file.write(payload);
file.close();
file.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
```

### After

```cpp
QFile file("data.bin");
file.open(QIODevice::WriteOnly);
file.write(payload);
file.close();
#ifndef Q_OS_OHOS
file.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
#endif
// The OHOS sandbox manages file permissions automatically; setPermissions is a no-op
```

---

## 6. Launch arguments

A HarmonyOS application's `argv` layout differs from desktop platforms: `argv[0]` points at the `.so` library rather than an executable, and your own arguments aren't at a fixed position.

| Other platform behavior | HarmonyOS behavior | Notes |
|---|---|---|
| `argv[0]` = the executable path | `argv[0]` = the library file path (`.so`) | Don't use `argv[0]` to infer the application directory |
| Your arguments start at `argv[1]` | `want.uri` may occupy `argv[1]` | The argument positions aren't fixed |
| Fixed argument positions | The positions change with the system version | Use `QCommandLineParser` to parse them |

### Before

```cpp
int main(int argc, char *argv[])
{
    QCoreApplication app(argc, argv);
    QString taskFile = argv[1];   // assumes the first argument is the task file
    // ...
}
```

### After

```cpp
int main(int argc, char *argv[])
{
    QCoreApplication app(argc, argv);

    QCommandLineParser parser;
    parser.addOption({"task", "Task file path", "file"});
    parser.process(app);

    QString taskFile = parser.value("task");
    // QCommandLineParser gets the arguments reliably, without depending on position
}
```

---

## 7. Drag and drop

During a drag on HarmonyOS, only the MIME type list is available in the `dragEnterEvent` and `dragMoveEvent` phases; the full data is only available in `dropEvent`.

| Other platform behavior | HarmonyOS behavior | Notes |
|---|---|---|
| Reading `QMimeData` in `dragEnterEvent` | Only the MIME types are available | You can decide whether to accept the drop based on the MIME type |
| Reading `QMimeData` in `dragMoveEvent` | Only the MIME types are available | Same as above |
| Reading `QMimeData` in `dropEvent` | The full data is available | Read the actual content in the drop phase |

### Before

```cpp
void MyWidget::dragEnterEvent(QDragEnterEvent *event)
{
    if (event->mimeData()->hasText()) {          // reads the data
        event->acceptProposedAction();
    }
}

void MyWidget::dropEvent(QDropEvent *event)
{
    QString text = event->mimeData()->text();    // reads the data
    processText(text);
}
```

### After

```cpp
void MyWidget::dragEnterEvent(QDragEnterEvent *event)
{
    // Only check the MIME type; don't read the actual data
    if (event->mimeData()->formats().contains("text/plain")) {
        event->acceptProposedAction();
    }
}

void MyWidget::dropEvent(QDropEvent *event)
{
    // The full data is only available in the drop phase
    QString text = event->mimeData()->text();
    processText(text);
}
```

---

## 8. Theme/appearance

HarmonyOS dark mode must be enabled to follow the system setting through a QtOhosExtras interface, and the system has no built-in monospace font.

| Other platform behavior | HarmonyOS replacement | Notes |
|---|---|---|
| Platform-native dark mode | `QOhosAppContext::setColorThemeMode(FollowSystemSetting)` | Set it through QtOhosExtras |
| `QPalette` customization | Still works | You need to listen for the `darkThemeActiveChanged` signal to switch dynamically |
| A system monospace font | Not available | Bundle your own font with `addApplicationFont()` |

### Before

```cpp
// On desktop platforms, dark mode follows the system automatically
QApplication app(argc, argv);
```

### After

```cpp
#include <QtOhosExtras/qohosappcontext.h>

QApplication app(argc, argv);

// Enable following the system's dark/light mode
auto *ctx = QtOhosExtras::QOhosAppContext::instance();
ctx->setColorThemeMode(
    QtOhosExtras::QOhosAppContext::ColorThemeMode::FollowSystemSetting
);

// Listen for theme changes and update your custom palette
QObject::connect(
    ctx,
    &QtOhosExtras::QOhosAppContext::darkThemeActiveChanged,
    [](bool dark) {
        QPalette pal;
        if (dark) {
            pal.setColor(QPalette::Window, Qt::black);
            pal.setColor(QPalette::WindowText, Qt::white);
        }
        qApp->setPalette(pal);
    }
);
```

---

## 9. Time zones

Qt's response to the platform's time zone resource limitations is to use the verified ICU backend; the platform resource conclusions aren't duplicated on this page.

| Other platform behavior | HarmonyOS replacement | Notes |
|---|---|---|
| `QTimeZone` with the tz backend | There's no tzdata | Use the ICU backend |

### Before

```cpp
QTimeZone tz("Asia/Shanghai");
QDateTime dt = QDateTime::currentDateTime().toTimeZone(tz);
```

### After

```cpp
// Make sure Qt was built with the ICU backend enabled
// The QTimeZone API is unchanged, but underneath it depends on ICU rather than tzdata
QTimeZone tz("Asia/Shanghai");   // works, provided ICU is available
QDateTime dt = QDateTime::currentDateTime().toTimeZone(tz);
```

> **Note**: when building Qt for OHOS, confirm the ICU libraries are linked, or `QTimeZone` may return an invalid time zone.

---

## 10. Threading

Qt's response to the platform's threading limitations is cooperative termination — `QThread::quit()`, interruption flags, and so on — rather than relying on `pthread_cancel`.

| Other platform behavior | HarmonyOS behavior | Notes |
|---|---|---|
| Macros such as `PTHREAD_CANCEL_DISABLE` | They're defined, but the functions are unavailable | Guard with `#ifdef` or `#undef` |

### Before

```cpp
#include <pthread.h>

// Disable thread cancellation
int oldState;
pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldState);
doCriticalWork();
pthread_setcancelstate(oldState, nullptr);
```

### After

```cpp
#include <pthread.h>

#ifndef Q_OS_OHOS
int oldState;
pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldState);
#endif

doCriticalWork();

#ifndef Q_OS_OHOS
pthread_setcancelstate(oldState, nullptr);
#endif
// OHOS doesn't support the pthread_cancel family; use cooperative termination instead (e.g. QThread::quit + wait)
```

---

## 11. Sharing

HarmonyOS provides the ShareKit framework for system-level sharing, invoked through `QOhosAbilityContext`.

| Other platform behavior | HarmonyOS replacement | Notes |
|---|---|---|
| A platform share sheet (iOS/Android) | `QOhosAbilityContext::shareDataWithShareKit()` | Create share records with `ShareKit::create*Record()` |

### Before

```cpp
// iOS: UIActivityViewController
// Android: Intent.ACTION_SEND
// Desktop: no unified sharing mechanism
```

### After

```cpp
#include <QtOhosExtras/qohossharekit.h>

auto textRecord = QtOhosExtras::ShareKit::createContentRecord(
    QMimeDatabase().mimeTypeForName("text/plain"),
    QStringLiteral("Check out this app!"));
auto urlRecord = QtOhosExtras::ShareKit::createUrlRecord(
    QUrl("https://example.com"));

auto context = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
context->shareDataWithShareKit({textRecord, urlRecord}, nullptr);
// The system share sheet appears and the user picks a target application
```

---

## 12. Application continuation

HarmonyOS supports cross-device application continuation (similar to Apple's Handoff), receiving continuation requests through the `continueRequestReceived` signal, with the serialized state limited to 100 KB.

| Other platform behavior | HarmonyOS replacement | Notes |
|---|---|---|
| Handoff / Continuity (Apple) | The `continueRequestReceived` signal | The serialized state must be < 100 KB |

### Before

```cpp
// Apple: NSUserActivity
// Desktop: no equivalent
```

### After

```cpp
#include <QtOhosExtras/qohosappcontext.h>
#include <QtOhosExtras/qohosuiabilitycontext.h>

auto context = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
context->setContinuationActive(true);

QObject::connect(context.get(),
    &QtOhosExtras::QOhosUiAbilityContext::continueRequestReceived,
    [](const QSharedPointer<QtOhosExtras::QOhosOnContinueContext> &request) {
        QByteArray stateData = serializeState();
        Q_ASSERT(stateData.size() < 100 * 1024);
        request->setAgreeResponse(stateData);
    });

auto launchInfo = QtOhosExtras::QOhosAppContext::getAppLaunchWantInfo();
if (launchInfo) {
    auto stateData = QtOhosExtras::tryGetOnContinueData(launchInfo->want());
    if (stateData)
        deserializeState(*stateData);
}
```

---

## 13. Long-press context menus on touch

By default, a HarmonyOS touchscreen **doesn't** generate a `QContextMenuEvent` on a long press (on desktop, a right click does so automatically). You must enable it explicitly through QtOhosExtras.

| Other platform behavior | HarmonyOS replacement | Notes |
|---|---|---|
| A right click automatically produces a `QContextMenuEvent` | `QOhosAppContext::enableContextMenuEventOnLongPress()` | Once enabled, a long press triggers it with the reason `Other` |

### Before

```cpp
// Desktop: a right click delivers contextMenuEvent with no extra setup
QApplication app(argc, argv);
// QWidget::contextMenuEvent() is triggered by a right click automatically
```

### After

```cpp
#include <QtOhosExtras>

QApplication app(argc, argv);
// Must be called once before exec(); it applies globally
QtOhosExtras::QOhosAppContext::instance()->enableContextMenuEventOnLongPress();
// From then on, a touch long press triggers contextMenuEvent() with QContextMenuEvent::Other
```

> **Note**: a `QContextMenuEvent` produced by a long press has `reason()` == `QContextMenuEvent::Other` (not `Mouse`). If your handler filters by reason, it must also accept `Other`. See [[qt-ohos-extras]] §Touch long press.

---

## Quick reference: the conditional compilation macro

```cpp
#ifdef Q_OS_OHOS
    // The HarmonyOS / OpenHarmony code path
#else
    // The desktop/other platform code path
#endif
```

## Migration checklist

1. **Process management** — keep QProcess as-is when headless; use startAppProcess for a Qt UI; use startAbility for a non-Qt UI; use startNoUiChildProcess when headless work needs native supervision
2. **Inter-application communication** — replace `QDesktopServices::openUrl` with the Want mechanism
3. **Window management** — give every standalone `QDialog` a parent or tag it as a subwindow
4. **Close events** — check the root cause in `closeEvent`, distinguishing a user action from a system reclaim
5. **The filesystem** — remove `setPermissions` and `symlink` calls, guarded by conditional compilation
6. **Launch arguments** — switch to `QCommandLineParser` and don't depend on `argv` positions
7. **Drag and drop** — only check MIME types in `dragEnter`/`dragMove`
8. **Themes** — call `setColorThemeMode` and bundle a monospace font
9. **Time zones** — confirm the ICU backend is linked
10. **Threading** — guard the `pthread_cancel`-related calls
11. **Sharing** — integrate ShareKit
12. **Continuation** — implement `continueRequestReceived` and keep the state size in check
13. **Touch long press** — call `enableContextMenuEventOnLongPress()` to enable long-press context menus (once, before exec)

## References

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | Accumulated from day-to-day Qt HarmonyOS porting work |
