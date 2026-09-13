---
id: problem-runtime-style-dark-palette-pure-black
type: problem
domain: runtime
tags: [runtime, ui-style, palette, dark-theme, qml, SystemPalette, pure-black, QOhosPlatformTheme, createDarkModePalette, setPalette, Q_OS_OHOS, RESP]
created: 2026-07-29
updated: 2026-07-29
status: solved
severity: medium
audience: public
refs: [semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-platform-limits, problem-runtime-crash-libqohos-modules-mismatch]
summary: >
  Under the OHOS system dark theme, buttons and text fields in a Qt QML application have pure-black backgrounds and are unreadable. Root cause: QOhosPlatformTheme's Dark palette sets
  QPalette::Base = activeWindowFrame = #000000 (pure black), QML's SystemPalette.base takes that, and the application uses sysPalette.base
  as the widget/window background → everything is pure black. Fix: add a Q_OS_OHOS branch in app.cpp calling QGuiApplication::setPalette(createDarkModePalette())
  as an override (setColorsTheme doesn't call setPalette, so the override persists); base #1E1E1E is readable.
leader_summary: >
  Captured the root cause of pure-black widgets in Qt QML applications under the OHOS dark theme (the platform's palette.Base takes the window frame color) and the application-level override fix —
  a common styling blocker when batch-porting dark-themed Qt QML applications
impact: [Migration efficiency, Framework support]
deliverables: [problem record, the RESP.app styling fix (app.cpp), before/after device screenshots]
evidence: [The Q_OS_OHOS palette override in src/app/app.cpp, screenshot/resp-after-fix.png, the #FF000000 string in libqohos.so]

# ====== Search keywords (for fast agent matching) ======
error_message: >
  A visual symptom (not an error): under the OHOS dark theme, a Qt QML application's Button and TextField default background color is pure black (#000000),
  merging into the window background so widget boundaries are indistinguishable; the light-colored text is visible but the widgets aren't.
  The root-cause log clue: QOhosPlatformTheme Dark palette: QPalette::Base = system.activeWindowFrame = QColor("#FF000000")
  (qohosplatformtheme.cpp:204, :485). QML SystemPalette.base → app.qml `color: sysPalette.base`
  / BetterButton `palette.button: sysPalette.button` / BetterTextField base → pure black.
  strings libqohos.so contains "#FF000000" (the Dark activeWindowFrame) and "#FFE4E4E4" (Light).
error_code: ""
keywords: [palette, Base, activeWindowFrame, "#000000", "#FF000000", Dark theme, SystemPalette, sysPalette, QML, Controls, pure black, QOhosPlatformTheme, setColorsTheme, createDarkModePalette, setPalette, Q_OS_OHOS, Q_OS_LINUX, G1, Fusion, darkmode.h, isDarkThemeEnabled, RESP.app, dark theme, pure black background, widgets unreadable]
symptoms: >
  A Qt QML application running on an OHOS device with the dark theme: buttons and text fields have pure-black default backgrounds, and the widgets merge into the background with indistinguishable boundaries (though the text is visible).

# ====== Problem details ======
environment: >
  Qt 5.15.16 OHOS SDK (${QT5_15_OHOS_SDK_FULL}, libqohos.so 5.8 MB, built 2026-07-25) |
  HarmonyOS | HUAWEI MateBook Fold (system dark theme) | RESP.app (Redis Desktop Manager), a Qt5 QML application (QApplication entry point)

---

# Pure-black widget backgrounds in Qt applications under the OHOS dark theme (palette.Base = activeWindowFrame = \#000000)

## Error message (a visual symptom)

Pure-black widget backgrounds, with no error. Screenshot signature: a Qt QML application on an OHOS device with the dark theme, where Button/TextField background = \#000000 (pure black), merging into the window background (which also uses sysPalette.base) so widget boundaries are indistinguishable; the light-colored text is visible.

## Scenario

Porting a Qt5 QML application (such as RESP.app) to OHOS, where the application's QML uses `SystemPalette`'s (sysPalette) base/button colors for widget and window backgrounds (`color: sysPalette.base`). It shows up on any device with the system dark theme (a HUAWEI MateBook Fold); devices with the Light theme are fine (\#FFE4E4E4 light gray is readable).

## Cause (three layers, from surface to root)

### Layer 1: the Dark palette of OHOS's QOhosPlatformTheme has Base = pure black

In `qtbase/src/plugins/platforms/ohos/qohosplatformtheme.cpp`:
```cpp
// Light theme (line 194):
.activeWindowFrame = QColor("#FFE4E4E4"),   // light gray
// Dark theme (line 204):
.activeWindowFrame = QColor("#FF000000"),   // ★ pure black
```
`makeSystemPalette` sets `QPalette::Base = system.activeWindowFrame` (lines 485-487):
```cpp
{QPalette::Active,   QPalette::Base, palettesColors.system.activeWindowFrame},  // Dark → #000000
{QPalette::Disabled, QPalette::Base, palettesColors.system.inactiveWindowFrame}, // #FF18181A
{QPalette::Inactive, QPalette::Base, palettesColors.system.inactiveWindowFrame},
```
In other words, **OHOS uses the "window frame color" (activeWindowFrame) as `QPalette::Base`**. In the Dark theme the window frame is \#000000, so Base is pure black. In the Light theme it's \#FFE4E4E4 light gray, so Light devices are fine.

### Layer 2: QML's SystemPalette.base comes straight from QGuiApplication::palette().Base

The base color of QML's `SystemPalette` (app.qml:87, `id: sysPalette`) comes from `QGuiApplication::palette().color(QPalette::Base)`. On OHOS Dark → sysPalette.base = \#000000.

Applications commonly use sysPalette.base as a background in QML:
- `app.qml:290 color: sysPalette.base` (the appWrapper background)
- `app.qml:383 color: sysPalette.base` (the TabBar background)
- `BetterButton.qml:18 palette.button: sysPalette.button`
- `BetterTextField` (which uses the base color for the input background)

→ Every widget and the window background = sysPalette.base = \#000000 → everything pure black, with indistinguishable widgets.

### Layer 3: the application's existing dark-mode override doesn't fire on OHOS

The existing dark override in the application's `src/app/app.cpp` was designed only for Windows/Linux desktop, and on OHOS the branch is taken but its body doesn't run:
```cpp
#if defined(Q_OS_WINDOWS) || defined(Q_OS_LINUX)   // ★ G1: Q_OS_OHOS implies Q_OS_LINUX → OHOS takes this branch
  if (isDarkThemeEnabled()) {                      // ★ darkmode.h's LINUX branch reads the QSettings "app/darkModeOn" (default false)
    setStyle(QStyleFactory::create("Fusion"));     //    → on OHOS it returns false → no override
    setPalette(createDarkModePalette());           //    → so the OHOS platform default palette is used (Dark Base = black)
  }
#endif
```
- golden-rules **G1**: `Q_OS_OHOS` implies `Q_OS_LINUX`, so a `#if Q_OS_LINUX` branch is taken on OHOS (even though the application meant Windows/Linux desktop).
- `darkmode.h`'s `isDarkThemeEnabled()` `Q_OS_LINUX` branch reads the `QSettings app/darkModeOn` (default false); OHOS has no such setting → it returns false → the override doesn't run → the OHOS platform palette (Dark Base = black) is used.

## Solution (override the palette at the application level)

Add an OHOS-specific branch in `app.cpp` that unconditionally calls `setPalette(createDarkModePalette())` (base = \#1E1E1E, a readable dark gray):

```cpp
#if defined(Q_OS_OHOS)
  // OHOS dark theme: Base = activeWindowFrame = #000000 → QML's sysPalette.base is pure black.
  // Override it with a readable dark palette (base #1E1E1E, button #323232, text #DFDFDF).
  // setColorsTheme() only flips the platform's internal palette map and doesn't call QGuiApplication::setPalette(),
  // so a single application-level setPalette override persists and we don't need to track color-mode changes.
  setPalette(createDarkModePalette());
#elif defined(Q_OS_WINDOWS) || defined(Q_OS_LINUX)
  if (isDarkThemeEnabled()) {
    setStyle(QStyleFactory::create("Fusion"));
    setPalette(createDarkModePalette());
  }
#endif
```

`createDarkModePalette()` (shipped with the application, in `src/app/darkmode.h`): base = `QColor(30,30,30)` (\#1E1E1E), button = `QColor(50,50,50)` (\#323232), text = `QColor(223,223,223)` (\#DFDFDF) — a readable dark gray where widgets and background have contrast and boundaries are visible.

### Why the override persists (the key diagnostic)

`QOhosPlatformTheme::setColorsTheme()` (qohosplatformtheme.cpp:931) only changes `m_currentColorsTheme` (which internal map is selected) and **doesn't call `QGuiApplication::setPalette()`**. `QOhosPlatformTheme::palette()` (:982) returns that internal map.

Qt's logic: `QGuiApplication::palette()` returns `QGuiApplicationPrivate::app_palette` first (if the application called `setPalette`), otherwise falling back to `QPlatformTheme::palette()` (= QOhosPlatformTheme). So once the application calls `setPalette`, `QGuiApplication::palette()` always returns the overridden createDarkModePalette and **never falls back to the platform's black palette**, and later system color-mode changes don't affect it.

## How to verify

1. `build_project(entry@default, debug)` → BUILD SUCCESSFUL (13 s)
2. `start_app` to install it (HUAWEI MateBook Fold, dark theme)
3. `perform_ui_action screenshot` and compare: before the fix, widgets and background are all \#000000; after the fix, base = \#1E1E1E and button = \#323232, with visible widget boundaries and readable text
4. **To determine the theme**: `strings <SDK>/plugins/platforms/libqohos.so | grep -E "FFE4E4E4|FF000000"` — both hex values present means that `.so` contains both the Light and Dark palettes; a device with the system dark theme → takes Dark → Base = \#000000

## Notes

- **The override is unconditional**: the OHOS branch doesn't check the system theme, so the application stays dark even under a Light system (it doesn't follow the system's Light theme). This is because of `setColorsTheme` timing (Dark may only be set after QApplication is constructed) plus the lack of an application-level colorMode change signal, so a conditional override would miss Dark. Being permanently dark is acceptable for a developer tool; to follow the system, you'd need QtOhosExtras' ColorThemeMode (but CMake doesn't support QtOhosExtras — see golden-rules B6).
- **createDarkModePalette is designed for QWidgets Fusion**: its Light/Dark roles are inverted (Light = \#4C4C4C dark, Dark = \#EBEBEB light, for Fusion's 3D raised effect). QML Controls 2's flat widgets don't explicitly use Light/Dark for borders, so those inverted values don't affect BetterButton and friends. base/button/text are the primary usable colors.
- **PlaceholderText isn't set**: createDarkModePalette doesn't set `QPalette::PlaceholderText`, so QPalette's default (a semi-transparent WindowText) is used, which is readable on a dark-gray base. Minor.
- **Non-OHOS platforms are unaffected**: the `#elif Q_OS_WINDOWS || Q_OS_LINUX` branch keeps the original isDarkThemeEnabled logic.
- **Similar but different causes**: QML rendering entirely black with no content (a missing qml/ module deployment) or a white screen (the WMS/Qt visibility state being out of sync) are different problems (see the black-screen/white-screen category in _lookup.md); this page is about widgets/backgrounds being pure black while the application renders correctly (the text is visible), rooted in palette.Base taking the window frame color.

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Captured the root cause of pure-black widgets in Qt QML applications under the OHOS dark theme (the platform's palette.Base takes the window frame color) and the application-level override fix |
| Scope of impact | A common styling blocker when batch-porting dark-themed Qt QML applications to OHOS |
| Deliverables | problem record + the RESP.app app.cpp fix + before/after device screenshots |
| Evidence | The Q_OS_OHOS override in src/app/app.cpp, screenshot/resp-after-fix.png, the \#FF000000 string in libqohos.so |
| How to reuse | Whenever you see "OHOS Qt QML widgets/background pure black but the application renders correctly", apply this page directly: the app.cpp setPalette override + `strings libqohos.so` to confirm the \#FF000000 Dark palette |

## Related

- [[semantic-qt-harmonyos-golden-rules]] G1 (Q_OS_OHOS implies Q_OS_LINUX, so `#if Q_OS_LINUX` branches are taken on OHOS)
- [[semantic-qt-harmonyos-platform-limits]] OHOS platform behavior
- [[problem-runtime-crash-libqohos-modules-mismatch]] The modulesFactories glue-code crash fix in the same project (RESP.app)
- Entirely black / white QML screens (different causes, not this page) → see the "black screen / white screen" category in problems/_lookup.md
- The Qt source `qtbase/src/plugins/platforms/ohos/qohosplatformtheme.cpp` (makeSystemPalette / setColorsTheme / palette)

---

> **Template note**: this template is for recording errors encountered during real execution.
> Known Qt platform limitations (such as chmod being unsupported) belong in `semantic/qt-harmonyos-platform-limits.md` and should not use this template.
