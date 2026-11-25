---
id: build-fail-ohos-sdk-api-too-old
type: problem
domain: build
status: solved
audience: public
created: 2026-09-19
updated: 2026-09-19
severity: critical
tags: [build, ohos-sdk, api-version, arkui, linux]
refs: [skills/qt-sdk-forge/references/build-matrix.md, knowledge/errors/QOH041.yaml]
error_message: "qtbase/src/plugins/platforms/ohos/qarkui/input.cpp:193:39: error: no member named 'OH_ArkUI_PointerEvent_GetGlobalDisplayX' in the global namespace"
error_code: N/A
summary: >
  The OHOS QPA plugin (qarkui) of the Qt HarmonyOS port takes the addresses of ArkUI NDK functions at compile time, which requires a fairly new
  API (tested: OpenHarmony SDK >= 6.1 / API 23; the official build uses API 24 v6.1.1.125).
  Older SDKs such as API 15 (OpenHarmony 5.0.3) lack these symbols. There's no prebuilt host package for Linux, so you must get the SDK from
  the public OpenHarmony mirror.
---

# The OHOS SDK API version is too old, so the QPA plugin lacks ArkUI NDK symbols

## Symptoms

When qtbase reaches the OHOS platform plugin (qarkui), the build reports "symbol doesn't exist":

```
qtbase/src/plugins/platforms/ohos/qarkui/input.cpp:193:39: error: no member named
'OH_ArkUI_PointerEvent_GetGlobalDisplayX' in the global namespace; did you mean
'OH_ArkUI_PointerEvent_GetDisplayX'?

qtbase/src/plugins/platforms/ohos/qarkui/input.cpp:219:52: error: no member named
'OH_ArkUI_HoverEvent_IsHovered' in the global namespace
```

## Cause

The OHOS QPA plugin takes function addresses via `Q_OHOS_NAMED_FUNC(::OH_ArkUI_...)` to build runtime dynamic-resolution
wrappers, so **the symbols must already be declared in the sysroot headers at compile time**; there's no fallback branch for older versions.
Known minimum requirements (tested against the sysroot's `arkui/ui_input_event.h`):

| SDK | apiVersion | Result |
|-----|-----------|--------|
| OpenHarmony 5.0.3.135 | 15 | ❌ missing `GetGlobalDisplayX/Y`, `IsHovered`, and others |
| **OpenHarmony 6.1.0.35 (6.1-LTS)** | **23** | ✅ all present; clang 15.0.4, same as the official one |
| HarmonyOS SDK 6.1.1.125 (used by the official build) | 24 | ✅ (requires a Huawei account; not available through public channels) |

Note: the compiler version is actually not the problem: the native toolchains of both 5.0.3 and 6.1 are OHOS clang 15.0.4.

## Solution

Getting a compliant SDK on Linux (a public channel, no login required):

```bash
# Official public OpenHarmony mirror (Huawei Cloud); the path pattern is:
# https://repo.huaweicloud.com/openharmony/os/<version>/ohos-sdk-windows_linux-public.tar.gz
curl -L -o ohos-sdk.tar.gz \
  "https://repo.huaweicloud.com/openharmony/os/6.1-LTS/ohos-sdk-windows_linux-public.tar.gz"

# Extract only the Linux native toolchain (the tar contains zips split by platform/component)
tar xzf ohos-sdk.tar.gz ohos-sdk/linux/native-linux-x64-*.zip
unzip native-linux-x64-*.zip -d native && mv native/native native-sdk

# Register it with forge (the env check needs llvm/bin + sysroot)
python3 tools/qt-sdk-run.py config set ohos_sdk_native <absolute-path>/native-sdk
```

**After switching SDKs you must clean the build directory** (see
[build-fail-stale-build-state](build-fail-stale-build-state.md); the newer CLI handles this automatically).

## Verification

```bash
cat <native-sdk>/oh-uni-package.json       # apiVersion >= 23
grep -l "OH_ArkUI_PointerEvent_GetGlobalDisplayX" \
  <native-sdk>/sysroot/usr/include/arkui/ui_input_event.h
```
