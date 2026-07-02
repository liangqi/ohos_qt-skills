---
id: semantic-qt-harmonyos-code-patterns
type: semantic
domain: tech
tags: [qt, harmonyos, code-patterns, porting, before-after, examples]
created: 2026-06-02
updated: 2026-06-02
status: active
audience: public
refs: [semantic-qt-harmonyos-api-mapping, semantic-qt-harmonyos-porting-workflow, semantic-qt-ohos-extras]
summary: >
  Qt鸿蒙移植12组Before/After代码模式速查：子进程→NoUi、启动外部应用→StartAbility、
  独立对话框→tagged子窗口、关闭事件处理、文件权限守卫、参数解析、
  平台构建配置、深色模式、拖放、等宽字体、浮窗、分享数据。
---

# Qt 鸿蒙移植 12 组 Before/After 代码模式

> 来源：[Code Patterns: Before/After Porting Examples](https://wiki.qt.io/Qt_for_HarmonyOS/code_patterns)
> 关联：[[qt-harmonyos-api-mapping]]、[[qt-harmonyos-porting-workflow]]、[[qt-ohos-extras]]

## 模式一览

| # | 场景 | 核心变化 |
|---|------|----------|
| 1 | 子进程 | QProcess → startNoUiChildProcess() |
| 2 | 启动外部应用 | QDesktopServices / JNI → startAbility() |
| 3 | 独立对话框 | 直接 show() → tagAsSubWindowOf() |
| 4 | 关闭事件处理 | 统一 closeEvent → 区分 WindowStage/Ability/Internal |
| 5 | 文件权限守卫 | setPermissions → 条件编译跳过 |
| 6 | 参数解析 | argv 直取 → QCommandLineParser |
| 7 | 平台构建配置 | qmake 缺 ohos 分支 → 补充 ohos {} |
| 8 | 深色模式 | 手动 palette → ColorThemeMode 跟随系统 |
| 9 | 拖放 | dragEnter 读数据 → 仅检查 MIME，drop 再读 |
| 10 | 等宽字体 | systemFont → 自带 .ttf 注册 |
| 11 | 浮窗 | 无 → setShowWindowAsFloatWindowHint() |
| 12 | 分享数据 | 无 → ShareKit 集成 |

---

## 模式 1：子进程 → NoUi Child Process

桌面/Android 用 `QProcess` 启动子进程。鸿蒙不支持传统 fork/exec，改用 QtOhosExtras 的 `startNoUiChildProcess()`。

**Before (Desktop/Android)**
```cpp
#include <QProcess>

void MainWindow::runWorker() {
    QProcess proc;
    proc.start("worker", {"--input", inputFile});
    proc.waitForFinished();
}
```

**After (HarmonyOS)**
```cpp
#include <QtOhosExtras/QtOhosExtras>

void MainWindow::runWorker() {
    QtOhosExtras::QOhosAppContext::startNoUiChildProcess(
        "libWorker.so",
        QStringList{"--input", inputFile}
    );
}
```

> **关键约束**：子进程必须编译为 `.so` 共享库，部署到 `entry/libs/<arch>/`。
> 详见 [[qt-ohos-extras]] 中 startNoUiChildProcess 的说明。

---

## 模式 2：启动外部应用 → Start Ability

桌面用 `QDesktopServices::openUrl()`，Android 用 JNI 构造 Intent。鸿蒙统一用 `QOhosWant` + `startAbility()`。

**Before (Desktop)**
```cpp
QDesktopServices::openUrl(QUrl("https://example.com"));
```

**Before (Android)**
```cpp
QAndroidJniObject intent("android/content/Intent");
// ... 复杂的 JNI 构造
```

**After (HarmonyOS)**
```cpp
QtOhosExtras::QOhosWant want;
want.uri = "https://example.com";
want.action = "ohos.want.action.viewData";
QtOhosExtras::startAbility(want);
```

> 参考 [[qt-ohos-extras]] 中 QOhosWant 和 startAbility() 的完整参数说明。

---

## 模式 3：独立对话框 → Tagged Subwindow

鸿蒙窗口模型不支持独立的顶级窗口弹出。所有 QDialog / Popup 必须标记为子窗口，参见 [[qt-harmonyos-api-mapping]] 窗口模型差异。

**Before (Desktop)**
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
    // 关键：标记为当前主窗口的子窗口
    QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(dlg, this->windowHandle());
    dlg->setAttribute(Qt::WA_DeleteOnClose);
    dlg->show();
}
```

> **注意**：不调用 `tagWindowOrWidgetAsSubWindowOf()` 的独立对话框在鸿蒙上将无法正常显示或导致崩溃。

---

## 模式 4：关闭事件处理 — 区分关闭原因

鸿蒙的 `closeEvent` 可能来自三种根源：窗口关闭（WindowStageClose）、Ability 生命周期销毁（AbilityClose）、内部关闭（InternalClose），需分别处理。

**Before (Desktop)**
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
        // 用户关窗口 → 正常询问保存（完整交互）
        if (unsavedChanges()) {
            int ret = QMessageBox::question(this, "Save?",
                "Unsaved changes. Save before closing?",
                QMessageBox::Save | QMessageBox::Discard | QMessageBox::Cancel);
            if (ret == QMessageBox::Save) { save(); event->accept(); }
            else if (ret == QMessageBox::Discard) { event->accept(); }
            else { event->ignore(); }
        }
    } else if (cause == QtOhosExtras::CloseEventRootCause::AbilityClose) {
        // 系统回收 Ability → 静默自动保存，不要弹窗
        if (unsavedChanges()) autoSave();
        event->accept();
    } else {
        // InternalClose → 直接接受
        event->accept();
    }
}
```

> **核心原则**：
> - `WindowStageClose` — 用户主动关窗口，可以弹 QMessageBox 完整交互
> - `AbilityClose` — 系统回收 Ability，用户已不在前台，必须快速 autoSave，禁止弹窗
> - `InternalClose` — 程序内部触发，直接 accept

---

## 模式 5：文件权限守卫

鸿蒙不支持 `chmod()` / `setPermissions()`，详见 [[qt-harmonyos-api-mapping]] 中 chmod 限制。

**Before (Cross-platform)**
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

> 在鸿蒙上调用 `setPermissions()` 会失败或产生未定义行为。用 `#ifndef Q_OS_OHOS` 条件编译守卫。

---

## 模式 6：参数解析 → QCommandLineParser

鸿蒙的 `argv[0]` 是应用库路径而非可执行文件路径，Want 参数可能占用 `argv[1]`。不要假设业务参数位置，改用 `QCommandLineParser`。参见 [[qt-harmonyos-api-mapping]] 参数传递章节。

**Before (Desktop)**
```cpp
int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    QString configFile = argv[1]; // 假设 argv[1] 是配置文件
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

> **关键约束**：永远不要直接索引 `argv[N]` 取业务参数。使用 `QCommandLineParser` 是跨平台安全做法。

---

## 模式 7：平台构建配置 → 补充 ohos 分支

qmake 项目文件中 Linux 条件 `unix:!android:!macx` 会错误匹配 ohos，需显式排除并添加 ohos 分支。构建详情见 [[qt-harmonyos-porting-workflow]]。

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

**After (Add OHOS)**
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

> **注意**：
> - `unix` 分支必须追加 `:!ohos` 排除鸿蒙，否则 ohos 会同时命中 unix 分支
> - `ohos` 分支必须加 `QT += ohosextras` 才能使用 QtOhosExtras API

---

## 模式 8：深色模式支持 → 跟随系统

桌面通过手动设置 QPalette 实现暗色主题。鸿蒙通过 `QOhosAppContext` 跟随系统暗色设置，并响应动态变化信号。

**Before (Desktop)**
```cpp
QApplication::setStyle("fusion");
QPalette darkPalette;
darkPalette.setColor(QPalette::Window, QColor(53, 53, 53));
darkPalette.setColor(QPalette::WindowText, Qt::white);
// ... 手动设置各颜色角色
qApp->setPalette(darkPalette);
```

**After (HarmonyOS)**
```cpp
#include <QtOhosExtras/QtOhosExtras>

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

> `FollowSystemSetting` 自动跟随系统深浅色切换；`darkThemeActiveChanged(bool)` 信号在切换时触发，可在槽函数中更新自定义样式。

---

## 模式 9：拖放 → 延迟读取数据

鸿蒙拖放的 MIME 数据在 `dragEnterEvent` 时可能不可用，只能在 `dropEvent` 中读取实际内容。

**Before (Desktop)**
```cpp
void Widget::dragEnterEvent(QDragEnterEvent *event) {
    if (event->mimeData()->hasText()) {
        QString text = event->mimeData()->text(); // 直接读取数据
        if (isValidData(text))
            event->acceptProposedAction();
    }
}
```

**After (HarmonyOS)**
```cpp
void Widget::dragEnterEvent(QDragEnterEvent *event) {
    if (event->mimeData()->hasText()) {  // 仅检查 MIME 类型
        event->acceptProposedAction();
        // 不要在 OHOS 上此处读取 text() 实际数据
    }
}

void Widget::dropEvent(QDropEvent *event) {
    QString text = event->mimeData()->text(); // 在 drop 时读取实际数据
    processData(text);
}
```

> **核心原则**：`dragEnterEvent` 只做 `hasText()` / `hasUrls()` 等类型检查，`dropEvent` 才读取实际内容。这是因为鸿蒙拖放协议的数据传输是异步的。

---

## 模式 10：等宽字体 → 自带 TTF

鸿蒙系统不提供等宽字体，`QFontDatabase::systemFont(QFontDatabase::FixedFont)` 返回普通字体。需自带 `.ttf` 并通过 `addApplicationFont()` 注册。

**Before (Desktop)**
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

> **部署步骤**：
> 1. 将 `NotoSansMono-Regular.ttf` 放入项目资源文件（`.qrc`）
> 2. 通过 `:/fonts/` 前缀引用
> 3. `addApplicationFont()` 返回 fontId，用 `applicationFontFamilies()` 获取实际字体族名

---

## 模式 11：浮窗（鸿蒙独有能力）

鸿蒙支持 Floating Window，桌面端无此概念。通过 `setShowWindowAsFloatWindowHint()` 启用悬浮窗显示。

**New (HarmonyOS only)**
```cpp
#include <QtOhosExtras/QtOhosExtras>

void MainWindow::openFloatingNote() {
    NoteWidget *note = new NoteWidget();
    QtOhosExtras::setShowWindowAsFloatWindowHint(note, true);
    note->setAttribute(Qt::WA_DeleteOnClose);
    note->resize(300, 400);
    note->show();
}
```

> **注意**：悬浮窗需要 `ohos.permission.SYSTEM_FLOAT_WINDOW` 权限，第三方应用通常不可用。桌面端此函数无效果。

---

## 模式 12：分享数据（鸿蒙独有能力）

通过 ShareKit 将文件分享到系统其他应用。桌面端无对等能力。

**New (HarmonyOS only)**
```cpp
#include <QtOhosExtras/QtOhosExtras>

void MainWindow::shareFile(const QString &filePath) {
    auto record = QtOhosExtras::ShareKit::createFileRecord(QFileInfo(filePath));
    record->setTitle(QFileInfo(filePath).fileName());

    auto ability = QtOhosExtras::QOhosAbilityContext::getDefaultInstance();
    ability->shareDataWithShareKit({record}, nullptr);
}
```

> `createFileRecord()` 从 `QFileInfo` 构造分享记录，`shareDataWithShareKit()` 调起系统分享面板。第二个参数为回调，传 `nullptr` 表示不关心结果。

---

## 移植检查清单

在实际移植中，按以下顺序逐项排查：

1. **构建系统** — qmake/CMake 是否补充了 `ohos` 分支和 `QT += ohosextras`？（模式 7）
2. **进程模型** — 是否用 QProcess？→ 改为 startNoUiChildProcess（模式 1）
3. **外部调用** — 是否用 QDesktopServices / JNI？→ 改为 startAbility（模式 2）
4. **窗口/对话框** — 所有独立顶级窗口是否 tag 为子窗口？（模式 3）
5. **生命周期** — closeEvent 是否区分 WindowStage / Ability / Internal？（模式 4）
6. **文件系统** — setPermissions 调用是否已条件编译守卫？（模式 5）
7. **参数传递** — 是否依赖 argv 位置？→ 改用 QCommandLineParser（模式 6）
8. **UI 适配** — 深色模式（模式 8）、拖放（模式 9）、等宽字体（模式 10）
9. **鸿蒙增强** — 是否需要浮窗（模式 11）或系统分享（模式 12）？

---

## 参考来源

- [Qt for HarmonyOS Code Patterns (Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS/code_patterns) — 原始 Before/After 示例
- [[qt-harmonyos-api-mapping]] — API 兼容性映射（argv、QProcess、窗口模型）
- [[qt-harmonyos-porting-workflow]] — 移植工作流与检查清单
- [[qt-ohos-extras]] — QtOhosExtras 模块 API 参考
