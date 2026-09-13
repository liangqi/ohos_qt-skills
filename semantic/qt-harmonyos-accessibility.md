---
id: semantic-qt-harmonyos-accessibility
type: semantic
domain: tech
tags: [qt, harmonyos, accessibility, a11y, QAccessible, ArkUI_AccessibilityProvider, xcomponent, want, io.qt.experimental.enableA11ySupport, uitest, dumpLayout, ui-tree, testing, automation]
created: 2026-07-23
updated: 2026-07-23
status: active
audience: public
refs: [procedural-qt-ohos-run-test, problem-runtime-crash-ohos-deviceinfo-global-expression, semantic-qt-harmonyos-window-model, procedural-demo-generation]
summary: >
  The Qt OHOS accessibility (a11y) bridge and how to enable it: libqohos contains QOhosPlatformAccessibility (a QPlatformAccessibility subclass)
  that publishes Qt's QAccessible widget tree to the OHOS accessibility framework through each QWindow's XComponent native ArkUI_AccessibilityProvider
  (via callbacks such as findAccessibilityNodeInfosById). The bridge is off by default and is enabled by the [boolean launch Want parameter io.qt.experimental.enableA11ySupport]
  (aa start --pb io.qt.experimental.enableA11ySupport true) — not by an env variable, not by an appArg, and not automatically by a system screen reader.
  Once enabled, uitest dumpLayout -b <bundle> returns the complete Qt widget tree (QApplication/QWidget/QPushButton/QLabel + text + bounds);
  the DevEco MCP get_app_ui_tree goes through the ArkUI inspector and only reaches the XComponent node (no Qt widgets).
leader_summary: >
  Captured the Want-parameter mechanism for enabling the Qt HarmonyOS accessibility bridge and the uitest method for obtaining the Qt widget tree, enabling UI automation verification / widget location / click driving for Qt HarmonyOS applications.
impact: [Framework support, Migration efficiency]
deliverables: [knowledge page, device verification record]
evidence: [uitest dumpLayout before/after enabling the parameter (empty tree → the full Qt tree of QApplication/QPushButton/QLabel), qohosjsmain.cpp:564-627 source, the gate at qohosplatformintegration.cpp:171-177]
---

# The Qt for HarmonyOS accessibility bridge and enabling it via a Want parameter

## The core mechanism (verified in the source, qtbase/src/plugins/platforms/ohos)

The Qt OHOS QPA contains a complete accessibility bridge that connects Qt's `QAccessible` widget tree to the OHOS accessibility framework. The chain:

```
The Qt QAccessible widget tree
  → QOhosPlatformAccessibility (a QPlatformAccessibility subclass; setActive(true), maps the tree on setRootObject)
  → AccessibilityTree (a copy of the Qt accessible tree)
  → per QWindow+XComponent: qnativenode.cpp:248 → tryInitializeAccessibilityForQWindowWithXComponent
    → registers callbacks with the XComponent's native ArkUI_AccessibilityProvider
       (findAccessibilityNodeInfosById / executeAccessibilityAction / findFocusedAccessibilityNode ...)
  → the OHOS accessibility framework (ArkUI accessibility) → queryable by consumers such as screen readers and uitest
```

**The bridge is compiled into libqohos.so** (gated on `QT_NO_ACCESSIBILITY`, which is undefined by default in Qt5, so it's compiled in; `strings libqohos.so` shows `QOhosPlatformAccessibility` plus all the `OH_ArkUI_AccessibilityElementInfoSet*` symbols (SetAccessibilityText/ComponentType/Clickable/ChildNodeIds…) and the `findAccessibilityNodeInfosById` error strings).

## Enabling it: the launch Want parameter (the key point)

The bridge is **off by default** (`experimentalEnableA11ySupport{false}`, qohosjsmain.cpp:106) and is enabled by a **boolean parameter in the application's launch Want** — not an env variable, not appArgs, and not automatically by a system screen reader:

```
getProcessLaunchOptionsFromWant(launchWant)                  // qohosjsmain.cpp:564
  assignWantParamIfPresent(experimentalA11ySupport,
      "io.qt.experimental.enableA11ySupport")                // :583-584  ← the Want parameter name
setGlobalFlagsFromAppProcessLaunchOptions(launchOpts)        // :616, called at :803
  experimentalEnableA11ySupport = launchOpts.experimentalA11ySupport.Value()  // :626-627
isA11ySupportEnabled() → return experimentalEnableA11ySupport   // :1968
QOhosPlatformIntegration constructor:                        // qohosplatformintegration.cpp:171-177
  #ifndef QT_NO_ACCESSIBILITY
    if (QtOhos::isA11ySupportEnabled())                      // :172  ← only builds the bridge when true
       m_accessibilityContext = makeAccessibilityContext();
       installEventFilter(makeAccessibilityEventHandler());
  #endif
```

**The command to enable it** (`aa start` passes boolean Want parameters with `--pb`):

```bash
hdc shell aa start -b <bundle> -a <ability> \
    --pb io.qt.experimental.enableA11ySupport true
```

### Other io.qt.* launch Want parameters (the same mechanism, getProcessLaunchOptionsFromWant)

| Want parameter | Type | Purpose |
|----------------|------|---------|
| `io.qt.experimental.enableA11ySupport` | bool | **Enables the accessibility bridge (this page)** |
| `io.qt.useDefaultUiAbilityInstanceInQt` | bool | Use the default UIAbility instance |
| `io.qt.appSharedLibNameOverride` | string | Override the application's .so name |
| `io.qt.experimental.enableGlBackingStore` | bool | Experimental GL backing store |
| `io.qt.experimental.enableSupportContextMenuEventOnLongPress` | bool | Long press triggers a context menu event |
| `io.qt.experimental.enableVsyncOnSoftwareBackingStore` | bool | vsync for the software backing store |
| `io.qt.experimental.enableNativeNodeApiKeyEvents` | bool | NativeNode API keyboard events |
| `io.qt.experimental.enableNativeNodeApiMouseEvents` | bool | NativeNode API mouse events |
| `io.qt.watchdogEnabled` | bool | QtWatchdog |
| `io.qt.debug.drawQtRasterBackingStoreFlushedRegion` | bool | Debug-draw the flushed region |
| `io.qt.debug.useBasicStyleAndTheme` | bool | Use the basic style/theme for debugging |
| `io.qt.debug.redirectedStdoutPath` | string | File to redirect stdout to |
| `io.qt.debug.autoRequestPermissions` | string | Request permissions automatically |

> Note: the system accessibility service (`startup.service.ctl.accessibility`, with the device reporting `BarrierFree.Accessibility.Core/Vision/Hearing=true`) runs continuously regardless of this parameter; but **whether the Qt bridge is created on the application side** depends on it. A system screen reader is a consumer — its presence doesn't mean the application's bridge is up.

## Getting the Qt widget tree: uitest vs. the DevEco MCP

| Tool | Mechanism | Before enabling the parameter | After enabling it |
|------|-----------|-------------------------------|-------------------|
| **`uitest dumpLayout -b <bundle>`** | Queries through the accessibility framework | An empty tree (no Qt widgets) | **The complete Qt widget tree** (QApplication/QWidget/QPushButton/QLabel + text + origBounds) |
| DevEco MCP `get_app_ui_tree` full | An ArkUI inspector dump (the ArkUI component tree) | Only the XComponent node + containers | Still only the XComponent (Qt widgets live behind the provider and aren't ArkUI nodes) |
| DevEco MCP `get_app_ui_tree` simple | A WMS window dump | Window bounds | The same (window level) |

**How to get the Qt widget tree**:

```bash
hdc shell uitest dumpLayout -b <bundle>           # saved to /data/local/tmp/layout_*.json
# After pulling/reading it, widget nodes include "type":"QPushButton"/"QLabel"/"QWidget", "text":..., "origBounds":"[l,t][r,b]"
```

Widget bounds are `[left,top][right,bottom]`, and the center point `(l+r)/2, (t+b)/2` can be fed to `uitest uiInput click <x> <y>` to drive clicks.

**Why the DevEco MCP's get_app_ui_tree can't see Qt widgets**: Qt Widgets render inside the XComponent surface and aren't ArkUI nodes; they're exposed as accessibility elements through the XComponent's `ArkUI_AccessibilityProvider` callbacks, not in the ArkUI inspector tree. The ArkUI inspector stops at the XComponent node itself. So **getting the Qt widget tree requires `uitest dumpLayout` (the accessibility channel), and you must enable `io.qt.experimental.enableA11ySupport` first**.

## Key diagnostic signals

- The bridge is off by default: without the parameter → libqohos doesn't create `QOhosPlatformAccessibility`, and `uitest dumpLayout -b` returns an empty tree for Qt windows (only the window/containers, no Qt widgets).
- The bridge is compiled in: `strings libqohos.so | grep -i accessibility` hitting `QOhosPlatformAccessibility` + `OH_ArkUI_AccessibilityElementInfoSet*` means the bridge is present; nothing at all means libqohos was built with `QT_NO_ACCESSIBILITY` (and needs rebuilding).
- Going from an empty tree to the full Qt tree after enabling the parameter proves the bridge was created, the XComponent provider was registered, and the QAccessible tree was published.
- No application code changes are needed (the bridge is automatic): just add `--pb io.qt.experimental.enableA11ySupport true` to the launch.
- **The prebuilt Qt 6.12 beta2 libqohos.so was measured to be built with `QT_NO_ACCESSIBILITY`** (2026-08-05, end-to-end testing with FeatherPad (an internal KB retrospective, not reachable in the public edition): `grep -ao` for the a11y bridge symbols `QOhosPlatformAccessibility`/`OH_ArkUI_AccessibilityElementInfoSet*`/`experimentalEnableA11ySupport`/`isA11ySupportEnabled` found nothing, with a "ccessibilit" count of 0 → the bridge isn't compiled in → `--pb` has no effect → `uitest dumpLayout` only returns the ArkUI tree and never the Qt widget tree; confirmed by measurement). **Prebuilt B′ can't run a11y-tree automated tests**; you need strategy B's source superbuild to rebuild libqohos (without defining QT_NO_ACCESSIBILITY).

## Use cases

1. **UI automation/verification**: get a Qt widget's bounds → drive the button with `uitest uiInput click` (instead of blind coordinates). Example: qapp-recreate-test uses this to locate btn1 (origBounds) → clicking it triggers a second QApplication construction/recreate.
2. **Widget tree inspection**: confirm the Qt widget structure/text/visibility (instead of screenshots where you can't see the content).
3. **Accessibility regression**: verify that Qt widgets' accessible text/role are exposed correctly to the system screen reader.

## Related

- [[procedural-qt-ohos-run-test]] — OHOS on-device run verification (getting the tree with uitest + driving clicks)
- [[problem-runtime-crash-ohos-deviceinfo-global-expression]] — This mechanism is used to locate/click to trigger the recreate that verifies the deviceInfo fix
- [[semantic-qt-harmonyos-window-model]] — The XComponent/window model (the accessibility provider is bound to the XComponent)
- [[procedural-demo-generation]] — After generating a demo, use uitest to get the tree and verify

## References

| Source type | Notes |
|-------------|-------|
| 🛠️ Verified in the Qt source | qtbase/src/plugins/platforms/ohos/{qohosjsmain.cpp, qohosplatformintegration.cpp, accessibility/*, render/qnativenode.cpp} |
| 🔬 Device verification | uitest dumpLayout before/after enabling the parameter + aa start --pb testing (HUAWEI MateBook Fold, OHOS 6.0) |
