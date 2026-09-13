---
id: harmonyos-development-fundamentals
title: HarmonyOS application development fundamentals
status: active
confidence: 0.7
sources:
  - type: official
    name: "HarmonyOS application development guide and API documentation"
    date: 2026-06-02
    uri: "https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/application-dev-guide"
  - type: doc
    name: "Qt Wiki: HarmonyOS Development Fundamentals"
    date: 2026-06-02
    uri: "https://wiki.qt.io/HarmonyOS_Development_Fundamentals"
created: 2026-08-13
updated: 2026-08-13
last_confirmed: 2026-06-02
review_by: null
superseded_by: null
tags: [harmonyos, openharmony, arkts, arkui, node-api, stage, deveco, hdc]
refs: []
summary: "A framework-neutral entry point to HarmonyOS application development: HarmonyOS vs. OpenHarmony, and the responsibility boundaries of Stage, ArkTS, ArkUI, Node-API, and DevEco/hdc."
audience: public
---

# HarmonyOS application development fundamentals

This page is an entry point to platform concepts that doesn't depend on Qt, Tauri, AWT/Swing, or Avalonia. For specific APIs, system behavior, and tool commands, defer to the official documentation for your target SDK and to this library's topic-specific pages.

## HarmonyOS vs. OpenHarmony

OpenHarmony is an open-source project under the OpenAtom Foundation; HarmonyOS is the commercial system Huawei delivers to its device and application ecosystem. They share some technical foundations, but you cannot assume their product capabilities, SDKs, API availability, signing permissions, and device policies are identical.

When migrating or troubleshooting, first establish:

- Whether the target is HarmonyOS or OpenHarmony
- The device form factor and system version
- The SDK/API level used to compile
- Whether a conclusion comes from public platform documentation, the target SDK, or one framework's adaptation implementation

## The application model and its main technology layers

| Layer | Main responsibility | Boundary for framework adaptation |
|---|---|---|
| Stage / UIAbility | Application components, lifecycle, launch, and Want routing | The platform defines the lifecycle; the framework maps its own event loop and window semantics onto it |
| ArkTS | The language for application-side logic and calls into system APIs | Framework glue usually reaches platform capabilities at the ArkTS layer |
| ArkUI | Declarative UI, components, layout, windows, and interaction | A framework may use ArkUI/XComponent purely as a rendering or window substrate |
| Node-API | The ABI between ArkTS/JS and native C/C++ modules | The framework handles threading, object lifetimes, and adapting its own types |
| Native C/C++ | The NDK, system interfaces, third-party libraries, and rendering runtimes | Platform toolchain and sandbox constraints are maintained here; framework build integration stays in the framework repository |

## Stage and UIAbility

The Stage model organizes runtime units around the application, modules, and abilities. A `UIAbility` is a UI-bearing application component that typically receives its launch target and parameters through a `Want`, with `module.json5` declaring metadata such as entry points, skills, device types, and permissions.

Don't equate a framework's window object with a UIAbility: a framework may manage several internal windows within a single Ability, or create extra windows through platform capabilities. The full lifecycle and Want semantics are maintained on the dedicated common pages.

## ArkTS, ArkUI, and Node-API

- ArkTS is the primary language for HarmonyOS application development, used for pages, abilities, and calls into system capabilities.
- ArkUI provides declarative components, layout, animation, events, windows, and the ability to host native components.
- Node-API lets ArkTS/JS call native C/C++ modules; cross-thread calls, async callbacks, object release, and exception propagation must all be managed explicitly by the integration layer.

Starting points:

- [ArkTS overview](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/arkts-overview)
- [Node-API development process](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/use-napi-process)
- [Window management](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/window-manager)

## Development and debugging tools

DevEco Studio provides project editing, SDK management, building, signing, debugging, and profiling. Command-line automation can be orchestrated uniformly through `devecocli`; AI tools can hook into static checks via deveco-mcp. The specific operating rules live on the internal tool-governance page and aren't required to understand this fundamentals page.

`hdc` is the device connector, used for low-level operations such as device queries, file transfer, installation, shell access, and logs. Day-to-day ecosystem workflows orchestrate these capabilities through `devecocli`; call the low-level tools directly only when diagnosing the wrapper layer itself or when the repository explicitly requires it.

## Project metadata note

The device types an application supports are declared in the module configuration, for example:

```json5
{
  "module": {
    "deviceTypes": ["phone", "tablet", "2in1"]
  }
}
```

The valid values and the range of products supported must come from the target SDK schema; changing the declaration alone will not make a framework adapt to new window, input, or display capabilities.

## Where to go next

- Stage/UIAbility lifecycle and Want routing
- ArkUI windows, XComponent, and native rendering hosts
- Node-API threading, object lifetimes, and exception boundaries
- The OHOS NDK, cross-compilation, HAP build signing, and the platform sandbox
