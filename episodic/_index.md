---
domain: episodic
description: >
  Episodic knowledge domain index. Project retrospectives and decision records.
---

# episodic

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| postmortems/ | Pitfalls and retrospectives |
| decisions/ | Architecture decision records (ADRs) |

## Knowledge pages in this domain

- [coin3d-quarter-ohos](postmortems/coin3d-quarter-ohos.md) — Complete Coin3D Quarter HarmonyOS migration: cross-compiling libQuarter.so (ARM aarch64) + building the demo application (37 MB HAP) + 3D rendering verified. Key findings: OHOS Qt5 doesn't include the UiTools module, FindOpenGL needs customizing (OHOS uses GLES/EGL), CMAKE_FIND_ROOT_PATH_MODE ONLY needs absolute paths to work around, and hvigor needs DEVECO_SDK_HOME. Reusable: an OHOS cross-compilation CMake template + a FindOpenGL mapping pattern + a prebuilt-library integration pattern.
- [ohostemplate-blockedbymodal-patch](postmortems/ohostemplate-blockedbymodal-patch.md) — In ohostemplate, matplotlib's third-level window (Configure subplots -> Export values) can't be closed. Root cause: a parentless QDialog is classified as a SubWindow through the syntheticParent fallback, but the OHOS QPA never calls setTransientParent() to write that back to the Qt layer, so blockedByModalWindow=1 blocks close(). Qt source fix: showImmediate() writes the transientParent back after the fallback (about 8 lines in qohosview.cpp); device logs confirm blockedByModalWindow=0 and close()=1. Also found and fixed the ArkTS template version mismatch crash (modules -> modulesFactories).
- [quit-deadlock-tsfn](postmortems/quit-deadlock-tsfn.md) — Exit deadlock retrospective: <STAKEHOLDER> (<PRODUCT>) hangs for ~2 minutes after qApp->quit(). Root cause: HarmonyOS doesn't process N-API ThreadSafeFunction callbacks during the Ability destruction phase, so qWindowDestroyPromise's resolve callback is never executed and the Promise never resolves. Fix: an external patch bypasses the TSFN mechanism using an atomic variable + parallel polling; verified effective. Related confirmation: the sensor plugin triggers a crash during the exit flow, and a partner confirmed that removing it avoids the issue (2026-07-13).
- [saribbon-ohos](postmortems/saribbon-ohos.md) — Complete SARibbon v2.5.5 HarmonyOS migration: standalone build files + building the MainWindowExample application (48 MB HAP) + two build fixes (QDesktopWidget::screen type mismatch + incompatible lazy import syntax). Key findings: the QDesktopWidget API inside the SARibbon source returns QWidget* rather than QScreen* under Qt 5.12 OHOS, the template's lazy import syntax requires API 12 beta3, and the project needs its own CMakeLists.txt to avoid modifying the source. Reusable: the standalone-build-file pattern for keeping third-party Qt library sources intact during HarmonyOS porting.
- [toolwindow-crossscreen-flicker](postmortems/toolwindow-crossscreen-flicker.md) — Analysis of the ToolWindow cross-screen flicker system issue: moveWindowToGlobalDisplay conflicts with resizeAsync during cross-screen dragging, and screenIdChanged only fires when the drag ends. Qt traced the full call chain to the root cause and attributed it to the HarmonyOS system interface.
- [wa-nativewindow-leave-bug](postmortems/wa-nativewindow-leave-bug.md) — Complete analysis of the WA_NativeWindow Leave event insensitivity bug: the dual-blind-spot root cause (the Qt Widget layer skips internalWinId() + the OHOS QPA hover callback is unreliable), full call-chain tracing, fix strategy assessment (three options compared), a 10-scenario risk matrix, and sequence diagrams. Qt 5.12 OHOS. ✅ Manually verified; deliverables were output to <WORK_DIR>/leave-event-fix/ (final cleanup 2026-06-09).
