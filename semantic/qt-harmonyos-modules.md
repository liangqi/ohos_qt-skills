---
id: semantic-qt-harmonyos-modules
type: semantic
domain: tech
tags: [qt, harmonyos, modules, qt5, adaptation-status]
created: 2026-06-02
updated: 2026-06-11
status: active
audience: public
refs: [semantic-qt-harmonyos-overview]
summary: >
  Quick reference for Qt 5.12/5.15 HarmonyOS module porting status: all the core modules (QtCore/GUI/Widgets/QML/Quick/
  Network/SQL) are done; **QtMultimedia is not included in the SDK** (you must build it yourself);
  unsupported modules (QtWebEngine/D-Bus/RemoteObjects/SerialBus);
  partially supported modules (QtPDF/QtQuickTimeline, 5.15 only).
---

# Qt module porting status on HarmonyOS

> Source: [Qt5 Module Adaptation Status](https://wiki.qt.io/Qt_for_HarmonyOS/support_modules)

## Quick lookup

| I want to check... | Which row below |
|--------------------|-----------------|
| Whether a core module is supported | The Essentials section |
| Whether WebEngine is available | Add-Ons → Qt WebEngine (Out of scope) |
| Whether 3D rendering is supported | Add-Ons → Qt 3D (Completed) |
| Whether databases are supported | Essentials → Qt SQL (Completed) |

## Essentials (core modules)

| Module | 5.12 | 5.15 | Notes |
|--------|------|------|-------|
| Qt Core | ✅ | ✅ | Signals/slots, object tree, property system |
| Qt GUI | ✅ | ✅ | Window integration, events, OpenGL/ES, 2D graphics, fonts and text |
| Qt Widgets | ✅ | ✅ | Classic C++ desktop-style UI |
| Qt QML | ✅ | ✅ | The QML language and engine infrastructure |
| Qt Quick | ✅ | ✅ | The standard declarative UI library for QML |
| Qt Quick Controls | ✅ | ✅ | Lightweight QML controls |
| Qt Quick Dialogs | ✅ | ✅ | System dialogs |
| Qt Quick Layouts | ✅ | ✅ | QML layouts |
| Qt Quick Test | ✅ | ✅ | QML unit testing |
| Qt Network | ✅ | ✅ | TCP/IP, HTTP, cookies |
| Qt SQL | ✅ | ✅ | Database integration |
| Qt Test | ✅ | ✅ | Unit testing |
| Qt Multimedia | ❌ | ❌ | **Not included in the SDK**; the wiki marks it Completed, but the SDK actually has no CMake/QML module (verified 2026-06-11) |
| Qt Multimedia Widgets | ❌ | ❌ | **Not included in the SDK**; missing along with Qt Multimedia |

## Add-Ons — completed ✅

| Module | 5.12 | 5.15 | Notes |
|--------|------|------|-------|
| Qt 3D (all submodules) | ✅ | ✅ | Near-real-time 2D/3D rendering |
| Qt Data Visualization | ✅ | ✅ | 3D data visualization (the wiki marks it Completed; the 5.15.16 source has no ohos{} scope + warning_clean, so it needs an `ohos{ -Wno-deprecated-declarations -Wno-misleading-indentation }` patch to build against the API 26 SDK — the same warning-suppression pattern as qt3d/qtcharts) |
| Qt Bluetooth | ✅ | ✅ | Bluetooth hardware access |
| Qt Concurrent | ✅ | ✅ | Multithreading (without low-level primitives) |
| Qt Graphical Effects | ✅ | ✅ | Quick 2 graphical effects |
| Qt Help | ✅ | ✅ | Documentation integration |
| Qt Image Formats | ✅ | ✅ | TIFF/MNG/TGA/WBMP |
| Qt Location | ✅ | ✅ | Maps and navigation |
| Qt PDF | ❌ | ✅ | **5.15 only** |
| Qt Platform Headers | ✅ | ✅ | Platform-specific information wrappers |
| Qt Positioning | ✅ | ✅ | Positioning/satellites/areas |
| Qt Print Support | ✅ | ✅ | Printing |
| Qt Quick Extras | ✅ | ✅ | Specialized controls |
| Qt Quick Timeline | ❌ | ✅ | **5.15 only** |
| Qt Quick Widgets | ✅ | ✅ | Displaying a Quick UI inside a widget |
| Qt SCXML | ✅ | ✅ | SCXML state machines |
| Qt Sensors | ✅ | ✅ | Sensor hardware |
| Qt Serial Port | ✅ | ✅ | Physical/virtual serial ports |
| Qt Speech | ✅ | ✅ | Text to speech |
| Qt SVG | ✅ | ✅ | SVG rendering |
| Qt UI Tools | ✅ | ✅ | Loading Designer forms at runtime |
| Qt WebChannel | ✅ | ✅ | Qt↔HTML/JS integration |
| Qt WebSockets | ✅ | ✅ | RFC 6455 WebSockets |
| Qt WebView | ✅ | ✅ | Native WebView |

## Add-Ons — out of scope ❌

| Module | Reason |
|--------|--------|
| Active Qt | Windows-only (ActiveX/COM) |
| Qt Android Extras | Android-only |
| Qt D-Bus | HarmonyOS has no D-Bus |
| Qt Gamepad | No gamepad support |
| Qt Mac Extras | macOS-only |
| Qt NFC | No NFC support |
| Qt Purchasing | In-app purchase on Android/iOS/macOS |
| Qt Remote Objects | Out of scope |
| Qt Serial Bus | Windows/Linux-only |
| Qt WebEngine (all submodules) | Windows/Linux/macOS-only (Chromium) |
| Qt Win Extras | Windows-only |
| Qt X11 Extras | X11-only |

## References

- [Qt for HarmonyOS Module Adaptation Status](https://wiki.qt.io/Qt_for_HarmonyOS/support_modules)
