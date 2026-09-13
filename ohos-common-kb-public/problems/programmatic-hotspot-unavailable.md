---
id: programmatic-hotspot-unavailable
title: "Ordinary applications cannot create a Wi-Fi hotspot programmatically"
status: active
confidence: 0.7
sources:
  - type: official
    name: "Constraints on the wifiManagerExt enableHotspot API"
    date: 2026-08-08
  - type: experience
    name: "Hotspot mode, on-device verification"
    date: 2026-08-08
created: 2026-08-14
updated: 2026-08-14
last_confirmed: 2026-08-08
superseded_by: null
tags: [problem, wifi, hotspot, privileged-api]
refs: [privileged-system-capabilities]
summary: "enableHotspot is deprecated and restricted to non-general-purpose products, so an ordinary application's automatic hotspot feature must degrade or switch to a supported network mode."
audience: public
error_message: |
  enableHotspot unavailable
  No WiFi interfaces found
  hotspot mode unsupported
---

# Ordinary applications cannot create a Wi-Fi hotspot programmatically

## Cause

The status of the public extension API and its product restrictions do not allow ordinary general-purpose device applications to create a hotspot automatically through it. Merely adding permissions, stubbing the interface, or treating OHOS as a Linux Wi-Fi backend will not grant you the system capability.

## What to do

- Mark programmatic hotspot as unavailable to ordinary applications for now.
- Evaluate alternatives: having the user enable it manually, using an existing LAN, the platform's public P2P/nearby capabilities, or removing the mode entirely.
- Make the functional difference explicit in the UI — don't silently return an empty network-interface list.
- If your product is an approved non-general-purpose device, have the corresponding product/system owner re-review it against their SDK and signing policy.

## Prevention

Before migrating, audit every network-management, VPN, hotspot, and system-settings capability for privileged API use, rather than waiting until the build succeeds to do functional testing.
