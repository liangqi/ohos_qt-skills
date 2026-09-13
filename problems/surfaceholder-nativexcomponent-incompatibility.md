---
id: problem-surfaceholder-nativexcomponent-incompatibility
type: problem
domain: errors
tags: [ohos, xcomponent, surface, opaque, surfaceholder, nativexcomponent, qpa, framework, api-conflict, deferred]
created: 2026-06-24
updated: 2026-06-24
status: open
audience: public
severity: high
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-window-model]
summary: >
  When setting the XComponent surface opaque (OH_ArkUI_XComponentSurfaceConfig_SetIsOpaque),
  OH_ArkUI_SurfaceHolder_Create returns null. The system side confirmed that SurfaceHolder (Node API) and
  OH_NativeXComponent (the older NAPI) cannot be used together, while Qt's QPA depends heavily on OH_NativeXComponent
  (accessibility/input/platform integration), making full decoupling too risky. Left for later analysis: pinning down the exact API boundary that triggers the mutual exclusion.

# ====== Search keywords (for fast agent matching) ======
error_message: >
  OH_ArkUI_SurfaceHolder_Create returned null
  LastFatalMessage:::OH_NativeXComponent_GetNativeXComponent failed
error_code: ""
keywords: [SurfaceHolder, SurfaceConfig, SetIsOpaque, NativeXComponent, opaque, XComponent, mutually exclusive, cannot be used together]
symptoms: >
  SurfaceHolder_Create returns null when setting the XComponent surface opaque;
  or GetNativeXComponent returns null before the node is mounted, causing a startup crash.

# ====== Problem details ======
environment: >
  Qt 5.12.12 OHOS (tqtc/harmonyos-5.12.12, commit 613336de)
  + the OHOS SDK (API 22+; SurfaceHolder/SurfaceConfig are available from API 19/22)
  Files modified: qtbase/src/plugins/platforms/ohos/qarkui/qqtembeddedwindownode.{h,cpp}
---

# XComponent SurfaceConfig opaque: SurfaceHolder and NativeXComponent are mutually exclusive

> **Error type**: API mutual exclusion / architectural conflict (SurfaceHolder_Create returns null at runtime)
> **Affected versions**: Qt 5.12 / 5.15 for OHOS
> **Status**: ⚠️ **Left for later analysis** (unresolved; the mutual-exclusion boundary must be pinned down before choosing an approach)

---

## Goal

Set `isOpaque=true` on the XComponent surface that Qt's QPA creates, so the compositor can skip alpha blending and improve performance.

The **only C entry point** for setting opaque is `OH_ArkUI_SurfaceHolder_SetSurfaceConfig(holder, config)` (the SDK has no setter that acts directly on an `ArkUI_NodeHandle` — confirmed).

The call chain:
```
OH_ArkUI_SurfaceHolder_Create(node)           // API 19
OH_ArkUI_XComponentSurfaceConfig_Create()     // API 22
OH_ArkUI_XComponentSurfaceConfig_SetIsOpaque(config, true)  // API 22
OH_ArkUI_SurfaceHolder_SetSurfaceConfig(holder, config)     // API 22 ← the only entry point that applies it
OH_ArkUI_XComponentSurfaceConfig_Dispose(config)
```

## Symptoms

1. `OH_ArkUI_SurfaceHolder_Create(node)` returns null (even when the node is mounted and `OH_NativeXComponent_GetNativeXComponent` has returned a valid pointer)
2. The opaque configuration can't be applied
3. Earlier versions also crashed because `GetNativeXComponent` returned null before mounting (fixed by deferring `registerCallbacks` until after mounting)

## Cause

### The mutual exclusion confirmed by the system side

<STAKEHOLDER> confirmed: **`OH_ArkUI_SurfaceHolder` (Node API) and `OH_NativeXComponent` (the older NAPI) cannot be used together**.

But **the exact API boundary that triggers the mutual exclusion hasn't been pinned down**. There are two possibilities:

| Hypothesis | Meaning | Scope of the fix |
|------------|---------|------------------|
| **A. Fully mutually exclusive** | Once `GetNativeXComponent` / `RegisterCallback` has been called (even just for touch), SurfaceHolder_Create fails | Fully decouple from NativeXComponent (a massive refactor) |
| **B. Only surface management is mutually exclusive** | As long as NativeXComponent no longer manages the surface (surface callback slots nulled out, keeping only DispatchTouchEvent), it can coexist with SurfaceHolder | A small change (surface via SurfaceHolder, touch still via NativeXComponent) |

### The Qt framework's deep dependence on OH_NativeXComponent (the obstacle to full decoupling)

`OH_NativeXComponent` is used not just for surface+touch callbacks but is deeply embedded in several subsystems:

| Subsystem | Where it's used |
|-----------|-----------------|
| **Accessibility** | `qohosaccessibilityprovider.cpp`, `qohosaccessibilitytree.cpp`, `qohosaccessibilityarkuihelpers.cpp` (`QXComponentRender` is used for accessibility provider registration and node mapping) |
| **Input** | `qohosnativexcomponentinputhandler.cpp` (touch via `GetTouchEvent`/`GetTouchPoint*`, mouse via `GetMouseEvent`, keyboard via `GetKeyEvent*`) |
| **Platform integration** | `qohosplatformintegration.cpp` (`xComponentProvider` runs through it) |
| **QNativeNode** | `renderXComponent()` returns a `QXComponentRender` that's passed around everywhere |
| **XComponentId** | `tryCreateFromXComponent()` takes the ID from an `OH_NativeXComponent*` |

### The coupling point: `OH_NativeXComponent_RegisterCallback` bundles surface + touch

The `OH_NativeXComponent_Callback` struct registers 4 callbacks together:
- `OnSurfaceCreated` / `OnSurfaceChanged` / `OnSurfaceDestroyed` (the surface lifecycle)
- `DispatchTouchEvent` (touch)

You can't keep only the surface and migrate only touch away, or vice versa. Decoupling the surface means dealing with touch too.

### Existing Node API alternatives (already implemented)

| Input type | The old NativeXComponent path | The Node API alternative | State of the Node handler |
|------------|-------------------------------|--------------------------|---------------------------|
| Surface create/change/destroy | `RegisterCallback` | `SurfaceHolder` + `SurfaceCallback` | ❌ Needs writing |
| Touch | `DispatchTouchEvent` + `GetTouch*` | `NODE_TOUCH_EVENT` + `OH_ArkUI_PointerEvent_*` | ❌ Needs a new handler |
| Mouse | `RegisterMouseEventCallback` (off by default) | `NODE_ON_MOUSE` | ✅ `qohosnativemouseeventshandler` exists |
| Hover | `DispatchHoverEvent` (off by default) | `NODE_ON_HOVER_EVENT` | ✅ `QOhosHoverEventsGenerator` exists |
| Keyboard | `RegisterKeyEventCallback` (off by default) | `NODE_ON_KEY_EVENT` | ✅ `qohosnativekeyeventshandler` exists |

> Mouse and keyboard already have Node API paths (`isNativeNodeApiMouseEventsEnabled` / `isNativeNodeApiKeyEventsEnabled` default to true). **Touch is the only gap.**

## Solution

⚠️ **Unresolved.** Current state of the code (`qqtembeddedwindownode.cpp`): the surface still goes through `OH_NativeXComponent_RegisterCallback`, and `applySurfaceConfig()` attempts `SurfaceHolder_Create` in the `OnSurfaceCreated` callback but gets null.

### The verification plan to run (minimal change, to pin down the mutual-exclusion boundary)

In `XComponentCallbackDispatcher::registerCallbackReceiver`:
1. Set the 3 surface slots of `OH_NativeXComponent_Callback` to `nullptr`, keeping only `DispatchTouchEvent`
2. Move the surface lifecycle onto `OH_ArkUI_SurfaceHolder` + `OH_ArkUI_SurfaceCallback` (Created/Changed/Destroyed)
3. Apply the opaque configuration in the `SurfaceCreated` callback
4. Build, run, and observe whether `SurfaceHolder_Create` returns non-null

**Interpretation**:
- If it returns non-null → the mutual exclusion is limited to surface management (hypothesis B holds) and a small change suffices
- If it's still null → `GetNativeXComponent` itself is mutually exclusive (hypothesis A holds), and C API opaque isn't feasible in the current architecture

### Fallback directions if hypothesis A holds

1. **Go through the ArkTS side**: have the `.ets` template call `XComponentController.setXComponentSurfaceConfig({isOpaque:true})`. But we'd need to confirm whether that affects the native window Qt's QPA creates via `createNode(ARKUI_NODE_XCOMPONENT)` (probably not, since it's a different node).
2. **Follow up with the system side**: ask whether an opaque setter acting directly on an `ArkUI_NodeHandle` (bypassing SurfaceHolder) is planned.
3. **Accept that it's unsupported**: opaque can't be set in the current architecture; record it as a platform limitation.

## Notes

- **Don't attempt full decoupling blindly**: it touches the accessibility subsystem, can't be tested locally, and is extremely risky. Don't try it before the mutual-exclusion boundary is pinned down.
- **The effort to migrate touch**: even migrating only touch to `NODE_TOUCH_EVENT` requires writing new `qohosnativetoucheventshandler.{h,cpp}` files and porting the multi-touch / tool type / tilt / display coordinate / historical point logic (roughly 200+ lines), none of which can be verified locally.
- **API versions**: SurfaceHolder/SurfaceConfig require API 19/22+; `NODE_TOUCH_EVENT` has the value 0 in `native_node.h` (a base enumerator).
- Existing analysis document: `${DEMOS_ROOT}/<INTERNAL_DEMO>` (includes mermaid sequence diagrams).

## Related

- Analysis document: `<LOCAL_PATH>`
- Plan file: `<LOCAL_PATH>`
- [[semantic-qt-harmonyos-window-model]]
