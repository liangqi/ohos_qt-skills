---
id: semantic-qt-harmonyos-overview
type: semantic
domain: tech
tags: [qt, harmonyos, ohos, huawei, cross-platform, qpa]
created: 2026-06-02
updated: 2026-08-14
status: active
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-api, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-modules, semantic-qt-ohos-extras]
summary: >
  Qt for HarmonyOS overview: an introduction to HarmonyOS, the Qt-on-HarmonyOS architecture (the QPA plugin mechanism),
  porting progress (Qt 5.12.12/5.15.16, roughly 90% ported),
  supported devices (phone/tablet/PC/2-in-1), and how to obtain the source (Gerrit tqtc-qt5).
---

# Qt for HarmonyOS overview

## Introduction to HarmonyOS

HarmonyOS is a distributed operating system developed by Huawei, targeting phones, tablets, smart screens, watches, PCs, and more.
- **Microkernel design** + a single framework, choosing an appropriate kernel based on device resources
- **First released in 2019**; versions 1–4 were originally based on AOSP + the Linux kernel
- **HarmonyOS NEXT** (released October 2024): switched to Huawei's own HarmonyOS microkernel, removed all Android code, and supports only the native "App" format
- **May 2025**: the first laptop running HarmonyOS PC was released

## The core mechanism for Qt on HarmonyOS

Qt interfaces with HarmonyOS through a **QPA (Qt Platform Abstraction) plugin**:
- The QPA plugin adapts Qt's abstract interfaces for the window system, event loop, and graphics rendering onto HarmonyOS's ArkUI/ArkTS layer
- Underneath, **Node-API** (based on Node.js 12.x LTS) provides cross-language interaction between C/C++ and ArkTS
- The rendering surface uses **XComponent** (a native ArkUI component); note that it is deprecated as of API 20 and you should migrate to ContentSlot

## Version information

| Item | Details |
|------|---------|
| Qt version | **Qt 5.12.12 LTS** (primary), Qt 5.15.16 |
| Minimum SDK | HarmonyOS SDK **API 15** |
| Recommended SDK | API 17 (HarmonyOS 5) / API 20 (latest features) |
| Porting progress | Roughly **90%** of the core modules (mid-2025) |
| Target architecture | arm64-v8a |

## Obtaining the source

1. Go to [https://codereview.qt-project.org](https://codereview.qt-project.org) and sign in
2. Settings → HTTP Credentials → GENERATE NEW PASSWORD
3. Clone the repository: `https://codereview.qt-project.org/qt/tqtc-qt5`
4. Switch branches:
   - `git checkout tqtc/harmonyos-5.12.12` (Qt 5.12)
   - `git checkout tqtc/harmonyos-5.15.16` (Qt 5.15)
5. Initialize submodules: `git submodule update --init --recursive`

## Development toolchain

| Tool | Purpose |
|------|---------|
| **DevEco Studio** | Huawei's official IDE; provides the SDK, emulator, and signing/packaging |
| **Qt Creator** | The Qt development IDE; used for C++ development once a HarmonyOS Kit is configured |
| **hdc** | HarmonyOS Device Connector — device debugging, file transfer, installation |
| **CMake** | Build system (cross-compilation within DevEco) |

## Related

- [[qt-harmonyos-build]] — Build guide
- [[qt-harmonyos-api]] — API compatibility notes
- [[qt-harmonyos-platform-limits]] — Platform limitations
- [[qt-harmonyos-modules]] — Module porting status
- [[qt-harmonyos-lifecycle]] — Lifecycle / development guide (dev-guide has been archived)
- [[qt-ohos-extras]] — The QtOhosExtras module
- [[ohos-common-kb/semantic/harmonyos-development-fundamentals|HarmonyOS development fundamentals]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-development-fundamentals.md))

## References

- [Qt for HarmonyOS Wiki](https://wiki.qt.io/Qt_for_HarmonyOS)
- [Building Qt for HarmonyOS](https://wiki.qt.io/Building_Qt_for_HarmonyOS)
- [HarmonyOS Development Fundamentals](https://wiki.qt.io/HarmonyOS_Development_Fundamentals)
