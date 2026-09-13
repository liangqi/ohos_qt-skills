---
id: arkui-window-xcomponent-model
title: The ArkUI window and XComponent hosting model
status: active
confidence: 0.5
sources:
  - type: official
    name: "HarmonyOS Window and XComponent development guide"
    date: 2026-08-11
    uri: "https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/window-overview"
  - type: experience
    name: "Audit of Qt QPA's WindowStage, XComponent, and SurfaceHolder adaptation"
    date: 2026-08-11
created: 2026-08-14
updated: 2026-08-14
last_confirmed: 2026-08-11
review_by: null
superseded_by: null
tags: [arkui, window, xcomponent, surface, native-window, focus]
refs: []
summary: "Distinguishing WindowStage/main/subwindow, XComponent nodes, the native surface, focus/visible/drawable states, and the old-vs-new API seam."
audience: public
---

# The ArkUI window and XComponent hosting model

This page defines conceptual boundaries that are reusable across frameworks; it does not promote the internal state machine of any particular QPA, Skia, JVM, or WebView adapter into platform behavior.

## Window hierarchy

- A UIAbility obtains its window host through the WindowStage.
- The application's main window, subwindows, floating windows, and other extension windows have different system-task, parent-child, permission, and lifecycle semantics.
- A framework's top-level windows need not map one-to-one onto platform main windows; the mapping is the adapter's decision.
- "Window object exists", "display requested", "visible to the system", "has focus", and "surface is drawable" are all distinct states.

When troubleshooting, observe the platform window state, focus, visibility/exposure, surface lifecycle, and the framework's own visible flag separately — no single one of them stands in for all the others.

## The XComponent seam

XComponent hosts a native surface or native node within the ArkUI node tree, letting C/C++ rendering and components embed into a page. A typical seam consists of:

1. ArkUI creates and mounts the XComponent/ContentSlot node.
2. The platform creates or changes the surface/native window.
3. The native adapter receives lifecycle, size, and touch/mouse/key/focus events.
4. The render thread submits only while the surface is valid and the size/state are ready.
5. Once the node is unmounted or the surface is destroyed, the old handle is no longer used.

## The old/new API boundary

Interfaces such as OH_NativeXComponent and the Node API's SurfaceHolder/SurfaceCallback may cover different eras or different responsibilities. Creation failures have been observed when two surface-management paths are mixed, but the precise boundary at which they are mutually exclusive still needs a minimal native reproduction to confirm.

So this common knowledge base pins down only the following rules:

- An adapter must explicitly decide who owns the surface lifecycle.
- Don't register two surface owners of unknown compatibility simultaneously and assume they can coexist.
- Input, accessibility, and surface management may have different API seams; enumerate each dependency before migrating.
- Defer to the target SDK documentation for API deprecation/replacement relationships; an unverified Qt symptom must not be written up as a global system limitation.

## Focus, visibility, and drawability

| State | The question it answers |
|---|---|
| requested visible | Has the application/framework requested display? |
| system visibility/window status | How is the system currently presenting the window? |
| focus/active | Who receives keyboard, input, and visual activation? |
| surface available/exposed | Can the native renderer submit content right now? |

A successful return from an asynchronous window API usually just means the request was accepted. Wait for the corresponding callback/event, and cancel stale requests on timeout or window destruction.

## Adapter verification

Cover first creation, rotation/resize, foreground/background transitions, hide/show, surface recreation, window close, focus changes, touch/mouse/keyboard, the accessibility tree, and multiple windows. Define a validity lifetime before storing a native handle, and guard every callback against using an already-destroyed surface/node.
