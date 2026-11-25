---
updated: 2026-11-02
counts:
  symptoms: 17
  causes: 18
  workarounds: 15
  tickets: 11
description: >
  The fault registry (human view of the symptom x cause x workaround x ticket graph).
  [GENERATED, DO NOT EDIT BY HAND -- rebuild with python tools/faults-build.py build]
  The machine-readable full graph is _graph.yaml; the spec is _index.md.
---

# Fault registry

> Look things up by behavior in §Symptom index (the main entry); for "who owns it, defect or limitation, fixed or not, how to work around it", see the causes.
> Machine-readable full graph (one file, one load): [_graph.yaml](_graph.yaml) | spec: [_index](_index.md)
> **This file is a derived artifact**: the source of truth is `_data/*.yaml` and `C-*.md`; after editing them run `python tools/faults-build.py build`.

## Statistics

| Dimension | Distribution |
|------|------|
| Nodes | symptoms 17 (active 4 / mitigated 12 / resolved 1) / causes 18 (defect 11 / undetermined 3 / limitation 4) / workarounds 15 / tickets 11 |
| Responsibility | app 2 · ohos-ndk 1 · ohos-runtime 6 · ohos-toolchain 1 · qt-port 6 · third-party 1 · undetermined 1 |
| Disposition | Must adapt for HarmonyOS 4 · Qt issue 6 · System issue 2 · Application usage issue 2 · Third-party library issue 1 · Pending classification 3 |
| Chain closure | root-fixed 1 · temporarily resolved 6 · not closed 11 (Missing ticket 7 · Missing workaround 2 · Both missing 2) |
| Severity | blocker 1 · critical 3 · high 6 · medium 7 · low 1 |

## Symptom index (main entry)

| S | Symptom | Domain | Severity | Status | Closure | Cause (nature) | Mitigation (W) |
|---|------|----|:------:|------|------|---------------|----------|
| S-0001 | QML platform guard silently fails (Qt.platform.os returns \"linux\" instead of \… | api | 🟠 high | mitigated | missing ticket | [C-0001](C-0001-qqmlplatform-os-ohos-branch.md) (defect) | W-0001 |
| S-0002 | Pinyin composition input breaks: the keyboard closes mid-input + pinyin letters … | input | 🟠 high | mitigated | missing ticket | [C-0002](C-0002-ime-reset-detach.md) (defect) | W-0002 |
| S-0003 | First character occasionally lost after switching focus between input fields | input | 🟡 medium | **active** | both missing | [C-0003](C-0003-ime-focus-switch-race.md) (defect) | — |
| S-0004 | App hangs for about 2 minutes after qApp->quit() (the Ability destroy Promise ne… | lifecycle | 🔴 critical | mitigated | — | [C-0004](C-0004-ability-destroy-tsfn.md) (undetermined) | W-0003 |
| S-0005 | Qt6 OHOS target build fails in a cascade (nullptr_t / __promote / hypot ambiguou… | build | ⬜ blocker | mitigated | missing ticket | [C-0005](C-0005-qt-cmake-isystem-injection.md) (defect) ×[C-0006](C-0006-libcxx-ohos-cmath-promote.md) (defect) (all_of) | W-0004; W-0004 |
| S-0006 | SURFACE-type XComponent native render surface is on the deprecation track (depre… | api | 🟡 medium | **active** | missing workaround | [C-0007](C-0007-xcomponent-surface-deprecated.md) (limitation) | — |
| S-0007 | chmod / symlink fails at runtime (QFile::setPermissions / QFile::link return fai… | filesystem | 🟡 medium | mitigated | — | [C-0008](C-0008-sandbox-chmod-symlink.md) (limitation) | W-0005; W-0006 |
| S-0008 | A QDialog without a parent cannot be closed and ignores the mouse wheel (blocked… | runtime | 🟠 high | mitigated | missing ticket | [C-0009](C-0009-qpa-syntheticparent-no-transientparent.md) (defect) | W-0007 |
| S-0009 | Qt5 HarmonyOS app crashes when onAcceptWant fires: Napi::Error global expression… | runtime | 🔴 critical | mitigated | missing ticket | [C-0010](C-0010-stale-template-ohos-bare-eval.md) (defect) | W-0008 |
| S-0010 | QWidget app Debug build crashes on mouse click: sendThroughApplicationEventFilte… | runtime | 🟠 high | **active** | missing workaround | [C-0011](C-0011-the-mainthread-mismatch.md) (undetermined) | — |
| S-0011 | Runtime dlopen of a .so from a writable path fails (errno=22 EINVAL / QPluginLoa… | runtime | 🟠 high | mitigated | — | [C-0012](C-0012-loader-rejects-writable-path.md) (limitation) | W-0010 |
| S-0012 | App crashes with SIGABRT a few seconds after startup (exit(1); the stack points … | runtime | 🔴 critical | mitigated | — | [C-0013](C-0013-sandbox-readonly-bundle-path.md) (limitation) | W-0011 |
| S-0013 | Qt::Tool child windows flicker when dragging the MainWindow across screens in a … | render | 🟡 medium | **active** | both missing | [C-0014](C-0014-crossscreen-move-resize-conflict.md) (defect) | — |
| S-0014 | HAP packaged by the hvigor CLI (--mode module) crashes at startup (handleAbility… | deploy | 🟡 medium | mitigated | — | [C-0015](C-0015-hvigor-cli-ide-packaging-divergence.md) (undetermined) | W-0013 |
| S-0015 | Mistakenly adding a Q_OS_OHOS alternative branch for QFileDialog (the guard conf… | api | 🟢 low | resolved | — | [C-0016](C-0016-qfiledialog-unnecessary-ohos-ifdef.md) (defect) | — |
| S-0016 | curl request body Chinese text garbled under Windows Git Bash (API returns 200/2… | toolchain | 🟡 medium | mitigated | — | [C-0017](C-0017-curl-gbk-terminal-mojibake.md) (defect) | W-0014 |
| S-0017 | Qt3D entities textured with alpha PNGs (RGBA8) render solid black (lighting OK, … | render | 🟠 high | mitigated | missing ticket | [C-0018](C-0018-zink-rgba8-mipmap-black.md) (defect) | W-0015 |

## By disposition (developer's view: what to do when you hit it)

> Derived view (computed automatically from nature × responsible; spec in _index §3): **Must adapt for HarmonyOS** = this is how the platform/SDK is specified; change your own code, there is no upstream fix to wait for; **Qt issue** = wait for a Qt fix / local patch / file a QTBUG; **System issue** = wait for a system/SDK/toolchain release or file a ticket with Huawei; **Application usage issue** = change the application code, not a framework problem; **Third-party library issue** = a defect in the third-party library itself; **Pending classification** = wait for upstream to classify it.

### Must adapt for HarmonyOS (must-adapt, 4)

| CID | Cause | nature/responsible | Status | Workaround (W) / route |
|-----|------|--------------------|------|---------------|
| [C-0007](C-0007-xcomponent-surface-deprecated.md) | ARKUI_XCOMPONENT_TYPE_SURFACE is deprecated in API 20; the m… | limitation/ohos-runtime | watching | ContentSlot (the official direction): watch capability cover… |
| [C-0008](C-0008-sandbox-chmod-symlink.md) | The application sandbox forbids runtime chmod/symlink (file … | limitation/ohos-runtime | wontfix | W-0005; W-0006 |
| [C-0012](C-0012-loader-rejects-writable-path.md) | The application loader refuses to load dynamic libraries fro… | limitation/ohos-runtime | wontfix | W-0010 |
| [C-0013](C-0013-sandbox-readonly-bundle-path.md) | The OHOS sandbox bundle install path is read-only, so deskto… | limitation/ohos-runtime | wontfix | W-0011 |

### Qt issue (qt-defect, 6)

| CID | Cause | nature/responsible | Status | Workaround (W) / route |
|-----|------|--------------------|------|---------------|
| [C-0001](C-0001-qqmlplatform-os-ohos-branch.md) | The #ifdef chain in qqmlplatform os() lacks a Q_OS_OHOS bran… | defect/qt-port | workaround | W-0001 |
| [C-0002](C-0002-ime-reset-detach.md) | QOhosInputContext::reset() Detach/Attach closes the IMF pane… | defect/qt-port | workaround | W-0002 |
| [C-0003](C-0003-ime-focus-switch-race.md) | Detach→Attach race at the moment of an IME focus switch comm… | defect/qt-port | open | Same component as C-0002; submit together with its fix (chec… |
| [C-0005](C-0005-qt-cmake-isystem-injection.md) | Qt cmake injects -isystem sysroot/usr/include into every CXX… | defect/qt-port | workaround | W-0004 |
| [C-0009](C-0009-qpa-syntheticparent-no-transientparent.md) | The OHOS QPA syntheticParent fallback doesn't write back tra… | defect/qt-port | workaround | W-0007 |
| [C-0010](C-0010-stale-template-ohos-bare-eval.md) | The stale glue template lacks @ohos.* eager import registrat… | defect/qt-port | workaround | W-0008 |

### System issue (system-defect, 2)

| CID | Cause | nature/responsible | Status | Workaround (W) / route |
|-----|------|--------------------|------|---------------|
| [C-0006](C-0006-libcxx-ohos-cmath-promote.md) | libcxx-ohos <cmath> uses __promote but lacks #include <__mat… | defect/ohos-ndk | diagnosed | W-0004 |
| [C-0014](C-0014-crossscreen-move-resize-conflict.md) | The ohos window APIs moveWindowToGlobalDisplay × resizeAsync… | defect/ohos-runtime | diagnosed | W-0012 |

### Application usage issue (app-usage, 2)

| CID | Cause | nature/responsible | Status | Workaround (W) / route |
|-----|------|--------------------|------|---------------|
| [C-0016](C-0016-qfiledialog-unnecessary-ohos-ifdef.md) | The app wrongly assumes QFileDialog has no native OHOS suppo… | defect/app | closed | Change the usage: use the standard QFileDialog API directly … |
| [C-0017](C-0017-curl-gbk-terminal-mojibake.md) | Inlining Chinese into curl -d in a non-UTF-8 terminal (Windo… | defect/app | workaround | W-0014 |

### Third-party library issue (third-party, 1)

| CID | Cause | nature/responsible | Status | Workaround (W) / route |
|-----|------|--------------------|------|---------------|
| [C-0018](C-0018-zink-rgba8-mipmap-black.md) | Mesa ZINK implements glGenerateMipmap via vkCmdBlitImage, wh… | defect/third-party | workaround | W-0015 |

### Pending classification (undetermined, 3)

| CID | Cause | nature/responsible | Status | Workaround (W) / route |
|-----|------|--------------------|------|---------------|
| [C-0004](C-0004-ability-destroy-tsfn.md) | The Ability destroy window doesn't process N-API TSFN callba… | undetermined/ohos-runtime | reported | W-0003 |
| [C-0011](C-0011-the-mainthread-mismatch.md) | theMainThread and QCoreApplication::instance()->thread() poi… | undetermined/undetermined | diagnosed | W-0009 |
| [C-0015](C-0015-hvigor-cli-ide-packaging-divergence.md) | hvigor CLI (--mode module) packaging is not equivalent to De… | undetermined/ohos-toolchain | diagnosed | W-0013 |

## Not closed (chain completeness gaps -- to be filled; rules in _index §4)

> Closed-loop rule: **defect (external responsibility) temporarily resolved = an adopted workaround (W adopted) + a tracked ticket (T)**; limitation / application issue / unclassified = an adopted workaround; root-fixed = fix-confirmed and later. **Gaps propagate upward**: a symptom's claim of resolution is bounded by the completeness of its cause chain (enforced by check).

### Missing ticket (workaround in place; ticket to be filed/tracked) (7)

| CID | Cause | Disposition | Status | Workaround (W) | Ticket (T) | Symptoms |
|-----|------|------|------|-----------|---------|------|
| [C-0001](C-0001-qqmlplatform-os-ohos-branch.md) | The #ifdef chain in qqmlplatform os() lacks a Q_OS_O… | Qt issue | workaround | W-0001 | T-0008 (planned) | S-0001 |
| [C-0002](C-0002-ime-reset-detach.md) | QOhosInputContext::reset() Detach/Attach closes the … | Qt issue | workaround | W-0002 | T-0009 (planned) | S-0002 |
| [C-0005](C-0005-qt-cmake-isystem-injection.md) | Qt cmake injects -isystem sysroot/usr/include into e… | Qt issue | workaround | W-0004 | T-0010 (planned) | S-0005 |
| [C-0006](C-0006-libcxx-ohos-cmath-promote.md) | libcxx-ohos <cmath> uses __promote but lacks #includ… | System issue | diagnosed | W-0004 | ✗ | S-0005 |
| [C-0009](C-0009-qpa-syntheticparent-no-transientparent.md) | The OHOS QPA syntheticParent fallback doesn't write … | Qt issue | workaround | W-0007 | T-0011 (planned) | S-0008 |
| [C-0010](C-0010-stale-template-ohos-bare-eval.md) | The stale glue template lacks @ohos.* eager import r… | Qt issue | workaround | W-0008 | T-0012 (planned) | S-0009 |
| [C-0018](C-0018-zink-rgba8-mipmap-black.md) | Mesa ZINK implements glGenerateMipmap via vkCmdBlitI… | Third-party library issue | workaround | W-0015 | T-0013 (planned) | S-0017 |

### Missing workaround (no adopted workaround/adaptation) (2)

| CID | Cause | Disposition | Status | Workaround (W) | Ticket (T) | Symptoms |
|-----|------|------|------|-----------|---------|------|
| [C-0007](C-0007-xcomponent-surface-deprecated.md) | ARKUI_XCOMPONENT_TYPE_SURFACE is deprecated in API 2… | Must adapt for HarmonyOS | watching | ✗ | T-0002 | S-0006 |
| [C-0011](C-0011-the-mainthread-mismatch.md) | theMainThread and QCoreApplication::instance()->thre… | Pending classification | diagnosed | ✗ | ✗ | S-0010 |

### Both missing (unresolved) (2)

| CID | Cause | Disposition | Status | Workaround (W) | Ticket (T) | Symptoms |
|-----|------|------|------|-----------|---------|------|
| [C-0003](C-0003-ime-focus-switch-race.md) | Detach→Attach race at the moment of an IME focus swi… | Qt issue | open | ✗ | ✗ | S-0003 |
| [C-0014](C-0014-crossscreen-move-resize-conflict.md) | The ohos window APIs moveWindowToGlobalDisplay × res… | System issue | diagnosed | ✗ | ✗ | S-0013 |

## Defects (defect -- will be fixed; track the fix version and upstream ticket)

| CID | Cause | Responsible | Severity | Status | Workaround (W) | Ticket (T) | Fix route | Review due |
|-----|------|------|:------:|------|--------------|------------|-------------|---------|
| [C-0001](C-0001-qqmlplatform-os-ohos-branch.md) | The #ifdef chain in qqmlplatform os() lacks a Q_OS_OHOS branch | qt-port | 🟠 high | workaround | W-0001 | T-0008 | Add the branch in upstream qtdeclarative → cherry-pick to th… | 2026-12-14 |
| [C-0002](C-0002-ime-reset-detach.md) | QOhosInputContext::reset() Detach/Attach closes the IMF panel and co… | qt-port | 🟠 high | workaround | W-0002 | T-0009 | Align with the Android plugin's behavior (reset only finaliz… | 2026-12-14 |
| [C-0003](C-0003-ime-focus-switch-race.md) | Detach→Attach race at the moment of an IME focus switch commits the … | qt-port | 🟡 medium | open | — | — | Same component as C-0002; submit together with its fix (chec… | 2026-12-14 |
| [C-0005](C-0005-qt-cmake-isystem-injection.md) | Qt cmake injects -isystem sysroot/usr/include into every CXX command… | qt-port | ⬜ blocker | workaround | W-0004 | T-0010 | Locate and remove Qt's SYSTEM include injection of sysroot/u… | 2026-10-15 |
| [C-0006](C-0006-libcxx-ohos-cmath-promote.md) | libcxx-ohos <cmath> uses __promote but lacks #include <__math/promot… | ohos-ndk | 🟡 medium | diagnosed | W-0004 | — | SDK/NDK adds #include <__math/promote.h> to libcxx-ohos <cma… | 2026-10-15 |
| [C-0009](C-0009-qpa-syntheticparent-no-transientparent.md) | The OHOS QPA syntheticParent fallback doesn't write back transientPa… | qt-port | 🟠 high | workaround | W-0007 | T-0011 | Upstream merges the qohosview.cpp patch in which showImmedia… | 2026-12-15 |
| [C-0010](C-0010-stale-template-ohos-bare-eval.md) | The stale glue template lacks @ohos.* eager import registration, so … | qt-port | 🔴 critical | workaround | W-0008 | T-0012 | On the Qt side, update the template in the same batch as lib… | 2026-12-15 |
| [C-0014](C-0014-crossscreen-move-resize-conflict.md) | The ohos window APIs moveWindowToGlobalDisplay × resizeAsync have no… | ohos-runtime | 🟡 medium | diagnosed | W-0012 | — | The system side guarantees rendering atomicity of move+resiz… | 2026-12-15 |
| [C-0016](C-0016-qfiledialog-unnecessary-ohos-ifdef.md) | The app wrongly assumes QFileDialog has no native OHOS support and a… | app | 🟢 low | closed | — | — | Change the usage: use the standard QFileDialog API directly … | 2026-12-15 |
| [C-0017](C-0017-curl-gbk-terminal-mojibake.md) | Inlining Chinese into curl -d in a non-UTF-8 terminal (Windows Git B… | app | 🟡 medium | workaround | W-0014 | — | Change the usage: write the Chinese JSON to a UTF-8 temporar… | 2026-12-15 |
| [C-0018](C-0018-zink-rgba8-mipmap-black.md) | Mesa ZINK implements glGenerateMipmap via vkCmdBlitImage, which fail… | third-party | 🟠 high | workaround | W-0015 | T-0013 | Wait for Mesa/ZINK to fix RGBA8 mipmap generation and for th… | 2026-12-15 |

**Undetermined (undetermined -- awaiting classification, track the upstream reply; the CID stays the same if reclassified)**

| CID | Cause | Responsible | Severity | Status | Workaround (W) | Ticket (T) | Classification outcome | Review due |
|-----|------|------|:------:|------|--------------|------------|---------|---------|
| [C-0004](C-0004-ability-destroy-tsfn.md) | The Ability destroy window doesn't process N-API TSFN callbacks (the… | ohos-runtime | 🔴 critical | reported | W-0003 | T-0001 | see the C page | 2026-12-14 |
| [C-0011](C-0011-the-mainthread-mismatch.md) | theMainThread and QCoreApplication::instance()->thread() point to di… | undetermined | 🟠 high | diagnosed | W-0009 | — | see the C page | 2026-12-15 |
| [C-0015](C-0015-hvigor-cli-ide-packaging-divergence.md) | hvigor CLI (--mode module) packaging is not equivalent to DevEco IDE… | ohos-toolchain | 🟡 medium | diagnosed | W-0013 | — | see the C page | 2026-12-15 |

## Limitations (limitation -- this is how the platform works; track alternatives and evolution)

| CID | Limitation | Classification evidence | Alternative (W) | Evolution | Status |
|-----|------|---------|--------------|------|------|
| [C-0007](C-0007-xcomponent-surface-deprecated.md) | ARKUI_XCOMPONENT_TYPE_SURFACE is deprecated in API 20; the migration… | Huawei's official deprecation notice (since API 20) + the Co… | — | ContentSlot (the official direction): watch capability c… | watching |
| [C-0008](C-0008-sandbox-chmod-symlink.md) | The application sandbox forbids runtime chmod/symlink (file permissi… | Application sandbox specification: file permissions and link… | W-0005; W-0006 | — (the specification is stable, no evolution direction; … | wontfix |
| [C-0012](C-0012-loader-rejects-writable-path.md) | The application loader refuses to load dynamic libraries from writab… | Loader security specification: dynamic libraries can only be… | W-0010 | — (the specification is stable, no evolution direction; … | wontfix |
| [C-0013](C-0013-sandbox-readonly-bundle-path.md) | The OHOS sandbox bundle install path is read-only, so desktop-style … | Application sandbox specification: the bundle install direct… | W-0011 | — (the specification is stable: a read-only bundle is pa… | wontfix |

## Workarounds (W)

| W | Workaround | Targets | Status | Last verified | Retire when |
|---|------|---------|------|---------|---------|
| W-0001 | In QML, detect the platform with Qt.platform.pluginName (in C++, productType()/#ifde… | C-0001 | adopted | 2026-08-06 Qt 5.15.16 (962aa625) source verification | Once the upstream fix (a Q_OS_OHOS branch in os()) lands in … |
| W-0002 | Rebuild libqohos.so (reset only finalizes the preedit, no detach) and replace it in … | C-0002 | adopted | 2026-09-12 Qt 6.12-beta3 / HarmonyOS PC (MateBook Pro) r… | Once an upstream release contains this fix, go back to the o… |
| W-0003 | Exit patch: atomic s_qtAppThreadIdle + polling from a separate thread in parallel, b… | C-0004 | adopted | 2026-06-09 Qt 5.12.12 / real device | Once the HarmonyOS version in use is confirmed to handle the… |
| W-0004 | Switch the build combination: MinGW g++ 13.1.0 host + API 23 SDK + superbuild path | C-0005; C-0006 | adopted | 2026-07-13 Qt 6.12.0 full build + gallery demo on a real… | Once Qt drops the -isystem injection or the SDK fixes C-0006… |
| W-0005 | Expand real files at build/packaging time (instead of runtime symlinks) | C-0008 | adopted | — | Not expected to retire (wontfix: the sandbox specification i… |
| W-0006 | Hand permission requirements to the platform packaging contract; don't make them a r… | C-0008 | adopted | — | Not expected to retire (wontfix: the sandbox specification i… |
| W-0007 | Rebuild libqohos.so with the transientParent write-back patch (about 8 lines in show… | C-0009 | adopted | 2026-08-06 Qt 5.15.16 / OHOS real device (ohostemplate, … | Once the upstream harmonyos branch merges the transientParen… |
| W-0008 | Replace the 4 glue files with the designated complete reference template (26+13 eage… | C-0010 | adopted | 2026-07-23 Qt 5.15.16 (515-generation libqohos 7/17) / H… | Once the Qt source-tree template is updated in the same batc… |
| W-0009 | main() constraint: QApplication must be the first Qt API call (don't touch QThreadDa… | C-0011 | proposed | — | Once the root cause is confirmed and permanently fixed (or c… |
| W-0010 | Ship plugin .so files in the HAP lib directory (or statically link a fixed set); no … | C-0012 | adopted | — | Not expected to retire (wontfix: the loader specification is… |
| W-0011 | Add a Q_OS_OHOS branch for path lookup: QStandardPaths::writableLocation(AppDataLoca… | C-0013 | adopted | 2026-07-09 Qt 5.15.16 / HarmonyOS 6.0 / HUAWEI MateBook … | Not expected to retire (wontfix: the read-only bundle specif… |
| W-0012 | Remove the redundant resize: don't trigger resizeAsync when the size hasn't changed,… | C-0014 | proposed | 2026-06-05 HUAWEI MateBook Fold dual-screen real device … | Once the system guarantees atomic rendering of cross-screen … |
| W-0013 | Drop hvigor CLI packaging and deploy with DevEco Studio IDE Run instead | C-0015 | adopted | 2026-08-06 OHOS + Qt 5.15.16 + DevEco Studio IDE Run (pe… | Once the hvigor CLI packaging difference is identified and f… |
| W-0014 | Write Chinese JSON to a UTF-8 temporary file and reference it with curl -d @file | C-0017 | adopted | 2026-06-10 Windows 10/11 + Git Bash (MSYS2) + curl 7.x/8… | Once the terminal environment reliably guarantees UTF-8 (chc… |
| W-0015 | On OHOS, disable mipmaps for alpha-PNG (RGBA8) entities (generateMipMaps:false + min… | C-0018 | adopted | 2026-07-14 Qt 5.12.12 OHOS SDK / HUAWEI MateBook Fold re… | Once Mesa ZINK fixes RGBA8 glGenerateMipmap (the vkCmdBlitIm… |

## Tickets (T)

| T | Tracker | Number | Tracks | Status | Fix version | Filed | Notes |
|---|------|------|---------|------|---------|--------|------|
| T-0001 | partner | — | C-0004 | submitted | — | 2026-06-09 | Deliverable: ISSUE.md (root cause in Chinese and English) + patc… |
| T-0002 | qt-bug | [QTBUG-146622](https://bugreports.qt.io/browse/QTBUG-146622) | C-0007 | submitted | — | — | Qt-side tracking of the XComponent SURFACE → ContentSlot migrati… |
| T-0003 | qt-bug | [QTBUG-146619](https://bugreports.qt.io/browse/QTBUG-146619) | C-0008 | submitted | — | — | Records the QFile::setPermissions platform behavior (registered … |
| T-0004 | qt-bug | [QTBUG-146621](https://bugreports.qt.io/browse/QTBUG-146621) | C-0008 | submitted | — | — | Records the QFile::link platform behavior (registered on the Qt … |
| T-0007 | qt-bug | [QTBUG-146624](https://bugreports.qt.io/browse/QTBUG-146624) | C-0012 | submitted | — | — | Qt-side record of platform behavior: the QPluginLoader/runtime .… |
| T-0008 | qt-bug | — | C-0001 | draft | — | — | qqmlplatform os() #ifdef chain lacks a Q_OS_OHOS branch; current… |
| T-0009 | qt-bug | — | C-0002 | draft | — | — | QOhosInputContext::reset() Detach/Attach closes the IMF panel an… |
| T-0010 | qt-bug | — | C-0005 | draft | — | — | Qt cmake injects -isystem sysroot/usr/include into every CXX com… |
| T-0011 | qt-bug | — | C-0009 | draft | — | — | OHOS QPA syntheticParent doesn't write back transientParent, so … |
| T-0012 | qt-bug | — | C-0010 | draft | — | — | The stale glue template lacks the @ohos.* eager imports, so libq… |
| T-0013 | upstream | — | C-0018 | draft | — | — | Mesa ZINK implements glGenerateMipmap via vkCmdBlitImage, which … |

## Relationship overview

```
S-0001 QML platform guard silently …   ──→ C-0001 The #ifdef chain in qqmlplatform os(… [defect/qt-port]
S-0002 Pinyin composition input bre…   ──→ C-0002 QOhosInputContext::reset() Detach/At… [defect/qt-port]
S-0003 First character occasionally…   ──→ C-0003 Detach→Attach race at the moment of … [defect/qt-port]
S-0004 App hangs for about 2 minute…   ──→ C-0004 The Ability destroy window doesn't p… [undetermined/ohos-runtime]
S-0005 Qt6 OHOS target build fails …   ──┬→ C-0005 Qt cmake injects -isystem sysroot/us… [defect/qt-port]  ← all_of (combined)
                                           └→ C-0006 libcxx-ohos <cmath> uses __promote b… [defect/ohos-ndk]
S-0006 SURFACE-type XComponent nati…   ──→ C-0007 ARKUI_XCOMPONENT_TYPE_SURFACE is dep… [limitation/ohos-runtime]
S-0007 chmod / symlink fails at run…   ──→ C-0008 The application sandbox forbids runt… [limitation/ohos-runtime]
S-0008 A QDialog without a parent c…   ──→ C-0009 The OHOS QPA syntheticParent fallbac… [defect/qt-port]
S-0009 Qt5 HarmonyOS app crashes wh…   ──→ C-0010 The stale glue template lacks @ohos.… [defect/qt-port]
S-0010 QWidget app Debug build cras…   ──→ C-0011 theMainThread and QCoreApplication::… [undetermined/undetermined]
S-0011 Runtime dlopen of a .so from…   ──→ C-0012 The application loader refuses to lo… [limitation/ohos-runtime]
S-0012 App crashes with SIGABRT a f…   ──→ C-0013 The OHOS sandbox bundle install path… [limitation/ohos-runtime]
S-0013 Qt::Tool child windows flick…   ──→ C-0014 The ohos window APIs moveWindowToGlo… [defect/ohos-runtime]
S-0014 HAP packaged by the hvigor C…   ──→ C-0015 hvigor CLI (--mode module) packaging… [undetermined/ohos-toolchain]
S-0015 Mistakenly adding a Q_OS_OHO…   ──→ C-0016 The app wrongly assumes QFileDialog … [defect/app]
S-0016 curl request body Chinese te…   ──→ C-0017 Inlining Chinese into curl -d in a n… [defect/app]
S-0017 Qt3D entities textured with …   ──→ C-0018 Mesa ZINK implements glGenerateMipma… [defect/third-party]
C→C depends_on: none yet
Orphan symptoms (empty causes): none
```

## By version baseline (upgrade checklist)

Check here before switching Qt / OHOS versions: the causes still active on the target version + the workarounds that must be carried along (W ids).

### Qt 5.12.12

| Cause | Status | Carried (W) |
|------|------|------------|
| C-0001 | workaround | W-0001 |
| C-0004 | reported | W-0003 |
| C-0018 | workaround | W-0015 |

### Qt 5.15.16

| Cause | Status | Carried (W) |
|------|------|------------|
| C-0001 | workaround | W-0001 |
| C-0009 | workaround | W-0007 |
| C-0010 | workaround | W-0008 |
| C-0011 | diagnosed | W-0009 |
| C-0013 | wontfix | W-0011 |
| C-0015 | diagnosed | W-0013 |

### Qt 6.12

| Cause | Status | Carried (W) |
|------|------|------------|
| C-0001 | workaround | W-0001 |
| C-0002 | workaround | W-0002 |
| C-0003 | open | — |
| C-0005 | workaround | W-0004 |

### Other Qt versions

| Cause | Status | Affected versions | Carried (W) |
|------|------|---------|------------|
| C-0014 | diagnosed | not recorded (the source page only records collecting logs f… | W-0012 |

### OHOS API / system versions

| Cause | Affected versions | Carried (W) |
|------|-----------|------------|
| C-0001 | all versions (independent of system/API version) | W-0001 |
| C-0002 | HarmonyOS PC (MateBook Pro, physical keyboard + Huawei IME) | W-0002 |
| C-0003 | HarmonyOS PC (Huawei IME) | — |
| C-0004 | real device (system version not recorded) | W-0003 |
| C-0005 | API 22 (Release 6.0.2.130); API 24 Beta1 (DevEco 6.1.1.268) | W-0004 |
| C-0006 | API 22; API 24 Beta1 (libcxx-ohos) | W-0004 |
| C-0007 | API 20+ | — |
| C-0008 | all versions (sandbox specification) | W-0005; W-0006 |
| C-0009 | real device (system version not recorded) | W-0007 |
| C-0010 | HarmonyOS 6.0.0.29 (HUAWEI MateBook Fold HPR-W72 real device) | W-0008 |
| C-0011 | not recorded (partner-reported case; device/system version not kept) | W-0009 |
| C-0012 | all versions (loader specification; the source page records evidence on real dev… | W-0010 |
| C-0013 | HarmonyOS 6.0 (evidenced in the source page; a read-only bundle is an all-versio… | W-0011 |
| C-0014 | not recorded (evidenced on a HUAWEI MateBook Fold dual-screen real device; syste… | W-0012 |
| C-0015 | not recorded (hvigor CLI / DevEco Studio versions not recorded in the source pag… | W-0013 |
| C-0018 | real device HUAWEI MateBook Fold (NEED_OPENGL=1; API version not recorded) | W-0015 |

## Reviews due

| Due | CID | Status | Review focus |
|--------|-----|------|---------|
| 2026-10-15 | C-0005 | workaround | Whether the new OHOS SDK / Qt 6.12 still injects -isystem; whether libcxx-ohos cmath add… |
| 2026-10-15 | C-0006 | diagnosed | Whether libcxx-ohos <cmath> adds __math/promote.h (review together with C-0005) |
| 2026-12-14 | C-0001 | workaround | Whether the harmonyos branch / qtdeclarative already has a Q_OS_OHOS branch |
| 2026-12-14 | C-0002 | workaround | Whether the next Qt 6.12 OHOS kit includes the reset fix; verify the lost first characte… |
| 2026-12-14 | C-0003 | open | Verify together with C-0002 (next Qt 6.12 kit) |
| 2026-12-14 | C-0004 | reported | Reply from the partner/system side; TSFN behavior in the destroy window on new system ve… |
| 2026-12-14 | C-0007 | watching | ContentSlot capability coverage and the Qt-port migration pace (T-0002); the platform's … |
| 2026-12-14 | C-0008 | wontfix | Whether the sandbox specification has changed (reclassify if chmod/symlink become availa… |
| 2026-12-15 | C-0009 | workaround | Check whether the harmonyos-5.15.16 branch has merged the transientParent write-back; if… |
| 2026-12-15 | C-0010 | workaround | Check whether the harmonyos-5.15.16 template has switched to the complete OhosExportModu… |
| 2026-12-15 | C-0011 | diagnosed | The three hypotheses for the trigger path are unresolved (app calls Qt APIs before QAppl… |
| 2026-12-15 | C-0012 | wontfix | Whether the loader's writable-path restriction has loosened (reclassify if controlled ru… |
| 2026-12-15 | C-0013 | wontfix | Whether the read-only bundle specification has changed; whether the app's other write po… |
| 2026-12-15 | C-0014 | diagnosed | Calibrate severity (commercial Qt feedback, always reproduces on multi-screen); file a t… |
| 2026-12-15 | C-0015 | diagnosed | The specific mechanism of the CLI vs IDE difference is to be investigated (the NAPI modu… |
| 2026-12-15 | C-0017 | workaround | Thin C page (app usage issue): unrelated to Qt/HarmonyOS (a Windows development environm… |
| 2026-12-15 | C-0018 | workaround | No Mesa upstream ticket filed yet (no ticket number in this KB; ticket material = the pl… |

## Resolved (verified / closed)

| CID | Cause | Resolution | Fix/migration version |
|-----|------|---------|--------------|
| C-0016 | The app wrongly assumes QFileDialog has no native OHOS suppo… | closed | — |
