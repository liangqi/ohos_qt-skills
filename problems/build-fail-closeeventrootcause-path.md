---
id: problem-closeeventrootcause-compile-fail
type: problem
domain: build
tags: [compile, enum-class, CloseEventRootCause, API-path]
created: 2026-06-03
updated: 2026-06-03
status: solved
audience: public
summary: "Build error: the QtOhosExtras::AbilityClose/WindowStageClose/InternalClose enumerators can't be found (API path changed)"
severity: high

# ====== Search keywords (for fast agent matching) ======
error_message: >
  error: 'AbilityClose' is not a member of 'QtOhosExtras'
  error: 'WindowStageClose' is not a member of 'QtOhosExtras'
  error: 'InternalClose' is not a member of 'QtOhosExtras'
error_code: ""
keywords: [CloseEventRootCause, AbilityClose, WindowStageClose, InternalClose, enum, compile]
symptoms: "Build error: enumerators such as QtOhosExtras::AbilityClose can't be found"

# ====== Problem details ======
environment: "Qt 5.12/5.15 for HarmonyOS, C++14/C++17"
refs: [semantic-qt-harmonyos-lifecycle, semantic-qt-ohos-extras, semantic-qt-harmonyos-golden-rules]
related_problems: []
---

# CloseEventRootCause short path fails to compile

## Error message

```
error: 'AbilityClose' is not a member of 'QtOhosExtras'
   if (cause == QtOhosExtras::AbilityClose) {
                            ^~~~~~~~~~~~~~
note: suggested alternative: 'CloseEventRootCause'
```

Or similar:

```
error: 'WindowStageClose' is not a member of 'QtOhosExtras'
error: 'InternalClose' is not a member of 'QtOhosExtras'
```

## Scenario

Using the short path `QtOhosExtras::AbilityClose` to access the close-reason enumerators in a `closeEvent()` handler fails to compile.

## Cause

`CloseEventRootCause` is a C++11 `enum class` (a strongly typed enum), so its enumerators are **not** directly visible in the enclosing `QtOhosExtras` namespace. You must use the fully qualified path:

```
QtOhosExtras::CloseEventRootCause::AbilityClose       ✅
QtOhosExtras::AbilityClose                             ❌
```

This was a **correction-propagation gap** found during an audit: `lifecycle.md` (the gold standard) used the correct path, but `porting-workflow.md` and `api-mapping.md` still used the short path.

## Solution

Change every enum reference to the fully qualified path:

```cpp
auto cause = QtOhosExtras::getCloseEventRootCause(event);

// ✅ Correct: the full enum class path
if (cause == QtOhosExtras::CloseEventRootCause::WindowStageClose) {
    // Level 1: the user closed the window
} else if (cause == QtOhosExtras::CloseEventRootCause::AbilityClose) {
    // Level 2: the system is reclaiming it
} else {
    // InternalClose
}
```

## Notes

- The same rule applies to the `ColorThemeMode` enum: `QtOhosExtras::ColorThemeMode::FollowSystemSetting` (not `QtOhosExtras::FollowSystemSetting`)
- Golden rules A1/A2 explicitly require the fully qualified path
- This was fully corrected in the 06-03 audit (porting-workflow.md + api-mapping.md, 6 occurrences in total)

## Related

- [[qt-harmonyos-lifecycle]] — the gold standard (canonical source)
- [[qt-ohos-extras]] — the CloseEventRootCause enum definition
- [[qt-harmonyos-golden-rules]] — rules A1/A2

> 📋 Back to the [error quick-reference table](_lookup.md)
