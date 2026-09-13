---
id: problem-build-hvigor-native-skip
type: problem
domain: build
tags: [hvigor, cmake, native-build, deveco-sdk-home, java, environment]
created: 2026-06-08
updated: 2026-08-14
status: solved
audience: public
severity: high
error_message: "spawn java ENOENT; BuildNativeWithCmake finished after 1ms with no .so artifact (DEVECO_SDK_HOME missing)"
refs: [semantic-qt-harmonyos-build-run-workflow]
summary: >
  hvigor doesn't build the native code (BuildNativeWithCmake takes 1 ms): DEVECO_SDK_HOME isn't set, so the
  CMake toolchain can't be found; PackageHap then fails with spawn java ENOENT because Java isn't on PATH.
---

# hvigor skips the native build + Java missing during HAP packaging

## Error messages

### Symptom 1: the native build is skipped
```
> hvigor Finished :entry:default@BuildNativeWithCmake... after 1 ms
> hvigor Finished :entry:default@BuildNativeWithNinja... after 1 ms
```
The build reports BUILD SUCCESSFUL but produces no .so artifacts.

### Symptom 2: HAP packaging fails
```
ERROR: Failed :entry:default@PackageHap...
ERROR: spawn java ENOENT
```

### Symptom 3: crash after copying Java
```
Command failed with exit code 3221225781: java -Dfile.encoding=GBK -jar ...
```
(0xC0000135 = STATUS_DLL_NOT_FOUND — java.exe is missing dependencies such as jvm.dll)

## When it happens

- Running an hvigor build from the command line (bash/terminal) without setting `DEVECO_SDK_HOME`
- The native step doesn't run during a DevEco MCP tool build (MCP doesn't pass through the SDK environment variables)

## Root cause

1. **DEVECO_SDK_HOME is missing**: hvigor needs this environment variable to locate the OHOS SDK toolchain. Without it, `BuildNativeWithCmake` is silently skipped (1 ms) without reporting an error.
2. **Java isn't on PATH**: the `PackageHap` step invokes the `java` command to run `app_packing_tool.jar`. DevEco Studio's IDE bundles JBR, but a command-line environment must be configured manually.
3. **Copying java.exe alone doesn't work**: JBR's java.exe depends on jvm.dll and other DLLs in the same directory, so the whole `jbr/bin` directory must be added to PATH.

## Solution

### Environment variables needed for a command-line build

```bash
# Required
export DEVECO_SDK_HOME="C:/Program Files/Huawei/DevEco Studio/sdk"

# Java must be reachable via PATH (copying java.exe alone is not enough)
export PATH="/c/Program Files/Huawei/DevEco Studio/jbr/bin:$PATH"
```

### Full build command

```bash
export DEVECO_SDK_HOME="C:/Program Files/Huawei/DevEco Studio/sdk"
export PATH="/c/Program Files/Huawei/DevEco Studio/jbr/bin:$PATH"

cd <project-root>
node "C:/Program Files/Huawei/DevEco Studio/tools/hvigor/bin/hvigorw.js" \
  --mode project -p product=default assembleApp -p buildMode=debug --no-daemon
```

### Clear the caches and rebuild

If `BuildNativeWithCmake` still reports 1 ms, clear all the caches:
```bash
rm -rf entry/.cxx entry/build .hvigor
```

## Verification

After a successful build, the HAP should contain every .so:
```bash
unzip -l entry/build/default/<INTERNAL_OUTPUT> | grep "\.so"
```

## Lessons learned

1. **Limits of the DevEco MCP tool**: a successful MCP build does not mean the native code compiled. `BuildNativeWithCmake 1ms` is the telltale sign of a silent skip.
2. **MCP tool vs. command line**: the MCP tool runs inside the DevEco Studio environment and configures the Java and SDK paths automatically — but `DEVECO_SDK_HOME` may not be passed through to the hvigor child process.
3. **How to diagnose**: check whether `entry/.cxx/` contains `CMakeCache.txt`, and whether there are `.so` artifacts under `entry/build/`.

## Content source

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | Found while building the Coin3D Quarter demo; confirmed in both the MCP and command-line environments |
