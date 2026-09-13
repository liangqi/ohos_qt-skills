---
id: application-sandbox-paths
title: HarmonyOS application sandbox paths and code loading
status: active
confidence: 0.7
sources: [{type: experience, name: "Qt runtime embedding and cross-framework on-device path troubleshooting", date: 2026-08-05}]
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-05
review_by: null
superseded_by: null
tags: [sandbox, path, mount-namespace, bundle, writable, dlopen]
refs: []
summary: "Distinguishing bundle paths from data paths and the application namespace from the hdc shell namespace, and the rules governing writes, chmod, dlopen, and execve."
audience: public
---

# HarmonyOS application sandbox paths and code loading

## Three dimensions you must not conflate

1. **Nature of the content**: installation-package resources, native libraries/executables, or runtime data.
2. **Accessing subject**: the application process, a child process, the hdc shell, or a system service.
3. **Type of operation**: read, write, change permissions, `dlopen`, or `execve`.

Post-installation bundle paths hold signed/packaged content and generally cannot be freely written to or `chmod`ed by an ordinary application. Writable application data directories hold configuration, databases, caches, and user data — but "writable" does not imply that loading or executing code from that location is allowed.

## Mount namespaces

The application process and the hdc shell may observe the same bundle file under different prefixes. In a verified case the application saw a `/data/storage/...` view while the shell observed the installed content under `/data/app/...`. Don't hard-code an absolute path copied from the shell into the application.

Prefer obtaining paths from the platform context/APIs or the framework's application-directory APIs. When diagnosing, inspect the file from each accessing subject separately — don't infer from an `ls` in one namespace that a file must be visible in another.

## Operating rules

- Treat packaged resources as read-only; when you need to modify something, copy the data into a writable data directory the platform provides.
- Don't try to `chmod +x` bundle files from application code; declare binaries that need to be executed at packaging time.
- Don't `dlopen` a downloaded/generated `.so` straight out of an ordinary writable directory; first confirm the code distribution and signing model the platform allows.
- Diagnose "not found", "permission denied", and "loader rejected" separately: they may come from the namespace, Unix mode bits, signing/policy, or a missing dependency, respectively.

## The deletion test

Framework pages should keep "which framework API returns the path, the raw error, and the fix steps"; this page maintains the platform invariants. If a framework page can fully explain the sandbox/mount/loader rules without this page, its summary has gone too deep.
