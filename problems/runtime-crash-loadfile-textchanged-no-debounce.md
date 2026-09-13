---
id: problem-runtime-crash-loadfile-textchanged-no-debounce
type: problem
domain: runtime
tags: [runtime, crash, textChanged, debounce, getFileTimeRange, loadfile, SIGSEGV]
created: 2026-08-10
updated: 2026-08-10
status: solved
severity: high
audience: public
refs: []
summary: >
  In QtSerialMonitor, every character typed into the Load File path field triggers getFileTimeRange (a heavy open+readAll+split),
  causing a SIGSEGV crash. Fix: a 500 ms QTimer debounce + an empty-list check.
leader_summary: >
  Captured the debounce pattern for QLineEdit textChanged signals that trigger heavy work, preventing crashes from per-keystroke file parsing at the application layer.
impact: [Migration efficiency, Application polish]
deliverables: [problem record, patch]
evidence: [QtSerialMonitor on-device test TC-08, fix in src/mainwindow.cpp]

# ====== Search keywords (for fast agent matching) ======
error_message: >
  SIGSEGV crash when typing in Load File path input field; on_lineEditLoadFilePath_textChanged triggers getFileTimeRange on every keystroke
error_code: ""
keywords: [textChanged, debounce, getFileTimeRange, loadfile, crash, SIGSEGV, QLineEdit]
symptoms: "The application crashes while the user is typing a path into the Load File field (before clicking the Load button)"

# ====== Problem details ======
environment: "Qt 5.15.16 OHOS (Qt5.15.16-arm64-v8a-full SDK), HUAWEI MateBook Pro (2-in-1), API 24"
---

# SIGSEGV crash while typing a Load File path (textChanged with no debounce)

## Error message

The application crashes with no clear error log (the SIGSEGV happens inside getFileTimeRange).

## Scenario

QtSerialMonitor on-device test TC-08: while the user types a file path into the "Load File" path field at the bottom of the window (`lineEditLoadFilePath`) — **before clicking the Load button** — the application crashes.

## Cause

`MainWindow::on_lineEditLoadFilePath_textChanged(const QString &arg1)` fires on **every character typed** and calls `fileReader.getFileTimeRange(&file)`. That function performs:
1. `file.open(QIODevice::ReadOnly)` — opens the file
2. `file.readAll()` — reads the entire contents into memory
3. `allData.split(QRegExp("[\\n+\\r+]"), Qt::SplitBehaviorFlags::SkipEmptyParts)` — a regex split

Triggering this heavy work (open+readAll+split) on every character leads to:
- Resource contention (repeatedly opening/closing the same file)
- Possible crashes from Qt's internal signal/slot reentrancy
- `Qt::SplitBehaviorFlags::SkipEmptyParts` may resolve unreliably at runtime on Qt 5.15 OHOS

## Solution

Add a QTimer debounce (fire after 500 ms) in `on_lineEditLoadFilePath_textChanged`, plus an empty-list check:

```cpp
void MainWindow::on_lineEditLoadFilePath_textChanged(const QString &arg1)
{
    // Debounce: fire after 500 ms so getFileTimeRange (a heavy open+readAll+split) isn't triggered per character
    QTimer::singleShot(500, this, [this, arg1]() {
        if (ui->lineEditLoadFilePath->text() != arg1)
            return; // the path changed; ignore the stale trigger
        
        QFile file(arg1);
        if (!file.exists())
        {
            ui->lineEditFileInfo->setText("File doesnt exist !");
            return;
        }
        
        QList<QTime> timeRange = fileReader.getFileTimeRange(&file);
        if (timeRange.count() >= 2)
        {
            ui->timeEditMinParsingTime->setTime(timeRange.first());
            ui->timeEditMaxParsingTime->setTime(timeRange.last());
        }
        
        QString info = "Size: " + QString::number(file.size());
        ui->lineEditFileInfo->setText(info);
    });
}
```

**Key changes**:
1. `QTimer::singleShot(500, ...)` — a 500 ms debounce
2. `if (ui->lineEditLoadFilePath->text() != arg1) return;` — ignore stale triggers when the path has changed
3. `if (timeRange.count() >= 2)` — guard against an empty list

## Notes

- The 500 ms debounce is an empirical value; adjust it based on how long file parsing takes
- `getFileTimeRange` itself could also be optimized (reading just the first and last few lines instead of readAll)
- This pattern applies to any case where a QLineEdit textChanged signal triggers heavy work

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Captured the QLineEdit textChanged debounce pattern, preventing crashes from per-keystroke file parsing at the application layer |
| Scope of impact | QtSerialMonitor on-device test TC-08; other Qt OHOS applications where textChanged triggers heavy work |
| Deliverables | problem record + a patch to src/mainwindow.cpp |
| Evidence | QtSerialMonitor on-device test TC-08 fix verified |
| How to reuse | Reuse the debounce pattern whenever "QLineEdit textChanged triggering heavy work causes a crash" |

## Related

- [[qt-app-harmonyos-completion]] — The application-polish workflow for HarmonyOS porting (TC-08 belongs to this workflow)
- [[qt-harmonyos-golden-rules]] — Quick reference to the iron rules

---

> **Template note**: this template is for recording errors encountered during real execution.
> Known Qt platform limitations (such as chmod being unsupported) belong in `semantic/qt-harmonyos-platform-limits.md` and should not use this template.
