---
id: dlopen-rejects-writable-path
title: "Shared library fails to load: the code lives on an ordinary writable path"
status: active
confidence: 0.7
sources: [{type: experience, name: "On-device troubleshooting of Qt plugins and runtime embedding", date: 2026-08-05}]
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-05
superseded_by: null
tags: [problem, runtime, dlopen, writable-path, sandbox, loader]
refs: [application-sandbox-paths, ohos-native-third-party-libraries]
summary: "The loader/security policy rejects an application's dlopen of code from an ordinary writable data/cache path; package it with the HAP in a compliant way and check the dependency closure."
audience: public
error_message: |
  dlopen failed
  Permission denied
  library load rejected
---

# Shared library fails to load: the code lives on an ordinary writable path

## Scenario and cause

The application downloads, extracts, or generates a `.so` into an ordinary writable location such as data/cache, then tries to `dlopen` it. A writable data directory is not automatically a trusted source of code, so the platform loader/security policy may reject it. The same error can also come from a missing dependency, an ABI mismatch, or a corrupted ELF.

## Solution

1. Confirm the resolved library path and what category its directory falls into.
2. Check the ELF target, its `NEEDED` entries, and the loader logs to rule out ordinary dependency problems.
3. Place fixed native code in the HAP's ABI library directory at build time and distribute it through the full signing chain.
4. If the product genuinely requires dynamic code updates, use a distribution/signing mechanism the platform explicitly supports — don't load from data/cache yourself.

## Prevention

Design data updates and executable-code updates as separate mechanisms; a framework's plugin manager must not bypass the platform's code-integrity model.
