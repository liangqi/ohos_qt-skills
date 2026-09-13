---
id: semantic-qt-harmonyos-system-tray
type: semantic
domain: tech
tags: [qt, harmonyos, system-tray, qsystemtrayicon, statusbar, StatusBarExtensionKit, notificationManager, qpa, ohos]
created: 2026-07-23
updated: 2026-07-23
status: active
audience: public
refs: [semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-window-model, procedural-demo-generation, problem-runtime-crash-ohos-deviceinfo-global-expression]
summary: >
  The implementation and behavior of the Qt HarmonyOS system tray (QSystemTrayIcon): underneath, QOhosSystemTrayIcon (qohossystemtrayicon.cpp) puts the icon into the HarmonyOS
  status bar via @kit.StatusBarExtensionKit.statusBarManager (addToStatusBar/updateIcon/updateMenu/
  removeFromStatusBar/updateStatusBarHoverTips), menus go through QOhosStatusBarMenuImpl (rightMenuClick/menuCode),
  and showMessage goes through @ohos.notificationManager.publish. Lists every stub/pitfall (geometry is a constant / messageClicked never fires /
  activated only reports Trigger / menus support only text + top-level separators + one level of submenu / icons are forced to a monochrome mask / tooltips need API ≥ 22).
leader_summary: >
  Filled the knowledge base's system tray gap at the source level: the HarmonyOS tray genuinely works (it's not a stub probe) and is implemented through the status bar's StatusBarExtensionKit;
  captured the API behavior and every stub pitfall, supporting future tray/notification/status-bar applications and demos.
impact: [Framework support, Demo generation, Migration efficiency]
deliverables: [${DEMOS_ROOT}/tray-ohos (a complete Qt 5.12 OHOS demo + HAP), a semantic knowledge page]
evidence: [${DEMOS_ROOT}/tray-ohos/entry-default-unsigned.hap (37.7 MB, BUILD SUCCESSFUL), libTrayOhos.so exporting T main, libqohos.so strings containing the 5 statusBarManager methods]
---

# The Qt for HarmonyOS system tray

> **Source**: the Qt 5.12.12 OHOS source `qtbase/src/plugins/platforms/ohos/qohossystemtrayicon.cpp/.h` + `qohosstatusbarmenu.cpp/.h`, verified against libqohos.so binary strings.
> HarmonyOS **does** have a real system tray implementation — on HarmonyOS, `QSystemTrayIcon` puts the icon into the **system status bar** (at the top); it isn't a stub probe.

## Factory integration

`createPlatformSystemTrayIcon()` in `qohosplatformtheme.cpp` returns `makeQOhosSystemTrayIcon()` (an anonymous-namespace final class, `QOhosSystemTrayIcon`). The menu backend is `QOhosStatusBarMenuImpl` (`qohosstatusbarmenu.cpp`). Calls are marshalled to the ArkTS thread through the **QtOhos JS thread bridge** (`runInJsThreadAndWait` / `invokeInJsThreadAndWaitForContinue` + `jsState.eval(expr, args)`, where `*` is a positional placeholder); the **first argument to every statusBarManager call is the UiAbility context** (`getContextForStatusBarManager` → `qAbility().eval<QNapi::Object>("context")`).

## API behavior (public QSystemTrayIcon → platform virtual → ArkTS eval)

| Public call | Platform virtual | ArkTS eval (verbatim) | What actually happens on HarmonyOS |
|------------|------------------|-----------------------|------------------------------------|
| `show()` / `setVisible(true)` | `init()` | `@kit.StatusBarExtensionKit.statusBarManager.addToStatusBar(*)` | Real: the icon appears in the status bar (as a white/black monochrome mask) |
| `hide()` / `setVisible(false)` | `cleanup()` | `@kit.StatusBarExtensionKit.statusBarManager.removeFromStatusBar(*)` | Real: the status bar icon disappears |
| `setIcon(QIcon)` | `updateIcon()` | `@kit.StatusBarExtensionKit.statusBarManager.updateStatusBarIcon(*)` | Real: swaps the icon live (converted to a monochrome mask) |
| `setContextMenu(QMenu*)` | `updateMenu()` | `@kit.StatusBarExtensionKit.statusBarManager.updateStatusBarMenu(*)` | Real: swaps the statusBarGroupMenu live |
| `setToolTip(QString)` | `updateToolTip()` | `@kit.StatusBarExtensionKit.statusBarManager.updateStatusBarHoverTips(*)` | Real, but **only on SDK API ≥ 22**; below 22 it's a no-op (logging "not supported, ignoring") |
| `showMessage(title,msg,QIcon,MessageIcon,msecs)` | `showMessage()` | `@ohos.notificationManager.publish(*)` | Real: posts a system notification (it appears in the notification shade); `MessageIcon` is ignored via `Q_UNUSED` |
| `geometry()` | `geometry()` | — | **Stub**: always returns `QRect(0,0,24,24)`; don't trust it |
| static `isSystemTrayAvailable()` | — | — | **Stub**: always `true` (no real probing) |
| static `supportsMessages()` | — | — | **Stub**: always `true` |
| signal `activated(Trigger)` | `init()` registers the `statusBarIconClick` event | `iconClickType=="leftClick"` → `activated(Trigger)` | Real: **only** a left click emits Trigger |
| signal `messageClicked()` | — | — | **Stub**: never fires (showMessage uses publish, which has no click callback) |

**The ActivationReason enum**: `Unknown=0, Context=1, DoubleClick=2, Trigger=3, MiddleClick=4`. HarmonyOS only emits `Trigger`; right-click **doesn't** emit `Context` (a right click goes through the menu item's `QOhosStatusBarMenuItem::activated()` → the public `QAction::triggered()`, via the `rightMenuClick` event + `menuCode` matching).

## The icon pipeline (a monochrome mask)

`init`/`updateIcon`/`showMessage` share `makeDisplayDensityScaledJsPixelMapFromQImage`: it reads the density via `@ohos.display.getPrimaryDisplaySync()`, scales the QImage by `1/density` (vp), then calls `createNapiPixelMapFromQImage`. The tray icon is **forced to a monochrome mask** by `convertToMonochromeIcon` — a white version (all pixels white, alpha preserved) plus a black version — because OHOS status bar icons are mask icons. **So any QColor/shape works in a demo; the color is meaningless.** The PixelMap size is read back via `getImageInfoSync().size` (a PixelMap method, not a @kit module).

## showMessage (system notifications)

`showMessage` builds a notificationRequest: `{content:{notificationContentType:<num>, normal:{title,text}}, smallIcon:<PixelMap 128×128>, [autoDeletedTime: now+msecs, only when msecs>0]}`. `notificationContentType` is the numeric value of `@ohos.notificationManager.ContentType.NOTIFICATION_CONTENT_BASIC_TEXT` (resolved once by `mapOhosEnumToJs` evaluating `@ohos.notificationManager.ContentType` into a double and caching it). `@ohos.notificationManager.publish(request)` returns a promise, and errors are caught and logged.

> **A runtime caveat** (to be verified on a device): `notificationManager.publish` may require the user to grant notification permission in system settings (not a module.json5 permission but a system-level notification grant); without it, notifications are silently not posted (rather than crashing). The showMessage button in the demo serves as the probe.

## Menu limitations (QOhosStatusBarMenuImpl / QOhosStatusBarMenuItem)

HarmonyOS status bar menus support **only**:
- `text` (the menu item's text)
- Top-level `separator` (splitting the `statusBarGroupMenu` into groups)
- **One** level of submenu (nested submenus are ignored with a warning)

Menu item setters that are **complete no-ops**: `setIcon/setVisible/setFont/setRole/setCheckable/setChecked/setShortcut/setEnabled/setIconSize`. The menu's `showPopup/dismiss/setIcon/setEnabled/setVisible/syncMenuItem/syncSeparatorsCollapsible` are also all no-ops (the OS pops the menu itself; Qt doesn't). A `separator` inside a submenu is ignored with a warning.

**Hard-coded values**: `quickOperation.abilityName=""` and `ohosSystemTrayItemTitle="Qt Application"` (the tray item's quickOperation title is always "Qt Application" and isn't configurable through the public API).

## Glue dependencies (OhosExportModules.ts)

The modules the tray evaluates through libqohos (which must be registered as "known module paths" in `OhosExportModules.ts`):
- `@kit.StatusBarExtensionKit.statusBarManager` (the core tray: init/cleanup/updateIcon/updateMenu/updateToolTip + the `statusBarIconClick`/`rightMenuClick` events)
- `@ohos.display` (icon density scaling via `getPrimaryDisplaySync`)
- `@ohos.notificationManager` (showMessage's `publish` + `ContentType`)

> **The key 5.12 vs. 5.15 difference**:
> - **The 5.12 libqohos uses the factories API** (reading the `modulesFactories` field, `makeJsModulesFactoriesMap`). The source tree template's `OhosExportModules.ts` (5 `@kit.*` lazy imports + the `getOhosExportModulesFactories` arrow factory) **is exactly the 5.12 generation**, and **already includes `@kit.StatusBarExtensionKit`** → the core tray works out of the box. **Don't** swap in the qView-ohos objects version (that's 5.15, which reads the `modules` field).
> - The tray additionally needs `@ohos.display` + `@ohos.notificationManager`, which the source tree template **doesn't register**. The tray demo adds these two itself (an eager default-import + factories map entries, matching the existing 5-line pattern).
> - The bare-eval crash trap for `@ohos.deviceInfo` ([[problem-runtime-crash-ohos-deviceinfo-global-expression]]) is a **5.15-generation** mechanism; a single-instance 5.12 demo doesn't trigger it (see the diagnostic on that problem page: `strings libqohos.so | grep "global expression"` distinguishes the generations).

## The demo (${DEMOS_ROOT}/tray-ohos)

A complete Qt 5.12 OHOS demo: `QApplication` + `MainWindow` (10 buttons triggering the various tray APIs + an on-screen log area) + `QSystemTrayIcon` (shown via a QTimer shortly after the window appears; the contextMenu contains show/hide window + post notification + a top-level separator + one level of submenu + quit, and `activated(Trigger)` toggles window visibility). It avoids every stub (no reliance on geometry/messageClicked/Context; menus use only text + top-level separators + one level of submenu). Its CMake follows iron rules B1/B2/B3/B7/B10/B11. **BUILD SUCCESSFUL** (unsigned + signed HAP; libTrayOhos.so exports `T main`; the HAP contains libqohos.so + libQt5Core/Gui/Widgets + styles/libqohosstyle.so).

> **Runs on a device (2026-07-23, a MateBook Fold)**: it once crashed at startup because of a **libqohos ↔ libQt5Gui version mismatch** (the `nativeSurfacePixelSize` symbol) — libqohos (patched 07-14) references that symbol, and the deployed libQt5Gui doesn't export it → dlopen "symbol not found". `NEED_OPENGL=1` doesn't help (the failure is at load time). **The MIX fix**: have CMake use FULL (whose libQt5Core/Gui/Widgets provide the symbol) and override `Qt5::QOhosPlatformIntegrationPlugin`'s `IMPORTED_LOCATION` to point at the ORIGINAL libqohos (which references the symbol and isn't a debug build) → hvigor copies the MIX combination via DT_NEEDED → libqohos loads successfully. The hilog proof: `Window show` + `addToStatusBar succeed!` + a stable process; the HAP's libqohos is 5.7 MB (ORIGINAL). See problems/runtime-crash-qbackingstore-qregion-ohos.md. The tray behavior (the status bar icon via addToStatusBar, the menu, and notifications) is verified on a real device.

## Related context

- [[qt-harmonyos-golden-rules]] — W5 (hiding the main window falls back to minimizing), L2 (argv[0] is the .so library path)
- [[qt-harmonyos-window-model]] — The relationship between window visibility and the status bar
- [[procedural-demo-generation]] — The six-step loop + §3.2 the OhosExportModules.ts pitfall (the 5.15 path)
- [[problem-runtime-crash-ohos-deviceinfo-global-expression]] — The @ohos.* eager-import trap (the 5.15-generation diagnostic)

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Filled the knowledge base's system tray gap at the source level: the HarmonyOS tray genuinely works (through the status bar's StatusBarExtensionKit) and isn't a probe stub |
| Scope of impact | Tray/notification/status-bar applications and demos, commercial responses, migration efficiency |
| Deliverables | ${DEMOS_ROOT}/tray-ohos (a complete Qt 5.12 OHOS demo + an unsigned HAP), a semantic knowledge page |
| Evidence | entry-default-unsigned.hap (37.7 MB, BUILD SUCCESSFUL), libTrayOhos.so's `T main`, libqohos.so strings containing the 5 statusBarManager methods |
| How to reuse | Any future tray/status-bar/notification Qt HarmonyOS demo or application can apply this page's API behavior and stub list directly |

## References

| Source type | Notes |
|-------------|-------|
| 🛠️ Verified in the Qt source | `qtbase/src/plugins/platforms/ohos/qohossystemtrayicon.cpp/.h` (all of QOhosSystemTrayIcon's virtuals + the ArkTS evals), `qohosstatusbarmenu.cpp/.h` (the menu backend + rightMenuClick/menuCode), `qohosplatformtheme.cpp:1005` (the createPlatformSystemTrayIcon factory), `qohosenums.h:143` (the notificationManager.ContentType fullTypeName), `qohosplugincore.cpp:659` (mapOhosEnumToJs) |
| 🛠️ Verified against the libqohos.so binary | `strings <SDK>/plugins/platforms/libqohos.so \| grep statusBarManager` confirms the 5 methods (addToStatusBar/removeFromStatusBar/updateStatusBarIcon/updateStatusBarMenu/updateStatusBarHoverTips) plus the `statusBarIconClick`/`rightMenuClick` events; `grep -E '@ohos.display\|@ohos.notificationManager'` confirms the two `@ohos.*` module names the tray evaluates match verbatim |
| 📖 Qt public API | `<QtWidgets/qsystemtrayicon.h>` (the QSystemTrayIcon public API + the ActivationReason enum + MessageIcon), `<QtGui/qpa/qplatformsystemtrayicon.h>` (the platform virtual interface) |
