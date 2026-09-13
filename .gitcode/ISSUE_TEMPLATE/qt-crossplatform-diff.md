---
name: Qt cross-platform behavior difference (undocumented)
about: Qt behaves differently on HarmonyOS than on other platforms, and the Qt docs don't mention the difference
title: "[Qt cross-platform difference] "
labels: ["qt-crossplatform", "needs-triage"]
---

## One-sentence description
<!-- Which Qt API / behavior differs on HarmonyOS compared to other platforms -->

## Environment details (required, for internal reproduction and analysis)
- Qt version: <!-- 5.12.12 / 5.15.16 / 6.x; include the tqtc/harmonyos branch + commit -->
- HarmonyOS version / API: <!-- API 17 / 20 etc. -->
- Device model + system version:
- DevEco Studio version:
- OHOS SDK (native) version:
- CMake / toolchain version:

## Expected behavior on other platforms
<!-- Behavior on Windows / Linux / macOS / Android; state the platform + Qt version -->

## Actual behavior on HarmonyOS
<!-- Detailed description; include whether it crashes / renders incorrectly / silently no-ops / returns a different value -->

## Have you checked the documentation?
- [ ] Qt official documentation (paste link; does it mention this platform difference?)
- [ ] HarmonyOS official documentation (paste link)
- [ ] This knowledge base's semantic/qt-harmonyos-platform-limits.md (is it already recorded as a known limitation?)

## Minimal reproduction
<!-- Steps for a minimal Qt project with business logic stripped out; a demo repository link is welcome -->
1.
2.
3.

## Logs
<!-- Key hilog / Qt debug output excerpts; attach a backtrace for crashes -->

## Your initial attribution
<!-- Which do you lean toward: a Qt problem / a HarmonyOS system problem / an application problem? Briefly explain why -->
