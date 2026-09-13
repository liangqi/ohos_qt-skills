---
id: runtime-write-to-readonly-bundle-path
title: "Runtime write fails: the target is on a read-only bundle path"
status: active
confidence: 0.7
sources: [{type: experience, name: "Troubleshooting Qt application databases, Python, and resource paths", date: 2026-08-05}]
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-05
superseded_by: null
tags: [problem, runtime, sandbox, readonly, bundle, writable-path]
refs: [application-sandbox-paths]
summary: "The application writes a database, cache, configuration, or generated file into the packaged resource/installation directory and hits EACCES/EROFS; copy it to a platform-writable data directory."
audience: public
error_message: |
  Permission denied
  Read-only file system
  EACCES
  EROFS
---

# Runtime write fails: the target is on a read-only bundle path

## Scenario and cause

The application opens a database, configuration file, script, or model from its resources/bundle and then tries to modify it in place. Installed content exists for distribution and integrity verification — it is not a runtime data directory — so writes, renames, chmod calls, and creating adjacent temporary files all fail.

## Solution

1. Log the *category* of the target path rather than a sensitive absolute path.
2. Confirm whether it came from a bundle/resource API.
3. On first run, copy any seed data that needs modification into the application data/files/cache directory the platform provides.
4. Always use the copied path for subsequent reads and writes.
5. Verify initialization, migration, and failure rollback for both clean-install and upgrade scenarios.

Read-only resources can still be read directly. Don't `chmod` the bundle just to make it writable, and don't put your code and your mutable data in the same directory.

## Prevention

At design time, label every artifact as an immutable resource, mutable persistent data, cache, or executable code, and obtain directories from the platform context / framework path APIs.
