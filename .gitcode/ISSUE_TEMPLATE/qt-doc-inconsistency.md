---
name: Qt behavior contradicts the documentation (Qt bug)
about: Qt's behavior on HarmonyOS clearly contradicts the Qt documentation; classified as a Qt bug
title: "[Qt doc inconsistency] "
labels: ["qt-bug", "needs-triage"]
---

## One-sentence description
<!-- Which Qt API / behavior clearly contradicts the Qt documentation -->

## Documentation evidence (required)
- Link to the Qt docs:
- Quote from the docs: <!-- paste the passage stating what "should" happen -->

## Actual behavior on HarmonyOS
<!-- The specific points that differ from the docs; attach a backtrace for crashes, details for wrong return values / rendering glitches -->

## Environment details (required, for internal reproduction + reporting to the Qt team)
- Qt version: <!-- 5.12.12 / 5.15.16 / 6.x; include the tqtc/harmonyos branch + commit -->
- HarmonyOS version / API: <!-- API 17 / 20 etc. -->
- Device model + system version:
- DevEco Studio version:
- OHOS SDK (native) version:

## Minimal reproduction
<!-- A pure-Qt minimal demo (with HarmonyOS-specific business logic stripped out), so it can be reported to the Qt team -->
1.
2.
3.
- [ ] Demo repository link available:

## Logs
<!-- Key hilog / Qt debug excerpts; attach a backtrace for crashes -->

## Has a QTBUG already been filed?
<!-- If already reported on bugreports.qt.io, paste the number/link; if not, note whether you need our help filing it -->

## Can you provide a pure-HarmonyOS minimal demo?
<!-- Used to tell a Qt problem apart from a HarmonyOS system-interface problem (reproduces in a pure HarmonyOS demo = system issue; reproduces in a pure Qt demo = Qt issue) -->
