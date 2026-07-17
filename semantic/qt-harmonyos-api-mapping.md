---
id: semantic-qt-harmonyos-api-mapping
type: semantic
domain: tech
tags: [qt, harmonyos, api, mapping, porting, qprocess, window, filesystem, sharing, context-menu, touch]
created: 2026-06-02
updated: 2026-07-06
status: active
audience: public
refs: [semantic-qt-harmonyos-api, semantic-qt-harmonyos-code-patterns, semantic-qt-ohos-extras]
summary: >
  Qt鸿蒙API迁移映射表：13大类Before/After对照——进程管理、应用间通信、
  窗口管理、关闭事件、文件系统、启动参数、拖放、主题外观、时区、线程、
  分享、应用接续、触摸长按上下文菜单。每类含映射表和代码示例。
---

# Qt → HarmonyOS API 迁移映射表

> 本文档汇总 Qt 跨平台应用移植到 OpenHarmony / HarmonyOS 时的 API 映射关系，覆盖 12 个核心领域。每类均提供映射表与 Before/After 代码示例，便于快速检索。

---

## 1. 进程管理 (Process Management)

HarmonyOS 对子进程的创建有严格限制，传统 `QProcess`、`system()`、`exec*()` 均不可用或不被推荐。需根据场景选择 QtOhosExtras 提供的替代接口。

| Other Platform API | HarmonyOS Replacement | Notes |
|---|---|---|
| `QProcess::start(program)` | `QtOhosExtras::QOhosAppContext::startNoUiChildProcess(libName, args)` | 仅用于后台/计算任务，不可启动 GUI 子进程 |
| `QProcess::startDetached(program)` | `QtOhosExtras::startAppProcess(name, want)` | 启动新的应用进程 |
| `QProcess` for GUI child | `QtOhosExtras::startAbility(want)` | 使用 Ability/Want 模型替代 |
| `system()`, `popen()` | Not recommended | 改用 `startNoUiChildProcess` |
| `exec*()` family | Not recommended | 改用 `startNoUiChildProcess` |

### Before

```cpp
QProcess proc;
proc.start("worker", {"--task", "compute"});
proc.waitForFinished();
QString output = proc.readAllStandardOutput();
```

### After

```cpp
#include <QOhosAppContext>

QtOhosExtras::QOhosAppContext::startNoUiChildProcess(
    "libWorker.so",
    QStringList{"--task", "compute"}
);
// 注意：子进程以 .so 库形式加载，而非独立可执行文件
```

---

## 2. 应用间通信 (Inter-Application Communication)

HarmonyOS 不使用 D-Bus 或 `xdg-open`，统一通过 Want 机制实现应用间调用与 URL 打开。

| Other Platform API | HarmonyOS Replacement | Notes |
|---|---|---|
| `QDesktopServices::openUrl(url)` | `startAbility(want)` with `want.uri` | 隐式匹配，系统选择合适应用 |
| `QDesktopServices::openUrl(mailto:)` | `startAbility(want)` with action | 设置 `want.action` 为对应 action |
| `xdg-open` / `ShellExecute` | `startAbility(want)` | 统一使用 Want 模型 |
| D-Bus calls | Not available on OHOS | 使用 Want-based IPC |
| `QProcess` to launch other apps | `startAbility(want)` | 显式或隐式匹配目标 Ability |

### Before

```cpp
QDesktopServices::openUrl(QUrl("https://example.com"));
```

### After

```cpp
#include <QOhosWant>

QOhosWant want;
want.uri    = "https://example.com";
want.action = "ohos.want.action.viewData";
startAbility(want);
```

---

## 3. 窗口管理 (Window Management)

HarmonyOS 对窗口层级、模态、全屏等有较多约束。独立 `QDialog`（无 parent）会被系统视为新主窗口，需显式标记为子窗口。

| Other Platform API | HarmonyOS Behavior / Replacement | Notes |
|---|---|---|
| Independent `QDialog()` | 成为新的主窗口 | 设置 `transientParent` 或使用 `tagWindowOrWidgetAsSubWindowOf()` |
| `Qt::Popup` | 自动回退到子窗口模式 | 通常可用 |
| `setMask()` on main window | Not supported | 改用子窗口或自定义绘制 |
| `showFullScreen()` on 1st window | 启动时不支持 | 在窗口显示后再调用 |
| `showMinimized()` on subwindow | Not supported | 仅主窗口可最小化 |
| `hide()` on main window | 回退为最小化 | 使用 `showMinimized()` 替代 |
| `Qt::WindowStaysOnTopHint` | 仅主窗口，且仅 PC 模式 | 移动端不生效 |
| `Qt::ApplicationModal` | 仅子窗口场景 | 主窗口不支持 |

### Before

```cpp
QDialog *dlg = new QDialog();   // 无 parent
dlg->exec();
```

### After

```cpp
// 方式一：设置 parent
QDialog *dlg = new QDialog(mainWindow);
dlg->exec();

// 方式二：显式标记为子窗口
#include <QOhosFunctions>
QDialog *dlg = new QDialog();
QtOhosExtras::QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(dlg, mainWindow);
dlg->exec();
```

---

## 4. 关闭事件处理 (Close Event Handling)

HarmonyOS 中 `closeEvent()` 不仅由用户点击关闭按钮触发，也可能由系统生命周期管理触发。需要根据 root cause 区分处理。

| Other Platform Behavior | HarmonyOS Behavior | Notes |
|---|---|---|
| `closeEvent()` 即用户主动关闭 | 可能是系统生命周期回调 | 检查 root cause |
| `event->ignore()` 阻止关闭 | Level 1 场景有效 | Level 2（系统强制回收）有时间限制 |

### After

```cpp
void MyWindow::closeEvent(QCloseEvent *event)
{
    auto cause = QtOhosExtras::QOhosFunctions::getCloseEventRootCause(event);

    switch (cause) {
    case QtOhosExtras::WindowStageClose:
        // 用户或系统关闭窗口
        if (hasUnsavedChanges()) {
            event->ignore();   // Level 1 可阻止
            promptSaveDialog();
        }
        break;
    case QtOhosExtras::AbilityClose:
        // Ability 被系统回收，必须尽快保存状态
        saveState();
        break;
    case QtOhosExtras::InternalClose:
        // 应用内部调用 close()
        break;
    }
}
```

---

## 5. 文件系统 (File System)

HarmonyOS 的沙箱机制限制了文件权限修改、符号链接创建以及对系统路径的访问。

| Other Platform API | HarmonyOS Behavior | Notes |
|---|---|---|
| `QFile::setPermissions()` on existing file | No-op（静默失败） | 用 `#ifndef Q_OS_OHOS` 包裹 |
| `QFile::link()` / `symlink()` | 返回 `EACCES` | 使用文件拷贝替代 |
| `QFileInfo::isFile()` on system paths | 返回 `false` | 结合 `exists()` + `isExecutable()` 判断 |
| `QStandardPaths::findExecutable()` | 无法找到系统可执行文件 | 系统二进制不在沙箱可见范围 |
| `QStandardPaths::PublicShareLocation` | 返回空字符串 | 该路径不存在 |
| `dlopen()` from writable paths | 被拒绝（`EINVAL`） | 仅可从应用 lib 目录加载 .so |
| `chmod()`, `fchmod()` | Not supported | 沙箱内文件权限由系统管理 |

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
// OHOS 沙箱自动管理文件权限，setPermissions 为 no-op
```

---

## 6. 启动参数 (Startup Arguments)

HarmonyOS 应用的 `argv` 布局与桌面平台不同：`argv[0]` 指向 .so 库而非可执行文件，业务参数位置不固定。

| Other Platform Behavior | HarmonyOS Behavior | Notes |
|---|---|---|
| `argv[0]` = 可执行文件路径 | `argv[0]` = 库文件路径（`.so`） | 不要用 `argv[0]` 推断应用目录 |
| 业务参数在 `argv[1]` 起 | `want.uri` 可能占据 `argv[1]` | 参数位置不固定 |
| 固定参数位置 | 位置随系统版本变化 | 使用 `QCommandLineParser` 解析 |

### Before

```cpp
int main(int argc, char *argv[])
{
    QCoreApplication app(argc, argv);
    QString taskFile = argv[1];   // 假设第一个参数是任务文件
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
    // 通过 QCommandLineParser 可靠获取参数，不依赖位置
}
```

---

## 7. 拖放 (Drag and Drop)

HarmonyOS 在拖放过程中，`dragEnterEvent` 和 `dragMoveEvent` 阶段仅可获取 MIME 类型列表，完整数据仅在 `dropEvent` 中可用。

| Other Platform Behavior | HarmonyOS Behavior | Notes |
|---|---|---|
| `dragEnterEvent` 中读取 `QMimeData` | 仅 MIME types 可用 | 可根据 MIME type 决定是否接受拖放 |
| `dragMoveEvent` 中读取 `QMimeData` | 仅 MIME types 可用 | 同上 |
| `dropEvent` 中读取 `QMimeData` | 完整数据可用 | 在 drop 阶段读取实际内容 |

### Before

```cpp
void MyWidget::dragEnterEvent(QDragEnterEvent *event)
{
    if (event->mimeData()->hasText()) {          // 读取了数据
        event->acceptProposedAction();
    }
}

void MyWidget::dropEvent(QDropEvent *event)
{
    QString text = event->mimeData()->text();    // 读取数据
    processText(text);
}
```

### After

```cpp
void MyWidget::dragEnterEvent(QDragEnterEvent *event)
{
    // 仅检查 MIME type，不读取实际数据
    if (event->mimeData()->formats().contains("text/plain")) {
        event->acceptProposedAction();
    }
}

void MyWidget::dropEvent(QDropEvent *event)
{
    // 完整数据在 drop 阶段才可用
    QString text = event->mimeData()->text();
    processText(text);
}
```

---

## 8. 主题/外观 (Theme/Appearance)

HarmonyOS 的暗色模式需通过 QtOhosExtras 接口启用跟随系统设置，且系统不内置等宽字体。

| Other Platform Behavior | HarmonyOS Replacement | Notes |
|---|---|---|
| Platform-native dark mode | `QOhosAppContext::setColorThemeMode(FollowSystemSetting)` | 通过 QtOhosExtras 设置 |
| `QPalette` customization | 仍然有效 | 需监听 `darkThemeActiveChanged` 信号动态切换 |
| System monospace font | Not available | 使用 `addApplicationFont()` 内置字体 |

### Before

```cpp
// 桌面平台自动跟随系统暗色模式
QApplication app(argc, argv);
```

### After

```cpp
#include <QtOhosExtras/QOhosAppContext>

QApplication app(argc, argv);

// 启用跟随系统暗色/亮色模式
auto *ctx = QtOhosExtras::QOhosAppContext::instance();
ctx->setColorThemeMode(
    QtOhosExtras::QOhosAppContext::ColorThemeMode::FollowSystemSetting
);

// 监听主题变化，更新自定义 palette
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

## 9. 时区 (Timezone)

HarmonyOS 不包含 tzdata 数据库，`QTimeZone` 需使用 ICU 后端。

| Other Platform Behavior | HarmonyOS Replacement | Notes |
|---|---|---|
| `QTimeZone` with tz backend | 无 tzdata | 使用 ICU backend |

### Before

```cpp
QTimeZone tz("Asia/Shanghai");
QDateTime dt = QDateTime::currentDateTime().toTimeZone(tz);
```

### After

```cpp
// 确保 Qt 编译时启用了 ICU 后端
// QTimeZone API 不变，但底层依赖 ICU 而非 tzdata
QTimeZone tz("Asia/Shanghai");   // 正常工作，前提是 ICU 可用
QDateTime dt = QDateTime::currentDateTime().toTimeZone(tz);
```

> **注意**：构建 Qt for OHOS 时需确认 ICU 库已链接，否则 `QTimeZone` 可能返回无效时区。

---

## 10. 线程 (Threading)

HarmonyOS 定义了 `PTHREAD_CANCEL_DISABLE` 等宏，但相关函数（如 `pthread_cancel`）不可用。

| Other Platform Behavior | HarmonyOS Behavior | Notes |
|---|---|---|
| `PTHREAD_CANCEL_DISABLE` 等宏 | 已定义但函数不可用 | 用 `#ifdef` 守卫或 `#undef` |

### Before

```cpp
#include <pthread.h>

// 禁用线程取消
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
// OHOS 不支持 pthread_cancel 系列函数，改用协作式终止（如 QThread::quit + wait）
```

---

## 11. 分享 (Sharing)

HarmonyOS 提供 ShareKit 框架实现系统级分享，通过 `QOhosAbilityContext` 调用。

| Other Platform Behavior | HarmonyOS Replacement | Notes |
|---|---|---|
| Platform share sheet (iOS/Android) | `ShareKit::shareDataWithShareKit()` | 通过 `QOhosAbilityContext` 获取上下文 |

### Before

```cpp
// iOS: UIActivityViewController
// Android: Intent.ACTION_SEND
// 桌面: 无统一分享机制
```

### After

```cpp
#include <QOhosAbilityContext>
#include <ShareKit>

auto context = QtOhosExtras::QOhosAbilityContext::currentContext();
ShareKit::SharedData data;
data.text = "Check out this app!";
data.uri  = "https://example.com";

ShareKit::shareDataWithShareKit(context, data);
// 系统弹出分享面板，用户选择目标应用
```

---

## 12. 应用接续 (Application Continuation)

HarmonyOS 支持跨设备应用接续（类似 Apple Handoff），通过 `continueRequestReceived` 信号接收接续请求，状态序列化限制在 100KB 以内。

| Other Platform Behavior | HarmonyOS Replacement | Notes |
|---|---|---|
| Handoff / Continuity (Apple) | `continueRequestReceived` signal | 序列化状态 < 100KB |

### Before

```cpp
// Apple: NSUserActivity
// 桌面: 无对应机制
```

### After

```cpp
#include <QOhosAbilityContext>

// 发送端：序列化当前状态
auto context = QtOhosExtras::QOhosAbilityContext::currentContext();
QJsonObject state;
state["document"] = currentDocumentPath;
state["cursor"]   = cursorPosition;

// 状态必须 < 100KB
QByteArray serialized = QJsonDocument(state).toJson(QJsonDocument::Compact);
Q_ASSERT(serialized.size() < 100 * 1024);

context->updateContinuationState(serialized);

// 接收端：处理接续请求
QObject::connect(context, &QOhosAbilityContext::continueRequestReceived,
    [](const QByteArray &stateData) {
        QJsonObject state = QJsonDocument::fromJson(stateData).object();
        openDocument(state["document"].toString());
        setCursorPosition(state["cursor"].toInt());
    }
);
```

---

## 13. 触摸长按上下文菜单 (Touch Long-Press Context Menu)

HarmonyOS 触摸屏默认**不**为长按生成 `QContextMenuEvent`（桌面平台鼠标右键自动触发）。需通过 QtOhosExtras 显式启用。

| Other Platform Behavior | HarmonyOS Replacement | Notes |
|---|---|---|
| 右键自动产生 `QContextMenuEvent` | `QOhosAppContext::enableContextMenuEventOnLongPress()` | 启用后长按触发，reason 为 `Other` |

### Before

```cpp
// 桌面：右键即收到 contextMenuEvent，无需额外设置
QApplication app(argc, argv);
// QWidget::contextMenuEvent() 自动被右键触发
```

### After

```cpp
#include <QtOhosExtras>

QApplication app(argc, argv);
// 必须在 exec() 前调用一次，全局生效
QtOhosExtras::QOhosAppContext::instance()->enableContextMenuEventOnLongPress();
// 此后触摸长按会以 QContextMenuEvent::Other 触发 contextMenuEvent()
```

> **注意**：长按产生的 `QContextMenuEvent::reason()` 为 `QContextMenuEvent::Other`（非 `Mouse`）。若处理函数按 reason 过滤，需同时接受 `Other`。详见 [[qt-ohos-extras]] §触摸长按。

---

## 快速参考：条件编译宏

```cpp
#ifdef Q_OS_OHOS
    // HarmonyOS / OpenHarmony 专用代码路径
#else
    // 桌面/其他平台代码路径
#endif
```

## 迁移检查清单

1. **进程管理** — 替换所有 `QProcess` 调用为 QtOhosExtras 接口
2. **应用间通信** — 替换 `QDesktopServices::openUrl` 为 Want 机制
3. **窗口管理** — 为所有独立 `QDialog` 设置 parent 或标记为子窗口
4. **关闭事件** — 在 `closeEvent` 中检查 root cause，区分用户操作与系统回收
5. **文件系统** — 移除 `setPermissions`、`symlink` 调用，用条件编译守卫
6. **启动参数** — 改用 `QCommandLineParser`，不依赖 `argv` 位置
7. **拖放** — `dragEnter`/`dragMove` 中仅检查 MIME type
8. **主题** — 调用 `setColorThemeMode`，内置等宽字体
9. **时区** — 确认 ICU 后端已链接
10. **线程** — 守卫 `pthread_cancel` 相关调用
11. **分享** — 集成 ShareKit
12. **接续** — 实现 `continueRequestReceived`，控制状态大小
13. **触摸长按** — 调用 `enableContextMenuEventOnLongPress()` 启用长按触发右键菜单（exec 前调用一次）

## 参考来源

| 来源类型 | 说明 |
|----------|------|
| 🛠️ 工作经验 | 日常 Qt 鸿蒙化开发实践积累 |
