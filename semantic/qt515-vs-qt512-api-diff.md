---
id: semantic-qt515-vs-qt512-api-diff
type: semantic
domain: tech
tags: [qt, qt5, qt515, qt512, api-diff, ohos, harmonyos, migration, deprecated, widgets, breaking-change, porting]
created: 2026-06-13
updated: 2026-06-13
status: active
audience: public
refs: [semantic-qt-harmonyos-api,semantic-qt-harmonyos-build,semantic-qt-harmonyos-modules,semantic-qt-harmonyos-overview,semantic-qt-harmonyos-qt6-status]
summary: >
  A complete public API diff report for the QtWidgets module between Qt 5.15.16 and 5.12.12 (the OHOS SDK):
  1 new header, 67 headers with differences, ~50 new APIs (QStyleOptionTabV4/QCalendar/Markdown/ExclusionPolicy/
  the OHOS-specific QSystemTrayIcon/QFileDialog), 50+ deprecated APIs, Qt6-preparatory dual signatures, and a migration risk assessment.
---

# QtWidgets: the public API diff between the Qt 5.15.16 and 5.12.12 OHOS SDKs

> **Purpose**: when migrating between the two OHOS Qt SDK versions, quickly look up which APIs were added/deprecated/changed.
> **Validation baseline**: Qt 5.15.16 (commit 962aa625, 2026-04-19) vs. Qt 5.12.12 (commit 613336de, 2026-05-25)

## Overview

| Metric | Value |
|--------|:-----:|
| Total headers in 5.15 | 355 |
| Total headers in 5.12 | 354 |
| Only in 5.15 (added) | 2 (1 real + 1 version marker) |
| Only in 5.12 (removed) | 1 (a version marker) |
| Headers in common | 353 |
| Common headers with differences | 67 |
| Headers with substantive API impact | ~50 |

---

## §1 New headers (5.15 only; downgrading breaks)

| Header | Description | Downgrade risk |
|--------|-------------|:--------------:|
| `QStyleOptionTabV4` | A forwarding header → `#include "qstyleoption.h"`. The class is defined in `qstyleoption.h` | Low |
| `5.15.16` | A version marker file (not an API) | — |

**Conclusion**: no real API header was removed.

---

## §2 New classes

### QStyleOptionTabV4 (qstyleoption.h)

```cpp
class Q_WIDGETS_EXPORT QStyleOptionTabV4 : public QStyleOptionTab
{
public:
    enum StyleOptionVersion { Version = 4 };
    QStyleOptionTabV4();
    int tabIndex = -1;
};
```

- **Purpose**: extends the tab style option with a `tabIndex` field so custom styles can get the index of the tab being painted
- **Downgrade risk**: low — existing `QStyleOptionTab` code is unaffected

---

## §3 OHOS-specific new APIs (5.15 only)

These are OHOS platform patches and don't exist in 5.12's public headers.

### 3.1 QFileDialog (`Q_OS_OPENHARMONY`)

```cpp
QList<QUrl> selectedUris() const;                         // OHOS-only
static QUrl getOpenFileUri(QWidget *parent, ...);         // OHOS-only
```

**Downgrade risk**: 🔴 high — code depending on these won't compile on 5.12.

### 3.2 QSystemTrayIcon (`Q_OS_OPENHARMONY`)

```cpp
// A new constructor supporting separate light/dark icons
QSystemTrayIcon(const QIcon &iconLight, const QIcon &iconDark, QObject *parent);

// A new enum
enum IconTheme { Dark, Light };

// The icon interface signatures changed (OHOS-specific)
QIcon icon(IconTheme theme = Light) const;
void setIcon(const QIcon &icon, IconTheme theme = Light);
```

**Downgrade risk**: 🔴 high — the `icon()`/`setIcon()` signatures differ on OHOS, so downgrading breaks the build.

### 3.3 QWidget (`Q_OS_OPENHARMONY`)

```cpp
#ifdef Q_OS_OPENHARMONY
#define platformUpdate() update()
#else
#define platformUpdate() repaint()
#endif
```

**Downgrade risk**: low — an internal macro that application code generally doesn't use directly.

---

## §4 New public APIs (present in 5.15, absent in 5.12)

### 4.1 New methods

| Class | New method | Version | Downgrade risk |
|-------|------------|:-------:|:--------------:|
| `QActionGroup` | `ExclusionPolicy exclusionPolicy() const` | 5.14 | Low |
| `QActionGroup` | `void setExclusionPolicy(ExclusionPolicy)` | 5.14 | Low |
| `QCalendarWidget` | `QCalendar calendar() const` | 5.14 | 🟠 Medium |
| `QCalendarWidget` | `void setCalendar(QCalendar)` | 5.14 | 🟠 Medium |
| `QComboBox` | `void setPlaceholderText(const QString &)` | 5.14 | Low |
| `QComboBox` | `QString placeholderText() const` | 5.14 | Low |
| `QDateTimeEdit` | `QCalendar calendar() const` | 5.14 | 🟠 Medium |
| `QDateTimeEdit` | `void setCalendar(QCalendar)` | 5.14 | 🟠 Medium |
| `QDateTimeEdit` | The constructor `(QVariant, QMetaType::Type, ...)` | 5.15 | Low |
| `QFileDialog` | `static void getOpenFileContent(...)` | 5.14 | 🟠 Medium |
| `QFileDialog` | `static void saveFileContent(...)` | 5.14 | 🟠 Medium |
| `QFileSystemModel` | `void setOption(Option, bool)` | 5.14 | Low |
| `QFileSystemModel` | `bool testOption(Option) const` | 5.14 | Low |
| `QFileSystemModel` | `void setOptions(Options)` / `Options options()` | 5.14 | Low |
| `QGraphicsItemAnimation` | `QTransform transformAt(qreal) const` | 5.14 | Low |
| `QGraphicsWidget` | `void setContentsMargins(QMarginsF)` | 5.15 | Low |
| `QGraphicsWidget` | `void setWindowFrameMargins(QMarginsF)` | 5.15 | Low |
| `QItemDelegate` | `static QPixmap selectedPixmap(...)` | 5.13 | Low |
| `QPlainTextEdit` | `bool find(const QRegularExpression &, ...)` | 5.13 | Low |
| `QPushButton` | `bool hitButton(const QPoint &) const override` | 5.15 | Low |
| `QShortcut` | 4 template constructors (functor support) | 5.14 | 🟠 Medium |
| `QSplashScreen` | `QSplashScreen(QScreen *, ...)` | 5.15 | Low |
| `QTabBar` | `bool isTabVisible(int) const` | 5.14 | Low |
| `QTabBar` | `void setTabVisible(int, bool)` | 5.14 | Low |
| `QTableView` | `void sortByColumn(int, Qt::SortOrder)` (as a slot) | 5.13 | Low |
| `QTableWidgetSelectionRange` | `operator=(const &)` | 5.15 | Low |
| `QTextBrowser` | `QTextDocument::ResourceType sourceType() const` | 5.14 | Low |
| `QTextBrowser` | `void setSource(const QUrl &, ResourceType)` | 5.14 | Low |
| `QTextBrowser` | `void doSetSource(const QUrl &, ResourceType)` | 5.14 | 🔴 High |
| `QTextEdit` | `QString toMarkdown(MarkdownFeatures)` | 5.14 | 🟠 Medium |
| `QTextEdit` | `void setMarkdown(const QString &)` | 5.14 | 🟠 Medium |
| `QTextEdit` | `bool find(const QRegularExpression &, ...)` | 5.13 | Low |
| `QTreeView` | `void sortByColumn(int, Qt::SortOrder)` (as a slot) | 5.13 | Low |
| `QTreeView` | `void expandRecursively(const QModelIndex &, int)` | 5.13 | Low |
| `QWidget` | `QScreen *screen() const` | 5.14 | Low |
| `QWizard` | `QList<int> visitedIds() const` | 5.15 | Low |

### 4.2 New enums

| Class | Enum | Values | Version |
|-------|------|--------|:-------:|
| `QActionGroup` | `ExclusionPolicy` (an enum class) | `None`, `Exclusive`, `ExclusiveOptional` | 5.14 |
| `QFileSystemModel` | `Option` | `DontWatchForChanges`, `DontResolveSymlinks`, `DontUseCustomDirectoryIcons` | 5.14 |
| `QStyle::StandardPixmap` | 7 new values | `SP_DialogYesToAllButton`, `SP_DialogNoToAllButton`, `SP_DialogSaveAllButton`, `SP_DialogAbortButton`, `SP_DialogRetryButton`, `SP_DialogIgnoreButton`, `SP_RestoreDefaultsButton` | 5.15 |
| `QStyle::SubElement` | `SE_PushButtonBevel` | A new element | 5.15 |
| `QSystemTrayIcon` (OHOS) | `IconTheme` | `Dark`, `Light` | OHOS-specific |

### 4.3 New Q_ENUM registrations

| Class | Registered enum | Notes |
|-------|-----------------|-------|
| `QActionGroup` | `ExclusionPolicy` | A new enum class |
| `QCompleter` | `CompletionMode` | Previously lacked Q_ENUM |
| `QCompleter` | `ModelSorting` | Previously lacked Q_ENUM |
| `QFileSystemModel` | `Option` | A new enum |
| `QGraphicsScene` | `ItemIndexMethod` | Previously lacked Q_ENUM |

### 4.4 New Q_PROPERTYs

| Class | Property | Version |
|-------|----------|:-------:|
| `QActionGroup` | `ExclusionPolicy exclusionPolicy` | 5.14 |
| `QComboBox` | `QString placeholderText` | 5.14 |
| `QFileSystemModel` | `Options options` | 5.14 |
| `QTextBrowser` | `QTextDocument::ResourceType sourceType` | 5.14 |
| `QTextEdit` | `QString markdown` | 5.14 |

### 4.5 New signals

| Class | Signal | Version | Replaces |
|-------|--------|:-------:|----------|
| `QButtonGroup` | `idClicked(int)` | 5.15 | `buttonClicked(int)` |
| `QButtonGroup` | `idPressed(int)` | 5.15 | `buttonPressed(int)` |
| `QButtonGroup` | `idReleased(int)` | 5.15 | `buttonReleased(int)` |
| `QButtonGroup` | `idToggled(int, bool)` | 5.15 | `buttonToggled(int, bool)` |
| `QComboBox` | `textActivated(const QString &)` | 5.15 | `activated(const QString &)` |
| `QComboBox` | `textHighlighted(const QString &)` | 5.15 | `highlighted(const QString &)` |
| `QSpinBox` | `textChanged(const QString &)` | 5.14 | `valueChanged(const QString &)` |
| `QDoubleSpinBox` | `textChanged(const QString &)` | 5.14 | `valueChanged(const QString &)` |

### 4.6 New Q_DECLARE_MIXED_ENUM_OPERATORS

| File | Declaration | Notes |
|------|-------------|-------|
| `qframe.h` | `Q_DECLARE_MIXED_ENUM_OPERATORS_SYMMETRIC(int, QFrame::Shape, QFrame::Shadow)` | Enables mixed-enum arithmetic |
| `qsizepolicy.h` | `Q_DECLARE_MIXED_ENUM_OPERATORS(int, QSizePolicy::Policy, QSizePolicy::PolicyFlag)` | Enables mixed-enum arithmetic |

---

## §5 Deprecated APIs (available in 5.12, marked deprecated in 5.15)

> All deprecated APIs are still present in the headers (inside `QT_DEPRECATED_SINCE` guards); they compile without errors but produce warnings.

### 5.1 Deprecated in 5.13

| Class | Deprecated API | Replacement |
|-------|----------------|-------------|
| `QAbstractItemDelegate` | `elidedText(QFontMetrics, int, TextElideMode, QString)` | `QFontMetrics::elidedText()` |
| `QAbstractItemView` | `setHorizontalStepsPerItem(int)` / `horizontalStepsPerItem()` | No direct replacement |
| `QAbstractItemView` | `setVerticalStepsPerItem(int)` / `verticalStepsPerItem()` | No direct replacement |
| `QComboBox` | `autoCompletion()` / `setAutoCompletion(bool)` | `completer()` / `setCompleter()` |
| `QComboBox` | `autoCompletionCaseSensitivity()` / `setAutoCompletionCaseSensitivity(...)` | `completer()->caseSensitivity()` / `completer()->setCaseSensitivity(...)` |
| `QDialog` | `setOrientation(...)` / `orientation()` / `setExtension(...)` / `extension()` / `showExtension(bool)` | `show`/`hide` on the affected widget |
| `QGraphicsItem` | `matrix()` / `sceneMatrix()` / `setMatrix(...)` / `resetMatrix()` | `transform()` / `sceneTransform()` / `setTransform()` / `resetTransform()` |
| `QGraphicsItemAnimation` | `reset()` | `setStep(0)` |
| `QGraphicsScene` | `isSortCacheEnabled()` / `setSortCacheEnabled(bool)` | No direct replacement |
| `QItemDelegate` | `selected(QPixmap, QPalette, bool)` | `selectedPixmap()` (static) |
| `QListWidget` | `isItemSelected(...)` / `setItemSelected(...)` | `QListWidgetItem::isSelected()` / `setSelected()` |
| `QListWidget` | `isItemHidden(...)` / `setItemHidden(...)` | `QListWidgetItem::isHidden()` / `setHidden()` |
| `QSplitter` | `operator<<(QTextStream&, const QSplitter&)` / `operator>>(QTextStream&, QSplitter&)` | `saveState()` / `restoreState()` |
| `QTableView` | `sortByColumn(int)` (without SortOrder) | `sortByColumn(int, Qt::SortOrder)` |
| `QTreeWidget` | `isItemSelected/setItemSelected/isItemHidden/setItemHidden/isItemExpanded/setItemExpanded/isFirstItemColumnSpanned/setFirstItemColumnSpanned` | The corresponding methods on `QTreeWidgetItem` |
| `QTreeWidgetItem` | `backgroundColor(int)` / `setBackgroundColor(int, QColor)` | `background()` / `setBackground()` |
| `QTreeWidgetItem` | `textColor(int)` / `setTextColor(int, QColor)` | `foreground()` / `setForeground()` |
| `QTreeView` | `sortByColumn(int)` (without SortOrder) | `sortByColumn(int, Qt::SortOrder)` |
| `QWidget` | `isEnabledToTLW() const` | `isEnabled()` |

### 5.2 Deprecated in 5.14

| Class | Deprecated API | Replacement |
|-------|----------------|-------------|
| `QFileDialog::Option` | `DontUseSheet` | None (unused outside macOS) |
| `QGraphicsItem::GraphicsItemChange` | `ItemMatrixChange` | `ItemTransformChange` |
| `QGraphicsItemAnimation` | `matrixAt(qreal)` | `transformAt(qreal)` |
| `QLineEdit` | `getTextMargins(int*, int*, int*, int*)` | `textMargins()` |
| `QWidget` | `getContentsMargins(int*, int*, int*, int*)` | `contentsMargins()` |

### 5.3 Deprecated in 5.15

| Class | Deprecated API | Replacement |
|-------|----------------|-------------|
| `QApplication` | The `globalStrut` property / `setGlobalStrut()` / `globalStrut()` | None (unused) |
| `QButtonGroup` | The `buttonClicked(int)` signal | `idClicked(int)` |
| `QButtonGroup` | The `buttonPressed(int)` signal | `idPressed(int)` |
| `QButtonGroup` | The `buttonReleased(int)` signal | `idReleased(int)` |
| `QButtonGroup` | The `buttonToggled(int, bool)` signal | `idToggled(int, bool)` |
| `QComboBox::SizeAdjustPolicy` | `AdjustToMinimumContentsLength` | `AdjustToContents` or `AdjustToContentsOnFirstShow` |
| `QComboBox` | The `activated(const QString &)` signal | `textActivated(const QString &)` |
| `QComboBox` | The `highlighted(const QString &)` signal | `textHighlighted(const QString &)` |
| `QComboBox` | The `currentIndexChanged(const QString &)` signal | `currentIndexChanged(int)` + `itemText(index)` |
| `QDirModel` | **The whole class** (its constructor) | `QFileSystemModel` |
| `QDockWidget::DockWidgetFeature` | `AllDockWidgetFeatures` | Combine the flags explicitly |
| `QFileDialog::FileMode` | `DirectoryOnly` | `setOption(ShowDirsOnly, true)` |
| `QGraphicsView` | `matrix()` / `setMatrix(...)` / `resetMatrix()` | `transform()` / `setTransform()` / `resetTransform()` |
| `QMacCocoaViewContainer` | **The whole class** | `QWindow::fromWinId` + `createWindowContainer` |
| `QMacNativeWidget` | **The whole class** | `QWidget::winId` |
| `QSpinBox` | The `valueChanged(const QString &)` signal | `textChanged(const QString &)` |
| `QDoubleSpinBox` | The `valueChanged(const QString &)` signal | `textChanged(const QString &)` |
| `QSplashScreen` | The `QSplashScreen(QWidget *, ...)` constructor | `QSplashScreen(QScreen *, ...)` |
| `QStyle::PixelMetric` | `PM_DefaultTopLevelMargin` / `PM_DefaultChildMargin` / `PM_DefaultLayoutSpacing` | None |
| `QStyle::SubElement` | `SE_DialogButtonBoxLayoutItem` | None |
| `QTextBrowser` | The `highlighted(const QString &)` signal | `highlighted(const QUrl &)` |
| `QWizard` | `visitedPages()` | `visitedIds()` |

---

## §6 Signature changes / behavioral differences

### 6.1 Signature changes

| Class | Change | Notes |
|-------|--------|-------|
| `QAction` | `#ifndef QT_NO_SHORTCUT` → `#if QT_CONFIG(shortcut)` | Modernizing the configuration system; same effect |
| `QDateTimeEdit` | The new constructor uses `QMetaType::Type` instead of `QVariant::Type` | The old constructor is kept inside a `QT_VERSION < 6.0.0` guard |
| `QInputDialog::getDouble()` | Unified into a single signature with `step` as a default argument | The old two-overload form is kept inside a version guard |
| `QMainWindow::toolBarArea` | `QToolBar *` → `const QToolBar *` (the Qt6 pattern) | A const correction |
| `QTableWidgetSelectionRange` | Added `operator=` | It previously had no assignment operator |
| `QWidget::insertActions` | `const QAction *before` → `QAction *before` (the Qt6 pattern) | A const correction |
| `QWidget::nativeEvent` | `long *result` → `qintptr *result` (the Qt6 pattern) | 64-bit safety |
| `QWizard::nativeEvent` | Likewise `long *` → `qintptr *` (the Qt6 pattern) | 64-bit safety |
| `QSizePolicy` | `Q_DECL_NOTHROW` → `noexcept` (across all methods) | Modernization; binary compatible |

### 6.2 Q_PROPERTY DESIGNABLE attributes removed

| Class | Property | Old | New |
|-------|----------|-----|-----|
| `QAction` | `checked` | `DESIGNABLE isCheckable` | (removed) |
| `QAbstractButton` | `checked` | `DESIGNABLE isCheckable` | (removed) |
| `QGroupBox` | `checked` | `DESIGNABLE isCheckable` | (removed) |
| `QWidget` | `windowTitle`/`windowIcon`/`windowIconText`/`windowOpacity`/`windowModified`/`windowFilePath` | `DESIGNABLE isWindow` | (removed) |
| `QToolBar` | `movable`/`allowedAreas`/`orientation` | `DESIGNABLE (qobject_cast<...>)` | (removed) |

**Impact**: low — this only affects Qt Designer's behavior, not runtime code.

### 6.3 Enum value reordering

| Enum | Change | Impact |
|------|--------|--------|
| `QGraphicsItem::GraphicsItemChange` | `ItemVisibleChange` is explicitly `= 2` | Binary compatible; the value is unchanged |
| `QComboBox::SizeAdjustPolicy` | `AdjustToMinimumContentsLengthWithIcon = AdjustToContentsOnFirstShow + 2` | An explicit value; backward compatible |
| `QStyle::SubElement` | `SE_LabelLayoutItem = SE_DateTimeEditLayoutItem + 2` (leaving a gap for the deprecated value) | Binary compatible |
| `QStyle::PixelMetric` | `PM_ToolBarIconSize = PM_SpinBoxSliderHeight + 4` (leaving a gap for the deprecated values) | Binary compatible |

### 6.4 QStyleOption operator= modernization

Every `QStyleOption*` class replaced its hand-written `operator=` with `= default`:
`QStyleOptionTabWidgetFrame`, `QStyleOptionTabBarBase`, `QStyleOptionHeader`, `QStyleOptionButton`, `QStyleOptionTab`, `QStyleOptionToolBar`, `QStyleOptionProgressBar`, `QStyleOptionFocusRect`, `QStyleOptionFrame`, `QStyleOptionViewItem`.

**Impact**: low — binary compatible, and `= default` has exactly the same semantics as the hand-written version.

### 6.5 QActionGroup: `exclusive` → `ExclusionPolicy`

The `bool exclusive` property was replaced by an `ExclusionPolicy exclusionPolicy`. `setExclusive(bool)` and `isExclusive()` still work, but `exclusionPolicy` adds an `ExclusiveOptional` mode.

**Migration**: 🟠 medium — code using `setExclusive(false)` should migrate to `setExclusionPolicy(ExclusionPolicy::None)`.

---

## §7 APIs removed (present in 5.12, absent in 5.15)

**No public API was genuinely removed** — every deprecated API is still available inside a `QT_DEPRECATED_SINCE` guard.

What "removed" means below is that they were placed behind a deprecation guard:

| Class | Notes |
|-------|-------|
| `QDirModel` | The whole class is inside a `QT_DEPRECATED_SINCE(5,15)` guard — it only compiles when deprecated functionality is enabled |
| `QMacCocoaViewContainer` | The whole class is inside a `QT_DEPRECATED_SINCE(5,15)` guard |
| `QMacNativeWidget` | The whole class is inside a `QT_DEPRECATED_SINCE(5,15)` guard |
| `QGraphicsTextItem` | 3 `Q_PRIVATE_SLOT` declarations removed (an internal cleanup) |

---

## §8 Qt6-preparatory code (QT_VERSION guards)

The following APIs have dual signatures based on `QT_VERSION < QT_VERSION_CHECK(6,0,0)`:

| Class | The pattern |
|-------|-------------|
| `QDateTimeEdit` | The constructor: `QVariant::Type` (Qt5) vs. `QMetaType::Type` (Qt6) |
| `QInputDialog::getDouble` | Two overloads (Qt5) vs. a single signature with a default `step` (Qt6) |
| `QMainWindow::toolBarArea` | A non-const (Qt5) vs. const (Qt6) parameter |
| `QWidget::nativeEvent` | `long *result` (Qt5) vs. `qintptr *result` (Qt6) |
| `QWizard::nativeEvent` | The same |
| `QWidget::insertActions` | A non-const (Qt5) vs. const (Qt6) first parameter |
| `QTextBrowser::setSource` | virtual (Qt5) vs. virtual + a default ResourceType (Qt6) |
| `QCommandLinkButton` | `sizeHint`/`heightForWidth`/`minimumSizeHint` protected (Qt5) vs. public (Qt6) |

---

## §9 Other changes (no API impact)

| Type of change | Files involved | Notes |
|----------------|----------------|-------|
| `Q_QDOC` → `Q_CLANG_QDOC` | qmenu.h, qtoolbar.h | An internal documentation-system macro swap |
| `Q_OS_OSX` → `Q_OS_MACOS` | qmenu.h | Platform macro modernization |
| `Q_DECL_EQ_DELETE` → `= delete` | qwhatsthis.h, qtooltip.h | C++11 style modernization |
| `Q_DECL_NOTHROW` → `noexcept` | qsizepolicy.h | C++11 style modernization |
| `QGraphicsTextItem` removed 3 `Q_PRIVATE_SLOT`s | qgraphicsitem.h | An internal cleanup |
| `0` → `nullptr` in `qgraphicsitem_cast` | qgraphicsitem.h | C++11 style |
| `QT_FEATURE_paint_debug` removed from the config | qtwidgets-config.h | An OHOS build configuration difference |
| `QMainWindow::tabifyDockWidget` gained a `QT_CONFIG(tabbar)` guard | qmainwindow.h | Conditional compilation on configuration |

---

## §10 Migration risk assessment

### 10.1 Downgrading 5.15 → 5.12 (breaking changes)

| Risk level | Affected APIs | Notes |
|:----------:|---------------|-------|
| 🔴 High | The OHOS `QSystemTrayIcon` APIs (`IconTheme`, the dual-icon constructor) | They don't exist at all in 5.12, so OHOS tray icon code won't compile |
| 🔴 High | The OHOS `QFileDialog` APIs (`selectedUris()`, `getOpenFileUri()`) | The OHOS file picker extensions don't exist |
| 🔴 High | `QTextBrowser::doSetSource()` | It doesn't exist in 5.12 |
| 🔴 High | The `QCalendar` methods (on `QCalendarWidget`/`QDateTimeEdit`) | The `QCalendar` class isn't in 5.12's public API |
| 🟠 Medium | The `QTextEdit` Markdown APIs (`toMarkdown`/`setMarkdown`/the `markdown` property) | Unavailable in 5.12 |
| 🟠 Medium | The `QFileSystemModel::Options` enum and methods | Unavailable in 5.12 |
| 🟠 Medium | The `QShortcut` template constructors | Unavailable in 5.12 |
| 🟠 Medium | `QStyleOptionTabV4` | Unavailable in 5.12 |
| 🟠 Medium | The `QActionGroup::ExclusionPolicy` enum | Unavailable in 5.12 |
| 🟡 Low | `QWidget::screen()` | Unavailable in 5.12 |
| 🟡 Low | `QTabBar::isTabVisible()`/`setTabVisible()` | Unavailable in 5.12 |
| 🟡 Low | `QTreeView::expandRecursively()` | Unavailable in 5.12 |
| 🟡 Low | `QFileDialog::getOpenFileContent()`/`saveFileContent()` | Unavailable in 5.12 |
| 🟡 Low | `QComboBox::placeholderText` | Unavailable in 5.12 |
| 🟡 Low | The new `QStyle` `SP_*` standard icons | Unavailable in 5.12 |
| 🟡 Low | The `QGraphicsWidget::setContentsMargins(QMarginsF)` overload | Unavailable in 5.12 |
| 🟡 Low | The new signals (`textActivated`/`textHighlighted`/`idClicked` and so on) | The old signal names still work; the new names won't compile |

### 10.2 Upgrading 5.12 → 5.15

| Risk level | Notes |
|:----------:|-------|
| 🟡 Low | Every 5.12 API is retained (possibly deprecated but still compilable) |
| 🟡 Low | Roughly 50+ APIs produce deprecation warnings — the code still compiles |
| 🟡 Low | `QDirModel` produces deprecation warnings — you should migrate to `QFileSystemModel` |
| ℹ️ Info | The OHOS-specific APIs are a bonus for HarmonyOS targets |

---

## References

| Source | Notes |
|--------|-------|
| 🛠️ SDK header comparison | `<LOCAL_PATH>` vs. `<LOCAL_PATH>` |
| 🛠️ diff analysis | Diffed all 67 differing headers individually, extracting patterns such as `class`/`Q_PROPERTY`/`Q_ENUM`/`Q_SIGNALS`/`QT_DEPRECATED_SINCE` |
| 🛠️ Validation baseline | Qt 5.15.16 tqtc/harmonyos-5.15.16 (962aa625) vs. Qt 5.12.12 tqtc/harmonyos-5.12.12 (613336de) |

## Qt framework versions (validation baseline)

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |

---

## Related context

- [[qt-harmonyos-overview]] — Qt on HarmonyOS overview (version information, the QPA architecture)
- [[qt-harmonyos-modules]] — Quick reference to module porting status
- [[qt-harmonyos-build]] — The build guide (the 5.12/5.15 build configuration differences)
- [[qt-harmonyos-api]] — API compatibility differences
- [[qt-harmonyos-qt6-status]] — Qt6 HarmonyOS porting status (a reference for the Qt5→Qt6 differences)
- The technology stack — An overview of the technology stack (the Qt version paths)
