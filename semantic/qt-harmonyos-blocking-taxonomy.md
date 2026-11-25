---
id: semantic-qt-harmonyos-blocking-taxonomy
type: semantic
domain: tech
tags: [qt, harmonyos, blocking, root-cause, taxonomy, feasibility, assess]
created: 2026-09-08
updated: 2026-09-08
status: active
audience: public
refs: [semantic-qt-harmonyos-modules, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-third-party-libs, semantic-qt-ohos-extras, procedural-qt-app-harmonyos-migration]
summary: >
  The taxonomy of "blocking root causes" for porting Qt applications to HarmonyOS, and its decision boundaries: first separate what adaptation can solve (QtOhosExtras wrappers /
  code guards / .so deployment paths / feature flags / shims) from what can't be adapted, then file the latter under one of 6 root cause codes
  (LIB-MISSING / MODULE-OUT-OF-SCOPE / PLATFORM-FEATURE-UNSUPPORTED /
  ABI-PERFORMANCE / CONCEPT-MISMATCH / OTHER) and route the follow-up action.
  The three-state verdict of `qt-ohos-run.py assess` (portable/blocked/uncertain) follows the boundary table on this page.
---

# Taxonomy of blocking root causes for porting Qt applications to HarmonyOS

> Consult this page when assessing **whether a Qt application can be ported to HarmonyOS**. The blockers produced by `qt-ohos-run.py assess`
> are classified by the codes on this page; the machine-readable version is `knowledge/adaptation/blockers.yaml`.

---

## Boundary statement: solvable by adaptation vs. not adaptable (must read)

**Only a root cause that "can't be solved by HarmonyOS porting adaptation" counts as a blocker** — that is, the kind that can only be moved forward by switching libraries / a system requirement /
Qt filling the gap / not investing, and that the application layer can't change.

Anything solvable by the following **adaptation techniques** **is not a blocker** (record it in the migration workflow and the must-adapt checklist
`knowledge/adaptation/checklist.yaml`):

| Adaptation technique | Common scenarios that "look like blockers but are actually solvable" | QtOhosExtras / platform wrapper interfaces |
|---------|--------------------------------------|------------------------------|
| QtOhosExtras wrapper interfaces | Launching child processes, inter-application communication, subwindow tagging, graded lifecycle closeEvent, screenshot prevention, dark mode | `startAppProcess` / `startNewAbilityInstance` / `startAbility(want)` / `setBundledAbilityAndQWindowBindingKeyForQWindow` (subwindow binding) / `getCloseEventRootCause` / `QOhosAppContext` |
| Code guard `#ifndef Q_OS_OHOS` | chmod/symlink/pthread_cancel/platform conditional branches wrongly matching Linux (note that `Q_OS_OHOS` implies `Q_OS_LINUX`; don't blindly widen guards) | The 8 categories in the platform limitations page |
| Adjusting the .so deployment path | dlopen EINVAL (can't load from a read-only path) | Package the `.so` into `entry/libs/arm64-v8a/` |
| Feature flag OFF / trimming non-core features | Direct X11/HWND/Cocoa/Wayland calls, optional platform integrations | `#ifndef Q_OS_OHOS` + stubs + CMake switches |
| Shim headers / disabling accelerated paths | Symbols missing from musl, missing Clang intrinsics | inline function shims, `--disable-modules` software implementations |

**Decision principle**: first confirm the root cause really "can't be changed by adaptation", then file it under the categories below. Sandbox constraints can mostly be solved via
QtOhosExtras / deployment paths / guards and aren't a blocking category; only when the core functionality no longer exists after trimming
is it escalated to `CONCEPT-MISMATCH`.

## Blocking root cause categories (quick reference)

| Code | Category | Root cause description (the kind adaptation can't change) | Typical signals | Follow-up action |
|------|------|------------------------------|----------|---------|
| `LIB-MISSING` | Third-party library not ported to HarmonyOS | A C/C++ third-party dependency has no OHOS arm64 prebuilt package, no cross-compilation recipe, no equivalent replacement, and shims/stubs can't work around it | `find_package(X REQUIRED)` not found, `undefined reference`, no bottle exists | Switch libraries / start a project to fill the gap; for a whole framework stack see the special case below |
| `MODULE-OUT-OF-SCOPE` | Qt module not supported on the platform (core dependency) | The Qt module depended on is completely absent from the OHOS SDK and carries core functionality that can't be trimmed (WebEngine/D-Bus/RemoteObjects/SerialBus, etc.) | `find_package(Qt5/6 <Module> REQUIRED)` fails; the module matrix marks it out-of-scope | Fill in or replace the Qt module (WebEngine→CEF); if it can be trimmed, it isn't a blocker |
| `PLATFORM-FEATURE-UNSUPPORTED` | The platform fundamentally doesn't provide the capability | A system capability is a blank on the HarmonyOS platform — not a missing library, not a sandbox permission | The native API/framework has no corresponding header/library in the OHOS SDK | System requirement |
| `ABI-PERFORMANCE` | ABI/compiler mismatch (no workaround) | OHOS Clang lacks an intrinsic, musl lacks a symbol, W^X forbids JIT, performance problems — and shims/disabling accelerated paths all fail | `undefined symbol` for an intrinsic, JIT-type applications | Rewrite / pick another backend |
| `CONCEPT-MISMATCH` | The problem domain has no mobile counterpart | The application's core problem domain is itself a desktop/system management capability, and the sandbox doesn't expose the corresponding resources | The problem domain is a desktop system capability (system monitors / window managers) | Don't invest |
| `OTHER` | Other | Not yet filed under the categories above | — | Assess further |

> **The KDE framework stack — a special large instance**: when what `LIB-MISSING` is missing is an entire framework stack (KDE Frameworks:
> ECM + several KF5/KF6 modules + PolkitQt, with ≥5 `find_package(KF6 ... REQUIRED)`),
> the effort is several person-years and some submodules have no platform counterpart — the verdict is don't invest; `blocking_category` is still
> `LIB-MISSING`, noted as "large framework stack instance".

## Mapping to the assess three-state verdicts

| Hit | assess verdict |
|------|------------|
| `MODULE-OUT-OF-SCOPE` / `CONCEPT-MISMATCH` / `PLATFORM-FEATURE-UNSUPPORTED` / KDE framework stack | **blocked** (with the blocker list and evidence) |
| `LIB-MISSING` / `ABI-PERFORMANCE` / `OTHER` | **uncertain** (with suggestions: switch libraries / start a project / pick another backend) |
| No blockers, only checklist hits and risk items | **portable** (with the must-adapt checklist + risk grading + an effort reference) |

## Related

- [[semantic-qt-harmonyos-modules]] — the module availability matrix (the basis for MODULE-OUT-OF-SCOPE verdicts)
- [[procedural-qt-app-harmonyos-migration]] — the phase zero pre-flight and the full migration workflow
- [[semantic-qt-harmonyos-third-party-libs]] — third-party library feasibility checks for LIB-MISSING
- `knowledge/adaptation/blockers.yaml` — the machine-readable version of this page (consumed by assess)
