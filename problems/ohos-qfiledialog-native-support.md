---
id: problem-ohos-qfiledialog-native-support
type: problem
domain: caveat
tags: [qfiledialog, file-dialog, save, load, download, qohosplatformplugin, native-support, qt515, frequest]
created: 2026-07-29
updated: 2026-08-03
status: solved
severity: low
audience: public
refs: [semantic-qt-harmonyos-api-mapping]
summary: "Anti-pattern: QFileDialog works natively on OHOS; wrapping it in #ifdef is a common anti-pattern"
error_message: >
  Developers mistakenly assume QFileDialog needs a \#ifdef Q_OS_OHOS workaround on OHOS (QInputDialog/hard-coded paths)
  and add unnecessary guard code, creating maintenance burden and conflicting with the native support. In reality,
  QOhosPlatformIntegrationPlugin already provides native support, so the standard QFileDialog API can be used directly.
---

# QFileDialog works natively on OHOS

## Problem description

When migrating a Qt application to OHOS, developers often **mistakenly assume** that OHOS doesn't support `QFileDialog`, and add `#ifdef Q_OS_OHOS` workarounds (such as `QInputDialog` or hard-coded paths) for Save/Load/Download features.

In fact, Qt for OHOS's platform plugin `QOhosPlatformIntegrationPlugin` (`libqohos.so`) already has built-in file dialog support.

## How to verify

See the ModbusDebuger verification project, whose Save feature uses the standard API directly:

```cpp
void MainWindow::on_pushButton_save_clicked()
{
    QString filePath = QFileDialog::getSaveFileName(this, tr("Save Data"), "",
                                                    tr("Data Files (*.txt)"));
    if (filePath.isNull()) return;
    QFile file(filePath);
    if (!file.open(QIODevice::WriteOnly|QIODevice::Text)) { ... }
    file.write(data.toLatin1());
}
```

- No `#ifdef Q_OS_OHOS` branch
- No ArkTS bridge
- No NAPI layer
- The `FILE_ACCESS_PERSIST` permission in module.json5 is preconfigured by the Qt template

## Root cause

Internally, `QOhosPlatformIntegrationPlugin` calls the native OHOS file manager API through `@kit.FileManagerServiceKit.fileManagerService`, registered in `OhosExportModules.ts`. This is completely transparent to the Qt Widgets code above it.

## Solution

**No special handling is needed.** Just use the standard Qt API:

```cpp
// Save
QString filePath = QFileDialog::getSaveFileName(this, tr("Save File"),
                                                 defaultPath,
                                                 tr("Project files (*.frp)"));

// Load
QString filePath = QFileDialog::getOpenFileName(this, tr("Load File"),
                                                 defaultPath,
                                                 tr("Project files (*.frp)"));
```

## Common wrong turns

| Wrong approach | Correct approach |
|----------------|------------------|
| `#ifdef Q_OS_OHOS` + QInputDialog to type a filename | Just use QFileDialog |
| `#ifdef Q_OS_OHOS` + hard-coding to getAppPath() | Just use QFileDialog |
| `#ifdef Q_OS_OHOS` + QStandardPaths::DocumentsLocation | Just use QFileDialog (DocumentsLocation doesn't exist on OHOS) |

## Notes

- The save path is decided by the Qt platform plugin and normally points at the application sandbox's `files` directory
- Saved files are **not visible** in the system file manager (a sandbox limitation); making them visible requires bridging the filePicker API via ArkTS + NAPI
- The `file://` URL scheme isn't supported by `QDesktopServices::openUrl()`, but QFileDialog itself works fine

## Affected projects

- FRequest (`com.ohosqt.FRequest`) — fixed; all unnecessary OHOS guards around QFileDialog were removed
