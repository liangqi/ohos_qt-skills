---
id: build-fail-bash-path-escape
type: problem
domain: build
status: solved
audience: public
created: 2026-06-05
updated: 2026-06-08
severity: medium
tags: [build, bash, path, mingw, powershell]
refs: []
error_message: "C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory"
error_code: N/A
summary: >
  mingw32-make path escaping fails under bash/git-bash: bash interprets the backslashes as escape characters,
  so the Windows short path C:\PROGRA~1\... is parsed as C:PROGRA~1... . You must run the build from PowerShell.
---

# mingw32-make path escaping fails under bash

## Symptoms

Running `mingw32-make -j64 install` in a bash/git-bash environment resolves the compiler path incorrectly:

```
/usr/bin/sh: line 1: C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory
```

Expected path: `C:\PROGRA~1\Huawei\DEVECO~1\sdk\default\OPENHA~1\native/llvm/bin/clang++`  
Actual path: `C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++`

The backslashes `\` are interpreted by bash as escape characters and swallowed.

## Cause

On Windows, `mingw32-make` runs build commands through `/usr/bin/sh` (bash), while the Windows short paths in the Makefile (such as `C:\PROGRA~1\...`) contain backslashes. bash interprets those backslashes as escape characters, so the path separators are lost.

## Solution

**You must run the build commands from PowerShell**, not bash/git-bash:

```powershell
cd <LOCAL_PATH>
mingw32-make.exe -j64 install
```

PowerShell handles Windows paths correctly and does not swallow backslashes.

## Failed approaches that were tried

1. ❌ Setting `PATH` to include clang within bash: `PATH="...:$PATH" mingw32-make`  
   → Failed; internally mingw32-make still invokes `/usr/bin/sh`

2. ❌ Changing `CC`/`CXX` in the Makefile to bare command names: `CC = clang`  
   → Failed; backslashes in the source file paths are still swallowed

3. ❌ Using `tr '\\' '/'` to replace every backslash in the Makefile  
   → Failed; the line-continuation `\` characters got replaced too, producing Makefile syntax errors

4. ❌ Manually compiling individual .cpp files and then linking  
   → Works but is slow; not practical for a full build

## Related

- Technology stack §Build environment
