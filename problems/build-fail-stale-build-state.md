---
id: build-fail-stale-build-state
type: problem
domain: build
status: solved
audience: public
created: 2026-09-19
updated: 2026-09-19
severity: medium
tags: [build, incremental, qmake, dbus, pitfall]
refs: [knowledge/errors/QOH040.yaml, problems/build-fail-qtdbus-deprecated-copy.md]
error_message: "qibusplatforminputcontext.h:61:44: error: unknown type name 'QDBusPendingCall'"
error_code: N/A
summary: >
  When you reuse an old build directory after changing the configuration (such as switching to -no-dbus / changing the OHOS SDK), the old
  module .pri files under mkspecs/modules/ (qt_lib_dbus.pri) remain, qtHaveModule(dbus) is still true, and the ibus plugin is
  built as usual and reports missing QDBus types. The CLI now has a built-in configure fingerprint guard that cleans the directory automatically.
---

# Reusing the build directory after changing the configuration/SDK: leftover old module .pri files break the build

## Symptoms

After changing configure from "with dbus" to `-no-dbus` (or changing the OHOS SDK) and re-running configure +
build, config.summary clearly shows `Qt D-Bus ... no`, yet the ibus input-method plugin is still built:

```
qtbase/src/plugins/platforminputcontexts/ibus/qibusplatforminputcontext.h:61:44:
error: unknown type name 'QDBusPendingCall'
qtbase/src/plugins/platforminputcontexts/ibus/qibustypes.h:58:22:
error: unknown type name 'QDBusArgument'
```

## Cause

qmake's `qtHaveModule(dbus)` decides whether a module exists by looking for **module .pri files already generated in the build tree**
(`build-*/qtbase/mkspecs/modules/qt_lib_dbus.pri`). Re-running configure doesn't
delete old .pri files: the `qt_lib_dbus.pri` left by the previous configure with dbus is still there, so:

```
platforminputcontexts.pro: qtHaveModule(dbus) → true → SUBDIRS += ibus
```

The ibus plugin unconditionally does `QT += dbus`, but QtDBus is gone → it reports missing QDBus types.

Likewise, **changing the OHOS SDK** (such as API 15 → API 23) without cleaning the build directory leaves behind cached state with the old
sysroot paths, producing all kinds of unpredictable mismatches.

This is the fourth pitfall beyond the knowledge base's "three incremental-build pitfalls": **switching between configurations requires cleaning the build directory**.

## Solution

**Now**: the CLI has a built-in guard (since v2026-09-19): configure computes a fingerprint (the configure arguments +
the OHOS SDK path and the oh-uni-package.json version); when it differs from the last record for that variant slot, it automatically clears the
build directory and prints `wiped stale build dir ... see QOH040`; half-configured directories without a record are cleared as well.

**Manual equivalent**:

```bash
rm -rf workspace/qt-sdk/build/build-Qt5.12.12-arm64-v8a-gles
python3 tools/qt-sdk-run.py configure --qt 5.12 --render gles --build-type release
python3 tools/qt-sdk-run.py build
```

## Verification

After re-running configure, confirm the old .pri is gone:

```bash
ls workspace/qt-sdk/build/build-*/qtbase/mkspecs/modules/ | grep -c dbus   # → 0
```
