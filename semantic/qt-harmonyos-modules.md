---
id: semantic-qt-harmonyos-modules
type: semantic
domain: tech
tags: [qt, harmonyos, modules, qt5, adaptation-status]
created: 2026-06-02
updated: 2026-11-04
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, problem-ohos-missing-qt5uitools]
summary: >
  Quick reference for Qt 5.12/5.15 HarmonyOS module porting status (refreshed against the wiki matrix on 2026-09-18):
  all the core modules are Completed; QtMultimedia is marked Completed on the wiki, but the official Qt5 SDK doesn't include
  its CMake/QML module, while the Qt-full complete build includes it (with the QOhosAudio/QOhosMediaService plugins);
  unsupported modules (QtWebEngine/D-Bus/RemoteObjects/SerialBus/VirtualKeyboard, etc.);
  5.15 only: QtPDF/QtQuickTimeline/Lottie/Quick3D; 5.12 only: QtXmlPatterns.
---

# Qt module porting status on HarmonyOS

> Source: [Qt5 Module Adaptation Status](https://wiki.qt.io/Qt_for_HarmonyOS/support_modules) (matrix baseline Qt 5.12.12 / Qt 5.15.15, retrieved 2026-09-18)
>
> The ✅/❌ in the tables are the **wiki adaptation status**; "measured on Qt-full" refers to the results of checking the locally built complete SDK (`QT5_15_OHOS_SDK`, based on tqtc/harmonyos-5.15.16 @ 962aa625). Where the two disagree, read the notes first.

## Quick lookup

> **Ecosystem statistics** (a sampling survey of 229 open-source Qt desktop applications, 2026-06): D-Bus (107),
> QtMultimedia (76), and QtWebEngine (62) are the three most frequent blocking modules —
> check these three first when assessing any Qt application.

| I want to check... | Which row below |
|--------------------|-----------------|
| Whether a core module is supported | The Essentials section |
| Whether WebEngine is available | Add-Ons → Qt WebEngine (Out of scope) |
| Whether 3D rendering is supported | Add-Ons → Qt 3D (Completed); Qt Quick 3D is 5.15 only |
| Whether databases are supported | Essentials → Qt SQL (Completed) |
| Whether multimedia works | Essentials → Qt Multimedia (wiki Completed; not in the official SDK, included in Qt-full) |
| Whether charts are available | Add-Ons → Qt Charts (Completed) |

## Essentials (core modules)

| Module | 5.12 | 5.15 | Notes |
|--------|------|------|-------|
| Qt Core | ✅ | ✅ | Signals/slots, object tree, property system |
| Qt GUI | ✅ | ✅ | Window integration, events, OpenGL/ES, 2D graphics, fonts and text |
| Qt Widgets | ✅ | ✅ | Classic C++ desktop-style UI |
| Qt QML | ✅ | ✅ | The QML language and engine infrastructure |
| Qt Quick | ✅ | ✅ | The standard declarative UI library for QML |
| Qt Quick Controls | ✅ | ✅ | Lightweight QML controls (measured on Qt-full: includes the Controls 1 QML and the four Controls 2 styles) |
| Qt Quick Dialogs | ✅ | ✅ | System dialogs |
| Qt Quick Layouts | ✅ | ✅ | QML layouts |
| Qt Quick Test | ✅ | ✅ | QML unit testing |
| Qt Network | ✅ | ✅ | TCP/IP, HTTP, cookies (Qt-full includes QOhosBearerEnginePlugin) |
| Qt SQL | ✅ | ✅ | Database integration (the SQLite driver is present) |
| Qt Test | ✅ | ✅ | Unit testing |
| Qt Multimedia | ✅ | ✅ | wiki Completed; **the official Qt5 SDK doesn't include the CMake/QML module (verified 2026-06-11), so you must build it yourself**; the Qt-full complete build includes libQt5Multimedia.so + QOhosAudioPlugin/QOhosMediaServicePlugin + the QtMultimedia QML (re-checked 2026-09-18) |
| Qt Multimedia Widgets | ✅ | ✅ | Follows Qt Multimedia: not in the official SDK; included in Qt-full (re-checked 2026-09-18) |

## Add-Ons — completed ✅

| Module | 5.12 | 5.15 | Notes |
|--------|------|------|-------|
| Qt 3D (all submodules) | ✅ | ✅ | Near-real-time 2D/3D rendering (measured on Qt-full: the full Core/Input/Logic/Render/Animation/Extras/Quick set is present) |
| Qt Bluetooth | ✅ | ✅ | Bluetooth hardware access |
| Qt Charts | ✅ | ✅ | Chart components (measured on Qt-full: includes libQt5Charts.so + the QtCharts QML) |
| Qt Concurrent | ✅ | ✅ | Multithreading (without low-level primitives) |
| Qt Data Visualization | ✅ | ✅ | 3D data visualization (the wiki marks it Completed; the 5.15.16 source has no ohos{} scope + warning_clean, so it needs an `ohos{ -Wno-deprecated-declarations -Wno-misleading-indentation }` patch to build against the API 26 SDK — the same warning-suppression pattern as qt3d/qtcharts; not included in the Qt-full build) |
| Qt Graphical Effects | ✅ | ✅ | Quick 2 graphical effects (measured on Qt-full: includes the QML plugin) |
| Qt Help | ✅ | ✅ | Documentation integration; on HarmonyOS qttools can only be built on a HarmonyOS PC host, so neither the official SDK nor Qt-full includes it → `problems/build-missing-qt5uitools-ohos.md` |
| Qt Image Formats | ✅ | ✅ | TIFF/MNG/TGA/WBMP |
| Qt Lottie Animation | ❌ | ✅ | **5.15 only**; measured on Qt-full: includes libQt5Bodymovin.so |
| Qt Location | ✅ | ✅ | Maps and navigation (Qt-full includes the OhosMapKit map service plugin) |
| Qt Network Authorization | ✅ | ✅ | OAuth authorization; **the Qt-full 5.15.16 complete build doesn't include libQt5NetworkAuthorization.so (checked 2026-09-18)**, so confirm your kit before using it |
| Qt PDF | ❌ | ✅ | **5.15 only**; the Qt-full complete build doesn't include libQt5Pdf.so either (checked 2026-09-18) |
| Qt Platform Headers | ✅ | ✅ | Platform-specific information wrappers |
| Qt Positioning | ✅ | ✅ | Positioning/satellites/areas (Qt-full includes an OHOS positioning backend) |
| Qt Print Support | ✅ | ✅ | Printing (Qt-full includes QOhosPrinterSupportPlugin) |
| Qt Quick 3D | ❌ | ✅ | **5.15 only**; measured on Qt-full: includes the full set of Quick3D C++ libraries and QML (Effects/Materials/Helpers) |
| Qt Quick Extras | ✅ | ✅ | Specialized controls |
| Qt Quick Timeline | ❌ | ✅ | **5.15 only**; the Qt-full build doesn't include libQt5QuickTimeline.so (checked 2026-09-18) |
| Qt Quick WebGL | ✅ | ✅ | Streaming a Quick UI over the network via WebGL; no QWebGL platform plugin found in the Qt-full build (checked 2026-09-18) |
| Qt Quick Widgets | ✅ | ✅ | Displaying a Quick UI inside a widget |
| Qt SCXML | ✅ | ✅ | SCXML state machines |
| Qt Sensors | ✅ | ✅ | Sensor hardware (Qt-full includes QOhosSensorPlugin) |
| Qt Serial Port | ✅ | ✅ | Physical/virtual serial ports |
| Qt Speech | ✅ | ✅ | Text to speech (Qt-full includes QTextToSpeechEngineOhos) |
| Qt SVG | ✅ | ✅ | SVG rendering |
| Qt UI Tools | ✅ | ✅ | Loading Designer forms at runtime; like Qt Help, it can only be built on a HarmonyOS PC host, so neither the SDK nor Qt-full includes it → `problems/build-missing-qt5uitools-ohos.md` |
| Qt WebChannel | ✅ | ✅ | Qt↔HTML/JS integration |
| Qt WebSockets | ✅ | ✅ | RFC 6455 WebSockets |
| Qt WebView | ✅ | ✅ | Native WebView (Qt-full includes QOhosWebViewPlugin); for a full browser engine use CEF for OpenHarmony |
| Qt XML | ✅ | ✅ | SAX/DOM C++ implementations (QXmlStreamReader/Writer belong to Qt Core) |
| Qt XML Patterns | ✅ | ❌ | **5.12 only** (wiki: 5.12 Completed / 5.15 Out of scope); XPath/XQuery/XSLT |

## Add-Ons — out of scope ❌

| Module | Reason |
|--------|--------|
| Active Qt | Windows-only (ActiveX/COM) |
| Qt Android Extras | Android-only |
| Qt D-Bus | HarmonyOS has no D-Bus |
| Qt Gamepad | The wiki's target platforms are Android/iOS/macOS/tvOS/Linux/Windows, not HarmonyOS |
| Qt Mac Extras | macOS-only |
| Qt NFC | The wiki's target platforms are Android/Linux only; **measured on the Qt-full complete build: includes libQt5Nfc.so + the QtNfc QML (2026-09-18)**; the port is unverified, so treat it as restricted |
| Qt Purchasing | In-app purchase on Android/iOS/macOS |
| Qt Remote Objects | Out of scope (included in the Qt6 prebuilt kit; see qt-harmonyos-qt6-status) |
| Qt Serial Bus | Windows/Linux/Boot to Qt-only |
| Qt Virtual Keyboard | wiki Out of scope; **measured on the Qt-full complete build: includes libQt5VirtualKeyboard.so + input method plugins such as Pinyin/OpenWnn/Hangul (2026-09-18)** — for soft keyboard needs, use Qt-full or build it yourself |
| Qt WebEngine (all submodules) | Windows/Linux/macOS-only (Chromium); the alternative is CEF for OpenHarmony |
| Qt Win Extras | Windows-only |
| Qt X11 Extras | X11-only |
| Qt Wayland Compositor | A Linux/Wayland compositor framework; the HarmonyOS window model isn't Wayland |
| Qt for WebAssembly | A browser platform target, unrelated to HarmonyOS device form factors |
| Qt Automotive Suite | An automotive product suite (Value-Add) |
| Qt for Automation | An automation product (KNX/OPC UA/MQTT, Value-Add) |
| Qt for MCUs | An MCU platform product (Value-Add) |

## Tools (Qt tools)

| Module | 5.12 | 5.15 | Notes |
|------|------|------|------|
| Qt Designer | ✅ | ✅ | Designer extension classes; qttools has the same HarmonyOS-PC-host-only build restriction, so Qt-full doesn't include it |
| Qt Distance Field Generator | ❌ | ✅ | 5.15 only; a text distance field generation tool |

## Value-Add (value-add products)

| Product | 5.12 | 5.15 | Notes |
|------|------|------|------|
| Qt for Device Creation | ✅ | ✅ | A product for embedded device application development (Boot to Qt-style toolchain) |

## Local verification record (Qt-full 5.15.16, 2026-09-18)

Verified: `QT5_15_OHOS_SDK` (the Qt-full complete build, arm64-v8a, tqtc/harmonyos-5.15.16 @ 962aa625); method: checking three layers — lib/cmake, lib/libQt5*.so, and qml/.

- **wiki Completed and present in practice**: Charts, XML, Lottie (Bodymovin), the full Quick 3D set, Multimedia (with the QOhosAudio/QOhosMediaService plugins), Bluetooth, Location (with OhosMapKit), Positioning/Sensors/TextToSpeech/WebView/PrintSupport (with OHOS backend plugins), Quick Controls 1+2, GraphicalEffects, QuickWidgets, QuickShapes/Particles, Scxml, WebSockets, WebChannel, SerialPort, Concurrent, OpenGL, OhosExtras.
- **wiki Completed but missing in practice**: DataVisualization (needs the warning-suppression patch), Help/UiTools (HarmonyOS PC host builds only), Pdf, QuickTimeline, NetworkAuthorization, Quick WebGL (no QWebGL platform plugin found).
- **wiki Out of scope but present in practice (port unverified, use with caution)**: Nfc, VirtualKeyboard.
- Note: the wiki matrix baseline is 5.15.15, while the local verification is on 5.15.16; the wiki's "Completed" means the port is done, not that the official SDK binaries necessarily include it (Multimedia is the precedent).

## Platform macros change with the version (measured on Qt 6.12+ / 6.13.0-dev)

In the Qt 6 series, the OHOS branch of `qsystemdetection.h` defines only **`Q_OS_HARMONY`** and no longer defines
`Q_OS_OHOS`; the 5.15-series kit defines both. Measurements of 14 platform dispatch headers under 6.13.0-dev all agree:

- Header dispatch files must write `#if defined Q_OS_OHOS || defined Q_OS_HARMONY`, or the branch is never taken;
- That kit includes OpenGL / OpenGLWidgets (QOpenGLWidget is usable); whether Svg is in the package must be confirmed separately;
- To determine "which module and which branch actually got compiled", you must use the full compile command plus `-H`; don't just read `flags.make`.

The module list itself doesn't change with the macro name; **a macro name change silently changes which platform branch is taken**, and that's the link most easily missed.
Audit command: `python tools/ohos-platform-audit.py <app>/SourceFiles/platform`.

## References

- [Qt for HarmonyOS Module Adaptation Status](https://wiki.qt.io/Qt_for_HarmonyOS/support_modules) (English, retrieved 2026-09-18)
- [Chinese mirror](https://wiki.qt.io/Qt_for_HarmonyOS/support_modules_zh)
