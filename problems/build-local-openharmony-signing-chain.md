---
id: problem-build-local-openharmony-signing-chain
type: problem
domain: build
tags: [signing, HAP, OpenHarmony, local-root-certificate, hap-sign-tool, debug-certificate, expiry, install-failure]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: medium
audience: public
summary: "The complete chain for self-signing a HAP with the OpenHarmony local root certificate when you have no Huawei developer certificate"
# ====== Search keywords (for fast agent matching) ======
error_message: >
  error: signature verification failed
  error: install failed due to grant request permissions failed
  hap-sign-tool: error: the certificate has expired
error_code: ""
keywords: [signing, HAP, hap-sign-tool, local root certificate, OpenHarmony, profile, p7b, debug certificate, install failure]
symptoms: "Installing the HAP reports a signature verification failure; or every install fails after the debug certificate expires"
# ====== Problem details ======
environment: "OpenHarmony local SDK with a real device/emulator; no dependency on a Huawei developer account"
refs: [problem-build-app-layer-out-of-tree-prerequisites, procedural-qt-harmonyos-build-run-workflow]
related_problems: []
---

# Self-signing a HAP with the OpenHarmony local root certificate

## When you need it

You have no Huawei developer account/AGC certificate, but need to install a HAP on a real device or emulator. The local root certificates
OpenHarmony provides (`OpenHarmony.p12`, `OpenHarmonyApplication.pem`, `UnsgnedReleasedProfileTemplate.json`,
and so on) can self-sign a HAP that **debug devices** accept.

## The chain (five steps; skip any one and the error only shows up at install time)

```
① generate a key pair → ② generate a CSR → ③ issue the application certificate (.cer) with the local root certificate
→ ④ generate the profile (.p7b, binding the bundleName + device UDID/debug type)
→ ⑤ hap-sign-tool signs the HAP with the certificate + profile
```

Key points:

- **The bundleName must match in three places**: `app.json5` / the profile / the signing command;
- **Device identity**: a debug profile has to be bound to a device (a real device's UDID or an emulator type); switching devices means re-signing;
- **Certificate validity**: self-signed certificates usually last only a few months; expiry shows up as "it installed yesterday, everything fails today".
  This is the **only** place to check; don't go digging through the build first;
- **Output layout**: keep signed and unsigned HAPs in separate directories, so you don't grab the wrong one.

## How to verify

1. `hap-sign-tool verify-app -in <signed.hap> -out <out> -public-profile <p7b>` passes;
2. `hdc install <signed.hap>` returns success and `bm dump -n <bundle>` shows the entry;
3. Uninstall and reinstall once (to rule out a false success where "an overwrite install keeps the old signature").

## Differences from official signing

| Item | Local self-signing | Official (AGC) |
|------|--------------------|----------------|
| Devices | Debug devices/emulators | Any production device |
| Distribution | Can't be published to the store | Can be published |
| Permissions | Restricted (restricted permissions need profile authorization) | Granted as applied for |
| Expiry | Short certificate validity; re-sign periodically | Per the certificate's validity |

This page covers only the minimal closed loop of "getting it running on your own device"; store publishing and official distribution still need the official chain.
