---
id: hap-device-sdk-version-mismatch
title: "HAP installation fails: device API is lower than compatibleSdkVersion"
status: active
confidence: 0.9
sources: [{type: experience, name: "AWT/Swing test app, on-device verification", date: 2026-07-30}]
created: 2026-08-13
updated: 2026-08-13
last_confirmed: 2026-07-30
superseded_by: null
tags: [problem, install, hap, sdk, api-version]
refs: [hap-native-project-structure]
summary: "When the device API is lower than the HAP's compatibleSdkVersion, installation returns 9568297/older sdk version; pick a compatible version based on the real minimum capability required."
audience: public
error_message: |
  error: failed to install bundle. code:9568297
  error: install failed due to older sdk version in the device.
---

# HAP installation fails: device API is lower than compatibleSdkVersion

## Error message

```text
error: failed to install bundle. code:9568297
error: install failed due to older sdk version in the device.
```

## Scenario and cause

The build product's `compatibleSdkVersion` is higher than the target device's API. The installer refuses to install a HAP that demands a higher minimum API onto an older device.

## Solution

1. Query the target device's API level.
2. Determine the true minimum API required by the application and all of its native/ArkTS capabilities.
3. Set the product's compatible SDK to a value no higher than the device's and no lower than what the application actually needs.
4. Do a clean rebuild, re-sign, and install.

Don't mechanically copy a low version number from some other case. If the application genuinely depends on a higher API, upgrade the device or accept the installation refusal — don't lower the declared version and take on runtime crashes instead.

## Prevention

Record the device system/API, compile SDK, target SDK, and compatible SDK in your test matrix, and have your tooling print these values before installation.
