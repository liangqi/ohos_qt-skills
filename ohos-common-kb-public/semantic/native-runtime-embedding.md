---
id: native-runtime-embedding
title: HarmonyOS native runtime embedding models
status: active
confidence: 0.7
sources: [{type: experience, name: "Python, Node, Java, Rust runtime embedding, on-device verification", date: 2026-08-05}]
created: 2026-08-13
updated: 2026-08-15
last_confirmed: 2026-08-05
review_by: null
superseded_by: null
tags: [runtime, embedding, hap-bin, shared-library, hnp, execve, jit]
refs: [application-sandbox-paths, executable-binary-eacces, executable-memory-permission-denied]
summary: "The three runtime integration models — hap-bin, in-process shared library, and HNP — and their path, signing, JIT, and verification contracts."
audience: public
---

# HarmonyOS native runtime embedding models

## Choosing a model

| Model | Isolation | Typical interface | Main risks |
|---|---|---|---|
| Executable inside the HAP (hap-bin) | Child process | fork/execve, stdin/stdout/IPC | Executable declaration, binary signing, path namespaces, JIT permission |
| In-process shared library | Same process | `dlopen` + C API | ABI, symbol closure; the main thread/signals/crashes affect the whole application |
| HNP | Separate package / system-managed path | HNP installation layout and public entry points | Device/distribution policy, path and version management complexity |

Choose based on the runtime's official embedding capabilities, your isolation requirements, and the platform's distribution model — don't lock in an architecture just because one framework API happens to be available.

## hap-bin contract

- The binary is packaged with the HAP and declared in `executableBinaryPaths` in `module.json5`.
- Post-installation execute permission, the integrity/signature section, and profile permissions are independent checks.
- The application and the shell see different path views; get paths from the running subject's platform API or a verified layout.
- The child process environment, stdlib/resources, locale, certificates, and dynamic dependencies must all be deployed explicitly.
- A JIT runtime may require a controlled writable-code-memory permission and a profile ACL.

## In-process shared library contract

- Use shared libraries built for the target ABI, and deploy the full `NEEDED` closure.
- Initialization order, allocator, threads, signals, locale, environment variables, and shutdown must all be explicitly managed by the host.
- Don't load code from an ordinary writable directory.
- Verify with a minimal C/C++ host first, then wire in the framework's event loop/threading adapter.

## Acceptance matrix

Cover at least: clean install, first launch, repeated launches, normal exit, abnormal exit, resource/stdlib loading, non-ASCII data, child processes/threads, permission denial, running after a device reboot, and a fresh package. The framework repository additionally verifies its UI/event loop and API adapter.
