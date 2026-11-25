---
id: problem-runtime-tray-must-exist-noop
type: problem
domain: runtime
tags: [tray, Tray, no-op, link-time, member-variable, complete-public-surface, PSNI, HasMonochromeSetting]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: high
audience: public
summary: "HarmonyOS has no tray API, but Platform::Tray is a member variable and must be constructible: you need a complete no-op surface, not to delete the class"
# ====== Search keywords (for fast agent matching) ======
error_message: >
  ld.lld: error: undefined symbol: Platform::Tray::Tray()
  ld.lld: error: undefined symbol: Platform::Tray::HasMonochromeSetting() const
  ld.lld: error: undefined symbol: Platform::Tray::setIcon(...)
error_code: ""
keywords: [tray, Tray, no-op, undefined symbol, member variable, TrayIconSupported, HasMonochromeSetting, complete public surface]
symptoms: "The link fails after deleting the tray implementation for HarmonyOS; or only some methods were implemented, and it crashes only once it reaches an icon-related path"
# ====== Problem details ======
environment: "Qt 6.13.0-dev OHOS kit; the desktop application platform layer's tray abstraction (the Linux side is based on PSNI/StatusNotifier)"
refs: [problem-platform-layer-two-dispatch-modes, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-platform-layer-two-dispatch-modes]
---

# The tray on HarmonyOS: the capability is false, but the class must exist and be complete

## Root cause

On Linux the desktop application's tray abstraction goes through PSNI (StatusNotifierItem) / D-Bus, and HarmonyOS has neither.
But **"no capability" doesn't mean "no class is fine"**:

```cpp
// SourceFiles/tray.cpp
Platform::Tray _tray;                                  // constructed unconditionally
void InitTray() { if (!Platform::TrayIconSupported()) return; ... }
```

`TrayIconSupported()` only blocks "creating the icon"; object construction happens before it. So:

- **Delete the class** → at link time, `undefined symbol: Platform::Tray::Tray()`;
- **Implement only some methods** → the link passes, but you get `undefined symbol` when reaching an icon/menu path
  (a typical omission: `HasMonochromeSetting()`, which is referenced by `std::optional`-related code in the construction chain).

## The minimal complete public surface (14 methods + 1 query)

Implementation essentials: every behavior function is a no-op, capability queries return `false`, return values are "empty/safe defaults", never null pointers.

| Category | Methods |
|----------|---------|
| Lifecycle | `Tray()`, `~Tray()` |
| Capability queries | `TrayIconSupported()` → false, `TrayIconRegenerated()`, `HasMonochromeSetting()` → false |
| Icon | `setIcon(...)`, `SetIcon(...)`, `destroyIcon()` |
| Menu/activation | `setMenu(...)`, `showMenu()`, `updateMenu()`, `activate(...)` |
| Tooltips | `setToolTip(...)`, `updateToolTip()`, `showMessage(...)` |
| Extensions | `setAdaptiveIconColor(...)` and others (fill in one by one per the upstream public header) |

**Criterion**: implement every method, taking the parent class/public header as the reference; compare
`llvm-nm -C <tray_ohos.cpp.o> | grep ' T '` against the public header's method list; missing even one blows up at some call site.

## How to verify

1. Zero `undefined symbol: Platform::Tray` at link time;
2. Runtime: in `hilog` the capability queries return false, and the application starts normally with no icon (matching the "HarmonyOS has no tray" expectation);
3. Reverse check: temporarily delete one method; the link **must** fail. Otherwise the method isn't referenced at all,
   and can be removed from the public surface (keeping it "minimal but complete").

## Lessons learned

When "the platform lacks some capability", the right move is to **provide a complete no-op implementation + capability queries returning false**,
not to delete the abstraction. Deleting pushes the gap to link time, and a link-time error only gives a symbol name, not "which platform capability this is".
