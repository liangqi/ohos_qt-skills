---
id: semantic-qt-ohos-extras-examples
type: semantic
domain: tech
tags: [qt, harmonyos, ohos, ohosextras, examples, cookbook, howto, ability, want, window, share, permissions, continuation, multimedia, serialport, fileshare, colortheme, contextmenu, nativewindow, startrequest]
created: 2026-07-21
updated: 2026-07-21
status: active
audience: public
refs: [semantic-qt-ohos-extras, semantic-qt-harmonyos-lifecycle, semantic-qt-harmonyos-window-model, semantic-qt-ohos-js-thread-gateway, semantic-qt-harmonyos-api-mapping]
summary: >
  A recipe book for the official QtOhosExtras examples: organizes all 24 examples by "developer question", giving each a one-line purpose, the APIs it uses,
  the minimal code pattern, and the source file path. It directly answers "how do I implement feature X (that I have on other platforms) in Qt on HarmonyOS?"
  The index covers: opening links / launching applications / launching for a result / launch options / preloading / application continuation / permission requests (including serial ports) / system sharing (sending + receiving) /
  file sharing permissions / the file recycle bin / keeping the screen on / corner radius / drag-resizing / light and dark themes / long-press context menus / native window ids / display ids / application versions / restarting /
  audio stream scenarios / embedded UIExtension / file descriptor passing (Want FD send + receive). All API signatures come from the Qt 5.12.12 source
  (commit 613336de) and are word-for-word identical to 5.15.16; the example sources live under qtohosextras/examples/qtohosextras/.
leader_summary: >
  Distills the 24 official QtOhosExtras examples into a "feature → API → code pattern" recipe book, so that developers (including commercial partners) facing
  "how do I implement this feature in Qt on HarmonyOS" can find the answer on one page, cutting repeated exploration and support costs.
impact: [developer support, commercial responses, faster migration]
deliverables: [knowledge page]
evidence: [the source at qtohosextras/examples/qtohosextras/, commit pending]
---

# A recipe book for the official QtOhosExtras examples

> **Purpose**: when a developer asks "how do I implement feature X (that I have on other platforms) in Qt on HarmonyOS?", check this page first.
> Each entry = a one-line purpose + the APIs used + the minimal code pattern + the source file path.

## Overview

Qt for HarmonyOS's `qtohosextras` module ships **24 official examples** (Qt 5.12.12, commit `613336de`; word-for-word identical to 5.15.16). This page reorganizes those 24 examples into a recipe book keyed by "developer question", with a directly copyable minimal code pattern and a source location for each.

> For the **full API tables** see [[qt-ohos-extras]] (145+ public APIs). This page only covers "which example to look at and how to use it" and doesn't repeat the full API tables.

**Prerequisite**: every example needs `QT += ohosextras` (some need extra modules — noted per entry). These APIs are private in Qt6 — see [[qt-harmonyos-qt6-status]].

**Example directory**: `qtohosextras/examples/qtohosextras/` (under `qtohosextras/` in the Qt source tree). `abilitycontext/` is a subdirectory project containing 9 Ability-related examples.

## 1. Launching abilities and contexts

### 1. Opening a link / opening a URL with the system
**The question**: how do I open a link in Qt on HarmonyOS the way `QDesktopServices::openUrl` does, and control whether it only goes through app linking (never the browser)?

**APIs**: `QtOhosExtras::QOhosAbilityContext::tryOpenLink(url)` / `tryOpenLink(url, options)`; `createOpenLinkOptions()` + `setAppLinkingOnly(bool)`.

**Pattern** (`abilitycontext/openlink/main.cpp`):
```cpp
auto ctx = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
auto opt = QtOhosExtras::createOpenLinkOptions();
opt->setAppLinkingOnly(appLinkingOnly);        // true = open only via app linking
if (!ctx->tryOpenLink(url, *opt)) { /* handle failure */ }
```
Source: `abilitycontext/openlink/main.cpp` — `QT += ohosextras widgets`

### 2. Launching an ability (fire-and-forget)
**The question**: how do I launch another Ability / application / child process?

> **Choosing a child-process mechanism** (added 2026-07-21 from field experience): "child process" depends on the scenario; there's no one-size-fits-all answer —
> - **A headless child process** → `QProcess` **works** (you can fork/exec a headless binary inside the HarmonyOS sandbox, so leave it as is)
> - **A UI + a Qt program** → `QtOhosExtras::startAppProcess()` / `startNewAbilityInstance()` (the Qt extras interfaces)
> - **A UI + a non-Qt program** → `QtOhosExtras::startAbility(want)` (this entry, the Want model)
> - **Headless but needing native HarmonyOS hosting** → `startNoUiChildProcess()` (an .so child process — see [[qt-ohos-extras]] §AppContext)
> For the decision tree see [[qt-harmonyos-api-mapping]] §1.

**APIs**: the namespace free function `QtOhosExtras::startAbility(const QOhosWant&)` → `QSharedPointer<QOhosOperationStatus>`; check the result with `->success()`. For details see the "Launching abilities" section of [[qt-ohos-extras]].

**Pattern** (`abilitycontext/wantfdssender/main.cpp` uses `startAbility(want)` to send a Want carrying fds):
```cpp
QtOhosExtras::QOhosWant want;
want.bundleName = "..."; want.abilityName = "...";
auto status = QtOhosExtras::startAbility(want);
if (!status.isNull() && status->success()) { /* ok */ }
```

### 3. Launching an ability for a result (the startActivityForResult equivalent)
**The question**: how do I do Android's `startActivityForResult` in Qt on HarmonyOS?

**APIs**: `QOhosAbilityContext::startAbilityForResult(const QOhosWant&)` / `(want, startOptions)` → returns a `QByteArray requestId` (**asynchronous**, non-blocking); the result comes back through the `startAbilityForResultResponseReceived(requestId, resultCode, optWant)` / `startAbilityForResultErrorResponseReceived(requestId)` signals.

**The key point**: you only need [[qt-ohos-js-thread-gateway]]'s `evalWithPromise` if you want to **block synchronously** for the result (QtOhosExtras has no synchronous variant).

**Pattern** (`abilitycontext/startabilityforresult/main.cpp`):
```cpp
auto ctx = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
QObject::connect(ctx.get(),
    &QtOhosExtras::QOhosAbilityContext::startAbilityForResultResponseReceived, this,
    [](QByteArray requestId, int resultCode, QSharedPointer<QtOhosExtras::QOhosWant> want) {
        // resultCode is the result code returned by the launched Ability
    });
QObject::connect(ctx.get(),
    &QtOhosExtras::QOhosAbilityContext::startAbilityForResultErrorResponseReceived, this,
    [](QByteArray requestId) { /* an error */ });
auto requestId = ctx->startAbilityForResult(want);   // or (want, *startOptions)
```
Source: `abilitycontext/startabilityforresult/main.cpp`

### 4. Launch options (window geometry / split screen / the splash screen)
**The question**: how do I specify the window's position and size, split-screen/floating mode, the splash screen's icon and background color, and the display id when launching an Ability?

**APIs**: `createStartOptions()` → `QSharedPointer<QOhosStartOptions>`; `createWindowCreateParams()` → `QOhosWindowCreateParams`. For the setters see the launch options section of [[qt-ohos-extras]] (geometry/bounds/WindowMode/DisplayId/WithAnimation/StartupVisibility/HideStartWindow/ProcessMode/StartWindowIcon/StartWindowBackgroundColor/SupportWindowModes/WindowCreateParams).

**Going further — launch requests and completion callbacks** (the example also demonstrates `QOhosStartRequest`, which the older KB didn't record — see the new-APIs section of [[qt-ohos-extras]]):
```cpp
auto startRequest = QtOhosExtras::createStartRequest(*startOptions);   // launching with a completion handler
QObject::connect(requestPtr, &QtOhosExtras::QOhosStartRequest::requestSucceeded, this,
    [](QtOhosExtras::QOhosElementName name, QString msg) { /* name.bundleName/moduleName/abilityName */ });
QObject::connect(requestPtr, &QtOhosExtras::QOhosStartRequest::requestFailed, this,
    [](QtOhosExtras::QOhosElementName name, QString msg) { /* failed */ });
auto status = QtOhosExtras::startAbility(want, *startRequest);
```
Source: `abilitycontext/startoptions/main.cpp` — `QT += ohosextras` (with qrc resources) — this example is the most complete configuration demonstrator, covering almost every StartOptions setter.

### 5. Preloading an ability (fast cold start)
**The question**: how do I create the window ahead of time the way the system's preloading does, and only show it when the user taps?

**APIs**: `QOhosAppContext::getAppLaunchWantInfo()` → use `launchReason()` to distinguish `Preload` from `StartAbility`; don't call `show()` during the preload phase — listen for `QOhosAbilityContext::newWantInfoReceived` and only `show()` once `launchReason==StartAbility`.

**Pattern** (`abilitycontext/preload/main.cpp`):
```cpp
const auto wantInfo = QtOhosExtras::QOhosAppContext::getAppLaunchWantInfo();
if (wantInfo->launchReason() == QtOhosExtras::QOhosWantInfo::LaunchReason::StartAbility) {
    window->show();                       // a normal launch, so show it right away
} else if (wantInfo->launchReason() == ...::Preload) {
    // preloading: the window is built but not shown; wait for a real StartAbility to show it
    QObject::connect(ctx.get(), &...::newWantInfoReceived, window,
        [w](auto wantInfo) {
            if (wantInfo->launchReason() == ...::StartAbility) w->show();
        });
}
```
Source: `abilitycontext/preload/main.cpp` — the `LaunchReason` enum: `Unknown/StartAbility/Continuation/PrepareContinuation/Preload`

### 6. Cross-device continuation
**The question**: how do I hand an application off from one HarmonyOS device to another (device continuation)?

**APIs**: `QOhosAbilityContext::setContinuationActive(bool)`; the `continueRequestReceived(QSharedPointer<QOhosOnContinueContext>)` signal; `tryGetOnContinueData(want)` to retrieve the handoff data; `context->setAgreeResponse(data)` / `setMismatchResponse()` / `sourceApplicationVersionCode()` for version comparison.

**Pattern** (`applicationcontinuation/main.cpp`):
```cpp
auto ability = QtOhosExtras::QOhosAbilityContext::getInstanceForMainWindow(window.windowHandle());
ability->setContinuationActive(true);                       // activate continuation
QObject::connect(ability.get(), &...::continueRequestReceived, [](auto context) {
    auto ver = QtOhosExtras::QOhosAppContext::instance()->getBundleInfo()->versionCode();
    if (context->sourceApplicationVersionCode() == ver)
        context->setAgreeResponse(QByteArray("handoff data"));   // agree
    else
        context->setMismatchResponse();                          // version mismatch
});
auto data = QtOhosExtras::tryGetOnContinueData(             // retrieve the handed-off data
    QtOhosExtras::QOhosAppContext::getAppLaunchWant());
```
Source: `applicationcontinuation/main.cpp` — `QT += core ohosextras` — for details see the continuation section of [[qt-harmonyos-lifecycle]]

### 7. Passing file descriptors (Want FDs)
**The question**: how do two Abilities pass an already-open file descriptor (fd) between them?

**The sender** (`abilitycontext/wantfdssender/main.cpp`) — put the fd into `want.fds`:
```cpp
QtOhosExtras::QOhosWant want;
auto file = QSharedPointer<QFile>::create(filePath);
file->open(QIODevice::ReadOnly);
int fd = file->handle();
want.fds.insert(QStringLiteral("keyFd%1").arg(i), fd);     // QMap<QString,int>
QtOhosExtras::startAbility(want);                           // send it to the target Ability
// Note: file must stay alive until startAbility returns
```

**The receiver** (`abilitycontext/wantfdsreceiver/main.cpp`) — take the fd out of the Want:
```cpp
auto ctx = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
QObject::connect(ctx.get(), &...::newWantInfoReceived, &window,
    [&window](QSharedPointer<QtOhosExtras::QOhosWantInfo> wantInfo) {
        const auto &want = wantInfo->want();
        for (auto it = want.fds.cbegin(); it != want.fds.cend(); ++it)
            /* it.key() / it.value() (an int fd) can be read()/fstat()'d directly */
    });
// Also handle the launch Want at startup (the continuation / being-launched scenarios)
auto launch = QtOhosExtras::QOhosAppContext::getAppLaunchWantInfo();
if (!launch.isNull()) window.handleWant(launch->want());
```
Source: `abilitycontext/wantfdsreceiver/` + `abilitycontext/wantfdssender/` — two Abilities run as a pair

## 2. Permissions

### 8. Runtime permission requests
**The question**: how do I ask the user for a runtime permission (clipboard/screen capture/bluetooth/location, etc.)?

**APIs**: `QOhosAbilityContext::getInstanceForMainWindow(qWindow)` to get the instance for the current main window; `requestPermissionFromUserIfNeeded(Permission)` (the enum) or `(const QString& namedPermission)` (a custom permission name); the result comes back through the `permissionRequestResponseReceived(Permission, PermissionResult)` / `namedPermissionRequestResponseReceived(QString, PermissionResult)` signals. `PermissionResult{permissionGranted, dialogShown}`.

**The predefined permission enum** (5 values): `ReadPasteboard / CustomScreenCapture / AccessBluetooth / ApproximatelyLocation / Location`, corresponding to string names such as `ohos.permission.READ_PASTEBOARD`.

**Pattern** (`abilitycontext/requestpermission/main.cpp`):
```cpp
auto ctx = QtOhosExtras::QOhosAbilityContext::getInstanceForMainWindow(window->windowHandle());
ctx->requestPermissionFromUserIfNeeded(
    QtOhosExtras::AppPermissions::Permission::Location);          // the enum
// or a custom permission name:
ctx->requestPermissionFromUserIfNeeded(QStringLiteral("ohos.permission.XXX"));
QObject::connect(ctx.get(), &...::permissionRequestResponseReceived, window,
    [](QtOhosExtras::AppPermissions::Permission p,
       QtOhosExtras::AppPermissions::PermissionResult r) {
        // r.permissionGranted / r.dialogShown
    });
```
Source: `abilitycontext/requestpermission/main.cpp` — **note**: you must call `window.show()` first (`getInstanceForMainWindow` needs a `windowHandle()`)

### 9. Serial port access permission
**The question**: how do I request HarmonyOS serial port access permission (a prerequisite for `QSerialPort`)?

**APIs** (not recorded in the older KB; source `qohosappcontext.h:53-54`):
- `QOhosAppContext::hasSerialPortAccessRight(const QString &portName) const` → bool
- `requestSerialPortAccessRightIfNeeded(const QString &portName)`
- The `serialPortAccessRightResponseReceived(portName, QSharedPointer<QObject> accessRightContext)` signal

**Pattern** (`serialportpermissions/main.cpp`):
```cpp
auto appCtx = QtOhosExtras::QOhosAppContext::instance();
appCtx->requestSerialPortAccessRightIfNeeded(portName);           // show the permission dialog
if (appCtx->hasSerialPortAccessRight(portName)) { /* already granted */ }
QObject::connect(appCtx, &...::serialPortAccessRightResponseReceived, this,
    [portName](QString respPort, QSharedPointer<QObject> ctx) {
        if (respPort != portName) return;
        // a non-null ctx = granted; the permission holds while you hold ctx, and is revoked when it's destroyed
        // The intended usage: keep ctx alive (e.g. as a window member) so closing the window revokes it
    });
```
Source: `serialportpermissions/main.cpp` — `QT += ohosextras serialport` (needs the Qt Serial Port module) — **a key constraint**: `accessRightContext` must be kept alive; destroying it revokes the permission (the example stores it as a `PermissionWindow` member, so closing the window revokes it)

## 3. System sharing

### 10. Sending a share (the ShareKit system sheet)
**The question**: how do I share text/a URL/a file through the system share sheet (the equivalent of Android's Intent.ACTION_SEND)?

**APIs**: `ShareKit::createContentRecord(mimeType, text)` / `createUrlRecord(QUrl)` / `createFileRecord(QFileInfo)` → `QSharedPointer<QOhosSharedRecord>`; `createControllerOptions()`; the entry point `QOhosAbilityContext::shareDataWithShareKit(records, controllerOptions)` → `QByteArray requestId`; the completion signals `shareKitCompleted(requestId, result)` / `shareKitPanelClosed(requestId)`.

**Record settings**: `setTitle/Label/Description`, `setThumbnail(QByteArray)` / `setThumbnailFilePath`, `setExtraData(QVariantMap)`.
**ControllerOptions**: `setAnchor(QPoint/QRect)`, `setSingleSelectionMode(bool)`, `setDefaultPreviewMode(bool)`, `setExcludedAbilities(QList<ShareAbilityType>)`.

**Pattern** (`abilitycontext/sharedata/main.cpp`):
```cpp
auto textRec = QtOhosExtras::ShareKit::createContentRecord(
    QMimeDatabase().mimeTypeForName("text/plain"), QStringLiteral("the content"));
textRec->setTitle("the title"); textRec->setThumbnail(logoBytes);
auto urlRec = QtOhosExtras::ShareKit::createUrlRecord(QUrl("https://..."));
auto fileRec = QtOhosExtras::ShareKit::createFileRecord(QFileInfo(path));

auto opts = QtOhosExtras::ShareKit::createControllerOptions();
opts->setSingleSelectionMode(true);
opts->setAnchor({x, y});

auto ctx = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
auto requestId = ctx->shareDataWithShareKit({textRec, urlRec, fileRec}, opts);
// The result: ctx's shareKitCompleted → result->targetAbilityName()
```
Source: `abilitycontext/sharedata/main.cpp` — `QT += ohosextras widgets` — includes rsc.qrc (the qt_logo.png thumbnail)

### 11. Receiving a share (being a share target)
**The question**: how do I make my application appear in the system share sheet's target list and receive the shared data?

**APIs**: your application is launched when something is shared to it, so retrieve the launch Want via `QOhosAppContext::getAppLaunchWant()` or listen for the `QOhosAbilityContext::newWantReceived(QOhosWant)` signal; `QOhosWantInfo::tryGetSharedRecordsFromShareKit()` retrieves the share records.

**Pattern** (`abilitycontext/sharedatareceiver/main.cpp`):
```cpp
auto ctx = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
QObject::connect(ctx.get(), &...::newWantReceived, this,
    [](QtOhosExtras::QOhosWant want) { /* want.parameters / want.uri etc. */ });
// Also handle the launch Want already present at startup (launched by a share)
```
Source: `abilitycontext/sharedatareceiver/main.cpp`

## 4. Files

### 12. Access permissions for files outside the sandbox (FileShare)
**The question**: how do I grant/revoke/check access to files outside the sandbox (working around the sandbox restrictions)?

**APIs**: the `FileShare` namespace, with batch operations over a `QList<PathPolicy>`: `persistPermission / revokePermission / activatePermission / deactivatePermission / checkPersistent`; `PathPolicy{path, operationModes}` with `OperationMode{Read, Write}` (QFlags).

**Pattern** (`filepermissions/main.cpp`, which has official qdoc):
```cpp
QtOhosExtras::FileShare::PathPolicy policy{filePath,
    QtOhosExtras::FileShare::OperationMode::Read | ...::Write};
auto result = QtOhosExtras::FileShare::persistPermission({policy});
// result->operationStatus()->success() + result->errorInfoList() (with path/error/errorMessage)
auto check = QtOhosExtras::FileShare::checkPersistent({policy});
// check->checkResultList()[i].result (a bool: whether it's granted)
```
Source: `filepermissions/main.cpp` — `doc/src/filepermissions.qdoc` (the official documentation, demonstrating PathPolicy creation + calling each API + logging the results)

### 13. Moving a file to the recycle bin
**The question**: how do I move a file to the recycle bin instead of deleting it outright?

**API**: `QtOhosExtras::moveFileToTrash(const QString &filePath)` → bool.

**Pattern** (`fileutils/main.cpp`):
```cpp
bool ok = QtOhosExtras::moveFileToTrash(filePath);   // returns whether it succeeded
```
Source: `fileutils/main.cpp` — there's also `authorizeFilePath(QWindow*, path)`, which shows the system authorization dialog for a path outside the sandbox (not demonstrated by this demo — see the utility functions section of [[qt-ohos-extras]])

## 5. Windows

### 14. Window corner radius
**The question**: how do I give a window rounded corners?

**API**: `QtOhosExtras::setWindowCornerRadius(QWindow*/QWidget*, double radius)` (overloaded, takes a `double`).

**Pattern** (`windowcornerradius/main.cpp`):
```cpp
auto *w = new QWidget; w->setWindowFlags(Qt::Window); w->resize(300, 300);
QtOhosExtras::setWindowCornerRadius(w, 16.0);   // call it before show()
w->show();
```
Source: `windowcornerradius/main.cpp`

### 15. Drag-resizing a window
**The question**: how do I enable the HarmonyOS window's drag-resize border?

**API**: `QtOhosExtras::setWindowDragResizable(QWindow*/QWidget*, bool)` (overloaded).

**Pattern** (`windowdragresize/main.cpp`):
```cpp
QtOhosExtras::setWindowDragResizable(window, enable);   // a toggle
// Combined with floating window mode:
QtOhosExtras::setShowWindowAsFloatWindowHint(floatWindow, true);
```
Source: `windowdragresize/main.cpp` — demonstrates both a subwindow and a floating window, each of which can be toggled drag-resizable independently

### 16. The native window id
**The question**: how do I get the HarmonyOS-side native window id (for cross-process window binding and so on)?

**API**: `QtOhosExtras::tryGetNativeWindowId(QWindow*)` → `QSharedPointer<double>` (the ArkTS-side `WindowProperties.id`).

**Pattern** (`nativewindowid/main.cpp`):
```cpp
auto id = QtOhosExtras::tryGetNativeWindowId(window->windowHandle());
// when id is non-null, *id is the native id; it isn't guaranteed valid for the object's whole lifetime
```
Source: `nativewindowid/main.cpp`

### 17. The display id
**The question**: how do I get the current screen's display id (for cross-screen/multi-monitor scenarios)?

**API**: `QtOhosExtras::tryGetScreenDisplayId(QScreen*)` → `QSharedPointer<double>`.

**Pattern** (`screendisplayid/main.cpp`):
```cpp
auto id = QtOhosExtras::tryGetScreenDisplayId(window->windowHandle()->screen());
```
Source: `screendisplayid/main.cpp`

### 18. Embedded UIExtension (binding multiple windows)
**The question**: how do I embed several Qt windows into the same Ability as UIExtensions?

**API**: `QtOhosExtras::setBundledAbilityAndQWindowBindingKeyForQWindow(QWindow*, const QString &key)`.

**Pattern** (`bundledembeddeduiextension/main.cpp`):
```cpp
widget->winId();                                        // make sure the QWindow exists
QtOhosExtras::setBundledAbilityAndQWindowBindingKeyForQWindow(
    widget->windowHandle(), QStringLiteral("A"));        // one key per window
```
Source: `bundledembeddeduiextension/main.cpp` — for details see the embedded subwindow / cross-process UIExtension section of [[qt-harmonyos-window-model]]

### 19. Keeping the screen on
**The question**: how do I keep the screen awake (for video/navigation applications)?

**API**: `QtOhosExtras::setWindowKeepScreenOn(QWindow*/QWidget*, bool)` (overloaded).

**Pattern** (`keepscreenon/main.cpp`):
```cpp
QtOhosExtras::setWindowKeepScreenOn(&window, keepOn);   // a checkbox toggle
```
Source: `keepscreenon/main.cpp`

### 20. Window privacy mode (screenshot blocking)
**The question**: how do I prevent a window's contents from being screenshotted or screen-recorded?

**API**: `QtOhosExtras::setWindowPrivacyMode(QWindow*, bool)` (no dedicated example — see the windows section of [[qt-ohos-extras]]).

> This API has no standalone demo but is recorded in the API tables; it's common in privacy scenarios (password fields, payments).

## 6. The application and its context

### 21. The application version
**The question**: how do I get my own application's version?

**API**: `QOhosAppContext::instance()->getBundleInfo()->versionCode()`.

**Pattern** (`appbundleinfo/main.cpp`):
```cpp
auto info = QtOhosExtras::QOhosAppContext::instance()->getBundleInfo();
auto versionCode = info->versionCode();
```
Source: `appbundleinfo/main.cpp` — `QT += core gui ohosextras`

### 22. Restarting the application (keeping or discarding the arguments)
**The question**: how do I restart the application and control whether the command line arguments are kept?

**API**: `QOhosAppContext::instance()->restartApp()` (Q_NORETURN, keeps the arguments) / `restartApp(const QOhosWant &want)` (Q_NORETURN, with a custom Want).

**Pattern** (`restartapp/main.cpp`):
```cpp
QtOhosExtras::QOhosAppContext::instance()->restartApp();           // keep all the arguments
auto want = QtOhosExtras::QOhosAppContext::getAppLaunchWant();
want.parameters = {};                                               // clear the parameters
QtOhosExtras::QOhosAppContext::instance()->restartApp(want);        // don't keep the arguments
```
Source: `restartapp/main.cpp` — the same example also demonstrates reading the launch arguments from `getAppLaunchWant().parameters`

### 23. Switching between light and dark themes
**The question**: how do I switch to a dark/light theme or follow the system?

**APIs**: `QOhosAppContext::setColorThemeMode(ColorThemeMode)`; `darkThemeActive()`; the `darkThemeActiveChanged(bool)` signal. `ColorThemeMode{LightTheme, DarkTheme, FollowSystemSetting}`.

**Pattern** (`colortheme/main.cpp`):
```cpp
auto appCtx = QtOhosExtras::QOhosAppContext::instance();
appCtx->setColorThemeMode(QtOhosExtras::QOhosAppContext::ColorThemeMode::DarkTheme);
QObject::connect(appCtx, &...::darkThemeActiveChanged, label,
    [](bool dark) { /* update the UI */ });
bool dark = appCtx->darkThemeActive();
```
Source: `colortheme/main.cpp`

### 24. Long-press context menus
**The question**: how do I pop up a context menu on a touchscreen the way a mouse right-click does?

**API**: `QOhosAppContext::enableContextMenuEventOnLongPress()` (**call it once before `app.exec()`; it applies globally**).

**A key constraint**: a `QContextMenuEvent` produced by a long press has `reason()` == `Other`, **not** `Mouse` — if you filter by reason, you must also accept `Other`.

**Pattern** (`contextmenuonlongpress/main.cpp`):
```cpp
QtOhosExtras::QOhosAppContext::instance()->enableContextMenuEventOnLongPress();
// then override contextMenuEvent:
void contextMenuEvent(QContextMenuEvent *e) override {
    // e->reason() == QContextMenuEvent::Other (a long press), not Mouse
}
```
Source: `contextmenuonlongpress/main.cpp`

## 7. Multimedia

### 25. Setting the audio stream scenario
**The question**: how do I set what an audio stream is for (alarm/ringtone/call/navigation, etc.), which affects the system volume category and the interruption policy?

**APIs**: `Multimedia::setAudioStreamUsageHintProperty(QObject*, AudioStreamUsageHint)` (applies to `QSound`/`QSoundEffect`); `tryGetAudioStreamUsageHintProperty`. The 14 hints: `Music/VoiceCommunication/VoiceAssistant/Alarm/VoiceMessage/Ringtone/Notification/Accessibility/Movie/Game/Audiobook/Navigation/VideoCommunication/Unknown`.

**Pattern** (`multimedia/audiostreamusagehint/main.cpp`):
```cpp
auto *soundEffect = new QSoundEffect(this);
QtOhosExtras::Multimedia::setAudioStreamUsageHintProperty(
    soundEffect, QtOhosExtras::Multimedia::AudioStreamUsageHint::Alarm);
soundEffect->setSource(QUrl("qrc:/test.wav"));
soundEffect->play();
// The same applies to QSound
```
Source: `multimedia/audiostreamusagehint/main.cpp` — `QT += ohosextras multimedia widgets` — includes resources.qrc (test.wav)

## A quick example-to-API index

| # | Example | The developer's question | Core APIs |
|---|---------|--------------------------|-----------|
| 1 | abilitycontext/openlink | Opening a link | `tryOpenLink` + `createOpenLinkOptions` |
| 2 | abilitycontext/wantfdssender | Launching an ability | `startAbility(want)` |
| 3 | abilitycontext/startabilityforresult | Launching for a result | `startAbilityForResult` + the response signals |
| 4 | abilitycontext/startoptions | Launch options | `createStartOptions` + `createStartRequest`/`QOhosStartRequest` |
| 5 | abilitycontext/preload | Preloading | `getAppLaunchWantInfo().launchReason()` + `newWantInfoReceived` |
| 6 | applicationcontinuation | Device handoff | `setContinuationActive` + `continueRequestReceived` |
| 7a | abilitycontext/wantfdssender | Sending an fd | `want.fds.insert(key, fd)` + `startAbility` |
| 7b | abilitycontext/wantfdsreceiver | Receiving an fd | `newWantInfoReceived` → `want.fds` |
| 8 | abilitycontext/requestpermission | Permission requests | `requestPermissionFromUserIfNeeded` + the response signals |
| 9 | serialportpermissions | Serial port permission | `requestSerialPortAccessRightIfNeeded`/`hasSerialPortAccessRight` |
| 10 | abilitycontext/sharedata | Sending a share | `shareDataWithShareKit` + `ShareKit::create*Record` |
| 11 | abilitycontext/sharedatareceiver | Receiving a share | `newWantReceived` + `tryGetSharedRecordsFromShareKit` |
| 12 | filepermissions | File permissions | `FileShare::persist/.../checkPersistent` + `PathPolicy` |
| 13 | fileutils | The recycle bin | `moveFileToTrash` |
| 14 | windowcornerradius | Corner radius | `setWindowCornerRadius` |
| 15 | windowdragresize | Drag-resizing | `setWindowDragResizable` + `setShowWindowAsFloatWindowHint` |
| 16 | nativewindowid | The native id | `tryGetNativeWindowId` |
| 17 | screendisplayid | The display id | `tryGetScreenDisplayId` |
| 18 | bundledembeddeduiextension | UIExtension | `setBundledAbilityAndQWindowBindingKeyForQWindow` |
| 19 | keepscreenon | Keeping the screen on | `setWindowKeepScreenOn` |
| 20 | — (no demo) | Screenshot blocking | `setWindowPrivacyMode` |
| 21 | appbundleinfo | The version | `getBundleInfo()->versionCode()` |
| 22 | restartapp | Restarting | `restartApp()` / `restartApp(want)` |
| 23 | colortheme | Themes | `setColorThemeMode` + `darkThemeActiveChanged` |
| 24 | contextmenuonlongpress | Long-press menus | `enableContextMenuEventOnLongPress` |
| 25 | multimedia/audiostreamusagehint | Audio scenarios | `Multimedia::setAudioStreamUsageHintProperty` |

> Other APIs have no standalone demo: `setWindowPrivacyMode` (screenshot blocking), `authorizeFilePath` (a dialog authorizing access to a path outside the sandbox), `setInAppOnlyPasteboardShareOption` (in-app-only clipboard), `setSurfaceBackgroundColor`, `setMainWindowGeometryPersistenceHint`, `startNoUiChildProcess`, `startAppProcess`, `startAbilityByType`, `setFont...` and so on — see the full API tables in [[qt-ohos-extras]].

## References

| Source | Notes |
|--------|-------|
| Qt source examples | `qtohosextras/examples/qtohosextras/` (24 examples, Qt 5.12.12 commit `613336de`, word-for-word identical to 5.15.16 commit `962aa625`) — fully scanned 2026-07-21 |
| Qt source headers | `qtohosextras/src/ohosextras/*.h` (API signature verification: `qohosappcontext.h` for serial ports, `qohosstartrequest.h` + `qohosbundlemanager.h` for launch requests) |
| Official documentation | `filepermissions/doc/src/filepermissions.qdoc` (the official qdoc for the filepermissions example, demonstrating PathPolicy creation and calling each API) |
| Qt Wiki | [Qt OHOS Extras Examples](https://wiki.qt.io/Qt_for_HarmonyOS/qtohosextras_doc/Qt_Ohos_Extras_Examples) |

## Related context

- [[qt-ohos-extras]] — The full table of the QtOhosExtras module's 145+ APIs (the source of this page's API details)
- [[qt-harmonyos-lifecycle]] — Lifecycle, Want, cross-device continuation (examples 5 and 6)
- [[qt-harmonyos-window-model]] — The window model, floating windows, embedded subwindows/UIExtension (examples 14-20)
- [[qt-ohos-js-thread-gateway]] — Making `startAbilityForResult`'s result synchronous (an async signal → a synchronous wait)
- [[qt-harmonyos-api-mapping]] — Cross-platform API migration mappings (before/after comparisons)

## Results summary

| Field | Content |
|-------|---------|
| Leadership summary | Distills the 24 official QtOhosExtras examples into a "feature → API → code pattern" recipe book, so developers facing "how do I implement this feature in Qt on HarmonyOS" can find the answer on one page |
| Impact | Developer support, commercial responses, faster application migration |
| Deliverable | A knowledge page |
| Evidence | A full scan of the source at `qtohosextras/examples/qtohosextras/` + header signature verification |
| How to reuse it | When a developer asks "how do I implement X in Qt on HarmonyOS", cite the matching entry on this page directly |
