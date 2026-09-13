---
id: semantic-qt-harmonyos-lifecycle
type: semantic
domain: tech
tags: [qt, harmonyos, lifecycle, ability, want, close-event, continuation, sharing]
created: 2026-06-02
updated: 2026-08-14
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-ohos-extras, semantic-qt-harmonyos-api]
summary: >
  The Qt adapter for the Stage/UIAbility lifecycle: bridging platform callbacks to Qt's main/event loop, launching other applications
  (explicit/implicit Wants), being launched by other applications (module.json5 skills), multi-instance management,
  three levels of close interception (WindowStageClose/AbilityClose/InternalClose),
  application continuation (cross-device handoff), sharing (ShareKit), UI-less child processes, argv assembly rules, and theme management.
---

# The Qt adapter for the Stage/UIAbility lifecycle

> For the platform semantics of Stage/UIAbility, WindowStage, Want, skills, launchType, and save/restore, the authority is the common knowledge base's [[ohos-common-kb/semantic/stage-uiability-lifecycle|The Stage model and the UIAbility lifecycle]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/stage-uiability-lifecycle.md)). This page maintains only how platform callbacks map onto Qt's `main()`/event loop, `QWindow`/`QDialog`, QtOhosExtras, argv, close interception, and the continuation and sharing adapters.

## The Qt startup bridge

The Qt adaptation layer bridges platform lifecycle events to a standard Qt `main()` entry point. The authoritative ordering of the platform callbacks is in the common knowledge base; what follows shows only the thread, shared library, and event loop seams the Qt glue layer adds.

### The startup sequence

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. The system launches the UIAbility (the Stage model entry point)    │
│    ↓                                                                 │
│ 2. The UIAbility starts the Qt thread through NAPI                   │
│    ↓                                                                 │
│ 3. The system loads the Qt shared library (.so) and calls main()     │
│    ↓                                                                 │
│ 4. The main window is created and shown inside the WindowStage       │
└──────────────────────────────────────────────────────────────────────┘
```

### Each stage in detail

| Stage | Who does it | Notes |
|-------|-------------|-------|
| 1. Launch the UIAbility | The system | The system creates the UIAbility instance based on `module.json5` and calls its lifecycle callbacks such as `onCreate()` and `onWindowStageCreate()` |
| 2. NAPI starts the Qt thread | The QPA plugin | Qt's ArkTS-side adaptation layer starts the Qt runtime on a separate thread through NAPI (Native API) |
| 3. Load the .so and call main() | The Qt runtime | It loads the shared library your application builds and runs the standard C++ `main(int argc, char *argv[])` |
| 4. Create the main window | Your code | After `QApplication`/`QGuiApplication` initializes, you create the main window and the QPA plugin embeds it in the WindowStage automatically |

> **The key point**: you only write a standard Qt `main()`; the Stage model's ArkTS side is handled automatically by the QPA plugin, so you don't write Ability lifecycle code by hand.

## Launching other applications

HarmonyOS uses **Want** objects for inter-Ability communication, similar to Android's Intent. In Qt they're wrapped by `QtOhosExtras::QOhosWant`.

### Explicit matching

Specify the target application's `bundleName` and `abilityName` directly to launch one specific Ability.

```cpp
#include <QtOhosExtras/qohoswant.h>
#include <QtOhosExtras/qohosuiabilitycontext.h>

QtOhosExtras::QOhosWant want;
want.bundleName = "com.example.targetapp";
want.abilityName = "MainAbility";

// Optional: attach parameters
QJsonObject params;
params.insert("key", "value");
want.parameters = params;

QtOhosExtras::startAbility(want);
```

**When it applies**: you know the target application's bundle and Ability name exactly, such as jumping to another application of your own.

### Implicit matching

Describe your intent with an `action`, `type`, and `uri`, and let the system pick a matching Ability.

```cpp
QtOhosExtras::QOhosWant want;
want.action = "ohos.want.action.viewData";   // the action: view data
want.type = "text/plain";                     // the data type
want.uri = "content://example/data";          // the data URI
QtOhosExtras::startAbility(want);
```

**When it applies**: you don't care which application handles it — sharing text, opening a web page, viewing an image, and so on.

### Explicit vs. implicit

| Property | Explicit matching | Implicit matching |
|----------|-------------------|-------------------|
| How you specify it | `bundleName` + `abilityName` | `action` + `type` + `uri` |
| Target certainty | Uniquely determined | The system chooses; a picker may appear |
| Typical use | A precise jump between applications | A general intent (share, open, view) |
| Needs exported | Yes | Yes (plus a matching skills entry) |

## Being launched by other applications

### 1. Declare skills in module.json5

Declare the intents your Ability can respond to in `module.json5`:

```json
{
  "abilities": [{
    "name": "QAbility",
    "launchType": "specified",
    "exported": true,
    "skills": [{
      "entities": ["entity.system.home"],
      "actions": [
        "action.system.home",
        "ohos.want.action.viewData"
      ],
      "uris": [
        { "type": "*/*" }
      ]
    }]
  }]
}
```

| Field | Notes |
|-------|-------|
| `entities` | The Ability's category identifiers; `entity.system.home` means it can be launched from the home screen |
| `actions` | The actions it can respond to, such as `ohos.want.action.viewData` for viewing data |
| `uris` | The data URI formats it can handle, with `type` giving the MIME type |

> `exported: true` is mandatory, or other applications can't launch this Ability.

### 2. Listen for newWantReceived in code

When an already-running application is launched again by another application, the `newWantReceived` signal fires:

```cpp
QObject::connect(
    QtOhosExtras::QOhosUiAbilityContext::instance(),
    &QtOhosExtras::QOhosUiAbilityContext::newWantReceived,
    this,
    [](QtOhosExtras::QOhosWant want) {
        qDebug() << "Action:" << want.action;
        qDebug() << "URI:" << want.uri;

        // Handle the attached parameters
        if (want.parameters.contains("key")) {
            QString value = want.parameters.value("key").toString();
            // act on the parameter
        }
    }
);
```

### Receiving a Want on a cold vs. warm start

| Scenario | How to get it |
|----------|---------------|
| Cold start (the application isn't running) | `QOhosAppContext::getAppLaunchWantInfo()->want()` gives the launch Want |
| Warm start (the application is already in the background) | Connect to the `newWantReceived` signal to receive the new Want |

## Multi-instance management

HarmonyOS supports three multi-instance modes for different scenarios:

### Comparing the modes

| Mode | Processes | Windows | How it works | When it applies |
|------|-----------|---------|--------------|-----------------|
| **Singleton** | 1 | 1 | The existing instance handles new requests through `newWantReceived` | Most applications, where state is shared |
| **Multi-instance, single process** | 1 | N | Create a new window instance in `newWantReceived` | Multi-document editors |
| **Multi-instance, multi-process** | N | N | `startAppProcess()` starts a new process | Scenarios needing process isolation |

### Singleton mode

The default behavior. A new launch request triggers the existing instance's `newWantReceived`, where you update the UI or navigate:

```cpp
QObject::connect(
    QtOhosExtras::QOhosUiAbilityContext::instance(),
    &QtOhosExtras::QOhosUiAbilityContext::newWantReceived,
    [](QtOhosExtras::QOhosWant want) {
        // The existing instance handles the new request, e.g. opening a new document
        openDocument(want.uri);
    }
);
```

### Multi-instance, single process

Create a new window in `newWantReceived`, sharing the same process memory:

```cpp
QObject::connect(
    QtOhosExtras::QOhosUiAbilityContext::instance(),
    &QtOhosExtras::QOhosUiAbilityContext::newWantReceived,
    [](QtOhosExtras::QOhosWant want) {
        // Create a new main window instance
        auto *window = new MainWindow();
        window->loadFromWant(want);
        window->show();
    }
);
```

### Multi-instance, multi-process

Call `startAppProcess()` to start a separate process; you need to configure process isolation in `module.json5`:

```cpp
// Start a new process
QtOhosExtras::startAppProcess("workerProcess", want);
```

The `module.json5` configuration:

```json
{
  "app": {
    "extensionAbilities": [{
      "name": "workerProcess",
      "isolationProcess": true
    }]
  }
}
```

> **Note**: in multi-process mode the processes don't share memory, so they must communicate via IPC.

## Application exit — three levels of close interception

This is the **most error-prone** part of the HarmonyOS lifecycle. The system grants different interception rights and time windows at different levels.

### The three levels at a glance

| Level | Name | Trigger | Interception ability | Time limit |
|-------|------|---------|----------------------|------------|
| **Level 1** | Window (WindowStageClose) | The user clicks the window's close button | Full interaction: you can show dialogs, save prompts, and wait for the user | **None** |
| **Level 2** | Ability (AbilityClose) | Closing from the task center / dock thumbnail | A quick save: no UI allowed, only a silent autosave | **Limited** (a system-imposed timeout) |
| **Level 3** | AbilityStage | System shutdown, the dock's right-click menu | **Not yet supported**; automatically degrades to level 2 | Degrades to level 2 |

### Mapping the close method to a level

| Close method | Level triggered | CloseEventRootCause | What you can intercept with |
|--------------|-----------------|---------------------|------------------------------|
| The main window's close button | Level 1 | `WindowStageClose` | Close / Hide / Minimize |
| A subwindow's close button | Level 1 | `WindowStageClose` | Close / Hide |
| The task center / dock thumbnail | Level 2 | `AbilityClose` | Close / Hide / Minimize (must complete quickly) |
| The dock's right-click menu | Level 3 | Degrades to level 2 | The same as level 2 |
| Closing from the system tray | Level 3 | Degrades to level 2 | The same as level 2 |
| System shutdown | Level 3 | Degrades to level 2 | The same as level 2 |
| A force-kill from the task manager | — | — | **Not interceptable** |
| The program calling `close()` internally | — | `InternalClose` | Just accept |

### Handling each root cause differently

In `closeEvent()`, use `QtOhosExtras::getCloseEventRootCause()` to determine where the close came from and act accordingly:

```cpp
void MainWindow::closeEvent(QCloseEvent *event) override {
    auto cause = QtOhosExtras::getCloseEventRootCause(event);

    switch (cause) {
    case QtOhosExtras::CloseEventRootCause::InternalClose:
        // The program called close() itself; just accept
        event->accept();
        break;

    case QtOhosExtras::CloseEventRootCause::WindowStageClose:
        // Level 1: the user clicked the window's close button
        // There's plenty of time, so a save dialog and other interaction is fine
        if (hasUnsavedChanges()) {
            showSaveDialog(event);  // let the user choose
        } else {
            event->accept();
        }
        break;

    case QtOhosExtras::CloseEventRootCause::AbilityClose:
        // Level 2: closed from the task center / dock
        // Time is limited and no UI is allowed — only a quick autosave
        if (hasUnsavedChanges()) {
            autoSave();  // a silent, fast save
        }
        event->accept();
        break;
    }
}
```

> **⚠️ A critical warning**: at level 2 you **must never show UI**. Popping a dialog at that level makes the application hang in the close flow and get force-killed by the system, which is a terrible user experience. Always distinguish the level 1 and level 2 logic.

## Application continuation

One of HarmonyOS's core features: an application's state migrates seamlessly from one device to another (phone → tablet, say).

### The source device: serialize the state

Connect to the `continueRequestReceived` signal and serialize the current application state when the user initiates continuation:

```cpp
auto ability = QOhosAbilityContext::getInstanceForMainWindow(window.windowHandle());

QObject::connect(ability.get(), &QOhosUiAbilityContext::continueRequestReceived,
    [](auto ctx) {
        // Version check: make sure the source and target application versions match
        auto appVersion = QOhosAppContext::instance()->getBundleInfo()->versionCode();

        if (ctx->sourceApplicationVersionCode() == appVersion) {
            // Serialize the application state (the payload must be < 100 KB)
            QByteArray payload = serializeState();
            ctx->setAgreeResponse(payload);

            // Optional: whether to close the source application after the handoff
            ctx->setExitAppOnSourceDeviceAfterMigration(false);
        } else {
            // Version mismatch: refuse the continuation
            ctx->setMismatchResponse();
        }
    });
```

> **The payload limit is < 100 KB.** Large data (files, databases) should be synced to the cloud first, with only a key or reference carried across.

### The target device, cold start

When the application isn't running on the target device, get the continuation data from the launch Want:

```cpp
if (auto launchInfo = QOhosAppContext::getAppLaunchWantInfo()) {
    auto data = QtOhosExtras::tryGetOnContinueData(launchInfo->want());
    if (data) {
        deserializeState(*data);
    }
}
```

### The target device, warm start

When the application is already running in the background on the target device, receive the continuation data through a signal:

```cpp
QObject::connect(ability.get(), &QOhosUiAbilityContext::newWantInfoReceived,
    [](const QSharedPointer<QOhosWantInfo> &info) {
        // Confirm this is a continuation launch
        if (info->launchReason() == QOhosWantInfo::LaunchReason::Continuation) {
            auto data = QtOhosExtras::tryGetOnContinueData(info->want());
            if (data) {
                deserializeState(*data);
            }
        }
    });
```

### The ContinueQuickStart optimization

Appending a `_ContinueQuickStart` suffix to `continueType` in `module.json5` makes the system launch the target application in two phases:

| Phase | LaunchReason | Purpose |
|-------|--------------|---------|
| Phase one | `PrepareContinuation` | Lightweight initialization, showing a loading placeholder UI |
| Phase two | `Continuation` | The full data arrives and you restore the complete state |

```json
{
  "abilities": [{
    "continueType": "video_ContinueQuickStart"
  }]
}
```

> This optimization lets the user see the target application's UI sooner, reducing the perceived handoff time.

## Application sharing

Content sharing between applications through HarmonyOS's **Share Kit**.

### The sender

Create a share record and initiate the share with `shareDataWithShareKit`:

```cpp
#include <QtOhosExtras/qohossharekit.h>

// Create a text content record
auto record = QtOhosExtras::ShareKit::createContentRecord(
    QMimeDatabase().mimeTypeForName("text/plain"),
    "The text content to share");
record->setTitle("The share title");
record->setDescription("The share description");

// Initiate the share (the system share sheet appears)
auto ability = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
ability->shareDataWithShareKit({record}, nullptr);
```

You can share files too:

```cpp
auto fileRecord = QtOhosExtras::ShareKit::createFileRecord(
    QMimeDatabase().mimeTypeForFile("/path/to/image.png"),
    "/path/to/image.png");
```

### The receiver

**Cold start** (launched by tapping in the share sheet):

```cpp
auto launchInfo = QOhosAppContext::getAppLaunchWantInfo();
auto records = QtOhosExtras::ShareKit::tryGetSharedRecordsFromShareKit(
    launchInfo->want());
for (const auto &record : records) {
    processSharedRecord(record);
}
```

**Warm start** (the application is already running in the background):

```cpp
QObject::connect(ability.get(), &QOhosUiAbilityContext::newWantInfoReceived,
    [](const QSharedPointer<QOhosWantInfo> &info) {
        auto records = QtOhosExtras::ShareKit::tryGetSharedRecordsFromShareKit(
            info->want());
        for (const auto &record : records) {
            processSharedRecord(record);
        }
    });
```

> The receiver must likewise declare the share actions and MIME types it can handle in `module.json5`'s `skills`.

## UI-less child processes

Used for background tasks (network sync, data processing, scheduled jobs, and so on) that create no window and save resources. This is HarmonyOS's **native** .so child-process supervision mechanism (the Child Process Manager).

> **The relationship to QProcess**: a headless background task can use either this section's `startNoUiChildProcess` or plain `QProcess` (you can fork/exec a headless binary inside the sandbox); a UI-bearing child process must go through the Ability framework. For the decision tree, see [[qt-harmonyos-api-mapping]] §1.

### Starting a child process

```cpp
// Start a UI-less child process from the main process
QtOhosExtras::QOhosAppContext::startNoUiChildProcess(
    "libBackgroundTask.so",           // the shared library the child loads
    QStringList{"task1", "param1"}    // arguments passed to the child's main()
);
```

### Detecting the mode inside the child process

```cpp
int main(int argc, char *argv[]) {
    if (QtOhosExtras::QOhosAppContext::isNoUiChildMode()) {
        // UI-less mode: don't create a QApplication or any window
        // Just do the background work
        runBackgroundTask(argc, argv);
        return 0;
    }

    // The normal UI mode
    QGuiApplication app(argc, argv);
    MainWindow w;
    w.show();
    return app.exec();
}
```

> **The key point**: in a UI-less child process, **don't create a `QApplication`/`QGuiApplication`** and don't initialize any GUI resources.

### Getting a child process's PID and killing it (an upstream patch is pending)

Today `startNoUiChildProcess` is a `static void` that **returns no PID and offers no way to kill the child**. The reason: the underlying OHOS `childProcessManager.startChildProcess` is an **asynchronous callback**, so the PID is only available inside the AsyncCallback (where it was originally used as a key for the setup-data file IPC and then discarded); and `childProcessManager` **only has start — no stop/abort/kill** (`appManager.killProcessesByBundleName` can only kill an entire app by bundle).

The ZWSOFT request (with an upstream patch pending) adds:
- `Q_SIGNAL noUiChildProcessStarted(int pid, const QString &libraryName, const QStringList &args)` — delivers the PID asynchronously (`Qt::QueuedConnection`, so an event loop must be running; the PID arrives before the setup data)
- `Q_SIGNAL noUiChildProcessStartFailed(const QString &libraryName)` — a launch failure (mutually exclusive with `started`, so the partner never hangs forever)
- `static killNoUiChildProcess(int pid)` — `::kill(pid, SIGKILL)` (native, since OHOS has no stop API)
- `static isNoUiChildProcessRunning(int pid)` — `::kill(pid, 0)` as a liveness probe

> **How feasible is the kill?** Native `::kill(pid,SIGKILL)` is a pattern already proven in this library (`killCurrentProcess`, the `kill(pid,0)` liveness check), but the **SELinux/MAC domain of APP_SPAWN_FORK child processes + AMS registry desync** (SIGKILL bypasses the AbilityManagerService, leaving a stale slot that causes `16000062` next time) is a **device-level open question** that needs on-device verification. The `startNoUiChildProcess` signature is unchanged (backward compatible).

## Passing arguments to main

The `argv` assembly rules on HarmonyOS differ significantly from desktop platforms.

### The argv assembly rules

| Index | Content | Notes |
|-------|---------|-------|
| `argv[0]` | The application library path (`.so`) | **Not** an executable path, but the path of the shared library that was loaded |
| `argv[1...]` | From `appArgs` or the Want parameters | Extracted from the Want per the rules |

### The Want parameter rules

| Parameter | Behavior |
|-----------|----------|
| `want.uri` | Occupies `argv[1]` by default |
| `want.parameters["io.qt.useUriAsArg"]` | Set it to `false` to stop the URI from taking that slot |
| `want.parameters["io.qt.appArgs"]` | A custom argument list that fills `argv[1...]` |

```json
{
  "parameters": {
    "io.qt.useUriAsArg": false,
    "io.qt.appArgs": ["--config", "production", "--verbose"]
  }
}
```

### Passing arguments while debugging with hdc

```bash
# Pass custom arguments
hdc shell aa start -a QAbility -b com.example.myapp \
  --pb io.qt.useUriAsArg false \
  --ps io.qt.appArgsJson '["--config","production","--verbose"]'
```

### The argv assembly priority

```
1. If the Want has io.qt.appArgs → use its values as argv[1...]
2. Else if want.uri exists and useUriAsArg isn't disabled → the uri takes argv[1]
3. Otherwise argv contains only argv[0] (the library path)
```

## Theme management

HarmonyOS supports switching between dark and light modes, and Qt exposes query and listening interfaces through `QOhosAppContext`.

### Querying the current theme

```cpp
auto *ctx = QtOhosExtras::QOhosAppContext::instance();
bool isDark = ctx->darkThemeActive();
```

### Setting the theme-following policy

```cpp
// Follow the system setting (the default)
ctx->setColorThemeMode(
    QtOhosExtras::QOhosAppContext::ColorThemeMode::FollowSystemSetting);

// Force light
ctx->setColorThemeMode(
    QtOhosExtras::QOhosAppContext::ColorThemeMode::LightTheme);

// Force dark
ctx->setColorThemeMode(
    QtOhosExtras::QOhosAppContext::ColorThemeMode::DarkTheme);
```

### Listening for theme changes

```cpp
QObject::connect(ctx, &QtOhosExtras::QOhosAppContext::darkThemeActiveChanged,
    [](bool dark) {
        qDebug() << "Theme changed to:" << (dark ? "Dark" : "Light");
        // Update UI colors, icons, styles, and so on
        updateColorScheme(dark);
    });
```

> **Best practice**: combine this with Qt's QPalette or a QSS stylesheet and switch your color scheme dynamically in the theme-change signal.

## Related documents

- [[qt-harmonyos-overview]] — An overview of Qt on HarmonyOS and its architecture
- [[qt-ohos-extras]] — The QtOhosExtras module API in detail
- [[qt-harmonyos-api]] — API compatibility notes

## References

- [Application Lifecycle on HarmonyOS](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/application_lifecycle_guide)
- [Application Continuation Guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/application_continuation_guild)
- [Application Sharing Guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/application_share_guild)
- [QOhosWant Usage](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_use_QOhosWant)
- [Pass Arguments to main()](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_pass_args_to_main_guide)
- [Color Theme](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/qt_for_harmonyos_color_theme)
- [UI-less Child Process](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_start_uiless_child_process)
