---
id: problem-platform-layer-two-dispatch-modes
type: problem
domain: build
tags: [platform-layer, header-dispatch, source-dispatch, tray, notification-manager, undefined symbol, no-op-implementation]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: high
audience: public
summary: "The platform layer has two dispatch mechanisms (#ifdef inside headers / the build choosing a .cpp by path); changing only the #ifdef permanently misses half of it"
# ====== Search keywords (for fast agent matching) ======
error_message: >
  ld.lld: error: undefined symbol: Platform::Tray::Tray()
  ld.lld: error: undefined symbol: Ui::CreateNotificationManager()
  fatal error: 'gio/gio.h' file not found
  fatal error: 'xcb/xcb.h' file not found
  error: 'glibmm.h' file not found
error_code: ""
keywords: [platform layer, header dispatch, source dispatch, platform_tray.h, platform_webauthn.h, undefined symbol, no-op, tray]
symptoms: "After filling in the #ifdef branches, the link blows up with a flood of platform symbols; or the Linux implementation gets compiled in as 'some other platform'"
# ====== Problem details ======
environment: "Qt 6.13.0-dev OHOS kit; the desktop application's platform layer has 11 dispatch headers + 18 implementation files in total"
refs: [problem-platform-guard-needs-both-ohos-macros, problem-runtime-tray-must-exist-noop, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-platform-guard-needs-both-ohos-macros, problem-runtime-tray-must-exist-noop]
---

# The platform layer has two dispatch mechanisms; changing only the `#ifdef` misses half of it

## Root cause

A desktop application's platform layer isn't one mechanism but **two coexisting ones**:

| Mechanism | Where it's decided | Header shape | What to change |
|-----------|--------------------|--------------|----------------|
| **Header dispatch** | An `#ifdef` chain inside the header | `#ifdef Q_OS_WIN / #elif Q_OS_MAC / #elif Q_OS_OHOS / #else` (else = Linux) | Change the chain (and it must use both macros; see [[platform-guard-needs-both-ohos-macros]]) |
| **Source dispatch** | The build system picks a `.cpp` by path | **No** `#ifdef` in the header | Add `ohos/xxx_ohos.cpp` and make the build select it |

A typical split is 9 header-dispatched + 5 source-dispatched. Auditing only the `#ifdef`s caps coverage at 9/14.
The headers in the source-dispatch category **need no changes at all**: `platform_webauthn.h` just does `#include "webauthn.h"`,
and which `.cpp` holds the real implementation is decided by the build; missing one shows up as `undefined symbol` at link time.

## The second pitfall: a capability being false ≠ you can skip providing the class

Domain objects (the tray, the notification manager) are **member variables**, unconditionally created by the construction chain:

```cpp
// SourceFiles/tray.cpp
Platform::Tray _tray;   // constructed unconditionally, regardless of TrayIconSupported()
```

`TrayIconSupported()` only prevents "creating the icon", not "constructing the object". So the right way to implement "HarmonyOS has no tray" is
**to provide a complete no-op implementation**, not to delete the class; delete it and you get undefined at link time.

## How to verify

1. Classify and count (script): `python tools/ohos-platform-audit.py <app>/SourceFiles/platform`
   — header-dispatched files must name both OHOS macros; source-dispatched files are listed separately and require a matching implementation under `ohos/`.
2. Converge at link time: feed the link log to `--undefined`, and the script lists symbols "not mentioned by any `ohos/` implementation":
   `python tools/ohos-platform-audit.py <platform-dir> --undefined link.log`
3. Prove on the device that "an empty implementation is enough but must exist": after installing, the logs should show the capability queries returning false while the objects exist:
   `platform appdata "..." icon "..." autostart false tray false permission true`.

## Solution

1. Classify first: headers with an `#ifdef` chain → add the dual-macro branch; headers without `#ifdef` → add `ohos/xxx_ohos.cpp` and confirm the build selects it.
2. Then fill in the implementation: capability queries return false, behavior functions are no-ops; **keep the complete public surface** (especially for the tray; see
   [[runtime-tray-must-exist-noop]]).
3. Assert coverage with the script rather than working backwards from the linker's `undefined symbol`: that's the last link in the chain, and every link before it has to pass first.
