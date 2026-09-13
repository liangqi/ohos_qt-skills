---
id: executable-memory-permission-denied
title: "JIT/runtime startup crash: executable memory permission not granted"
status: active
confidence: 0.7
sources:
  - type: experience
    name: "AWT/Swing JVM CodeCache, on-device verification"
    date: 2026-07-30
  - type: experience
    name: "Node V8 and JVM hap-bin, on-device verification"
    date: 2026-08-05
created: 2026-08-13
updated: 2026-08-15
last_confirmed: 2026-08-05
superseded_by: null
tags: [problem, runtime, jit, mmap, permission, signing]
refs: [native-runtime-embedding, hap-native-project-structure]
summary: "JITs such as V8/HotSpot hit ENOMEM/SIGABRT because writable-executable-memory permission or the profile ACL isn't in place; declare the permission and verify the signing grant."
audience: public
error_message: |
  Check failed: 12==errno (ENOMEM)
  CodeCache::initialize()
  JNI_CreateJavaVM
  Reason: Signal:SIGABRT
---

# JIT/runtime startup crash: executable memory permission not granted

## Error message

```text
V8: Check failed: 12==errno (ENOMEM)
HotSpot: CodeCache::initialize -> JNI_CreateJavaVM -> SIGABRT
```

## Scenario and cause

JITs such as V8 and HotSpot need to generate machine code dynamically. The platform security policy restricts writable/executable memory; and writing the permission name in `module.json5` alone, without the corresponding ACL in the signing profile, will not get it granted either.

## Solution

1. Confirm the failure really occurs in the JIT/code-cache executable-memory allocation, not in ordinary out-of-memory.
2. Declare `ohos.permission.kernel.ALLOW_WRITABLE_CODE_MEMORY` as the target system requires.
3. Sign with a profile that is approved for that system permission and matches your bundle/device.
4. After a clean install, verify the permission outcome, process startup, and runtime logs.

Don't assume that some "automatic signing" always grants system permissions. Whether a permission can be requested, is granted, and takes effect on a given class of device is determined by platform policy, account/certificate type, and the profile.

Interpreter mode or disabling the JIT can reduce risk where the runtime supports it, but you must verify performance and functionality separately — it is not a default general-purpose fix.

## Prevention

List your JIT/exec/mmap requirements during runtime selection. Verify with the release certificate and the debug certificate separately, and don't reuse another project's profile.
