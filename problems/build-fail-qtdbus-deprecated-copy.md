---
id: build-fail-qtdbus-deprecated-copy
type: problem
domain: build
status: solved
audience: public
created: 2026-09-19
updated: 2026-09-19
severity: high
tags: [build, dbus, clang, werror, ohos]
refs: [knowledge/errors/QOH039.yaml, knowledge/errors/QOH002.yaml, problems/runtime-fail-libqtdbus-missing.md]
error_message: "qdbusreply.h:105:24: error: definition of implicit copy constructor for 'QDBusReply<T>' is deprecated ... [-Werror,-Wdeprecated-copy-with-user-provided-copy]"
error_code: N/A
summary: >
  Qt 5.12's QtDBus module fails to build under OHOS clang 15.0.4 because of -Wdeprecated-copy-style warnings + the mkspec's
  default -Werror. And the HarmonyOS runtime has no DBus at all (QOH002); the official prebuilt configuration uses -no-dbus.
  The CLI's configure now has -no-dbus built in.
---

# The QtDBus module fails to build with -Wdeprecated-copy (dbus should be disabled)

## Symptoms

When qtbase reaches the QtDBus module, it reports a large number of errors of the same kind and stops:

```
qtbase/include/QtDBus/../../src/dbus/qdbusreply.h:105:24: error: definition of
implicit copy constructor for 'QDBusReply<QString>' is deprecated because it
has a user-provided copy assignment operator [-Werror,-Wdeprecated-copy-with-user-provided-copy]
```

## Cause

1. Qt 5.12's `qdbusreply.h` is in a pre-2012 code style: it has a user-provided copy assignment but no
   copy constructor, and newer clang (15.x) emits a `-Wdeprecated-copy-with-user-provided-copy` warning for that
2. The `ohos-clang` mkspec has `-Werror` by default, so warnings are errors
3. **At the fundamental level**: the HarmonyOS runtime has no DBus, so installing `libQt5DBus.so` is pointless anyway (QOH002).
   The configure arguments of the official v5.12.12 prebuilt explicitly include `-no-dbus` (for both the Windows and macOS builds)

## Solution

**Now**: the CLI's configure has `-no-dbus` built in (since v2026-09-19, aligned with the official prebuilt configuration
and the configure command in `semantic/qt-harmonyos-build.md`).

**Manual equivalent** (when assembling configure yourself):

```bash
../configure ... -no-dbus ...
```

**Note**: when switching from an old configuration with dbus to `-no-dbus`, you must clear the build directory, or you'll hit
[build-fail-stale-build-state](build-fail-stale-build-state.md) (the ibus plugin still being built from leftovers).

## Verification

config.summary should show:

```
Qt D-Bus ............................... no
```
