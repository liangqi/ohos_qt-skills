---
id: build-fail-python-not-found
type: problem
domain: build
status: solved
audience: public
created: 2026-09-19
updated: 2026-09-19
severity: high
tags: [build, linux, qtdeclarative, python, qml]
refs: [skills/qt-sdk-forge/references/build-matrix.md, knowledge/errors/QOH038.yaml]
error_message: "sh: 1: python: not found / Project ERROR: Building QtQml requires Python."
error_code: N/A
summary: >
  qtdeclarative's qmake scripts call `python` (not `python3`), while Linux distributions such as Ubuntu
  ship only python3 by default. qtbase builds fine, and the error only appears at QtQml. The CLI has a built-in forge-local shim that fixes it automatically.
---

# The QtQml build reports python: not found (Linux)

## Symptoms

A full Qt build on Linux: qtbase/qtsvg/qtimageformats all compile, then it fails on entering qtdeclarative:

```
Info: creating cache file .../qtdeclarative/.qmake.cache
sh: 1: python: not found
Project ERROR: Building QtQml requires Python.
make: *** [Makefile:159: module-qtdeclarative-make_first] Error 3
```

## Cause

qtdeclarative's qmake build scripts (the `python` probe in `qtdeclarative.pro`) call
**`python`** rather than `python3`. Ubuntu/Debian and most server distributions don't install
`python-is-python3` by default, so the `python` command doesn't exist.

## Solution

**Now**: the CLI has a built-in automatic fix (since v2026-09-19): `build_env()` creates
`.qtsdk/pyshim/python` (a symlink to the current interpreter) in the forge state directory and prepends it to PATH, without polluting the host system.
The SV0 environment check also gained two new items, `python3` / `python_alias`.

**Manual equivalent** (when running make directly, bypassing the CLI):

```bash
# System-wide (simple)
apt install python-is-python3        # or
ln -s /usr/bin/python3 /usr/local/bin/python
```

Resume the build (incremental, no need to start over):

```bash
python3 tools/qt-sdk-run.py build    # modules already built are skipped
```

## Verification

```bash
python --version    # prints 3.x
```
