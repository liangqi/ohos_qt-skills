---
id: cpython-dynamic-embedding-ohos
title: Embedding CPython as a shared library in a HarmonyOS application
status: active
confidence: 0.5
sources: [{type: experience, name: "expressPython Qt/OHOS dynamic embedding verification", date: 2026-08-04}]
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-04
review_by: null
superseded_by: null
tags: [cpython, embedding, shared-library, ohos, runtime]
refs: [application-sandbox-paths, ohos-native-third-party-libraries]
summary: "Embedding CPython in-process on HarmonyOS via libpython + the C API, deploying the stdlib/dependencies, and verifying initialization, threading, and paths."
audience: public
---

# Embedding CPython as a shared library in a HarmonyOS application

## Why:

The in-process shared-library approach avoids an extra executable/binary to sign and avoids IPC, but it also pulls the Python ABI, stdlib, extension modules, paths, GIL, and host lifecycle into a single shared failure domain.

## How to apply:

1. Build with the OHOS NDK — or otherwise obtain — a `libpython`, stdlib, and the extension modules you need, all with the same ABI and the same Python minor version.
2. Put the `.so` files and their full `NEEDED` closure into the HAP's native library directory, and the Python stdlib into a read-only resource directory.
3. At runtime, get the bundle/resource and writable data paths from the platform/framework context; don't hard-code hdc shell paths.
4. Before `Py_Initialize`, set the home, module search paths, program name, and argv through the supported Python config API.
5. After initialization, import a minimal set of standard library modules first, then load your application scripts; verify each extension module's ABI/symbols individually.
6. When the host calls Python from multiple threads, make GIL acquisition/release explicit; at shutdown, stop callbacks/threads before finalizing.
7. Verify on a clean install that there is no dependency on an external `PYTHONHOME`/`PYTHONPATH`, dev-machine files, or caches.

## Deployment checklist

- The Python minor version, stdlib, and `libpython` match exactly.
- Startup-critical modules such as encodings and importlib are present.
- `.pyc`/cache writes go to a writable data directory and don't pollute the bundle.
- Extension `.so` files use the OHOS ABI and have a complete dependency closure.
- Locale, UTF-8, certificates, time zone, and filesystem requirements are each verified separately.

## Adapter boundary

This common knowledge base maintains the CPython C API initialization and platform deployment invariants. Qt main-thread/event-loop handling, Tauri commands, a JVM bridge, or .NET host code stay in the corresponding framework repository. The current evidence comes from a Qt host, so other hosts must re-verify with a minimal native case before adopting this.
