---
id: privileged-system-capabilities
title: Privileged system capabilities and the ordinary-application boundary
status: active
confidence: 0.7
sources:
  - type: official
    name: "Constraints on the wifiManagerExt enableHotspot API"
    date: 2026-08-08
  - type: experience
    name: "Hotspot mode, on-device evaluation"
    date: 2026-08-08
created: 2026-08-14
updated: 2026-08-14
last_confirmed: 2026-08-08
review_by: null
superseded_by: null
tags: [privileged-api, permission, system-app, wifi, hotspot]
refs: [programmatic-hotspot-unavailable]
summary: "API visibility, manifest permissions, profile ACLs, application type, and product type together determine privileged capabilities; ordinary applications must design a degraded path."
audience: public
---

# Privileged system capabilities and the ordinary-application boundary

Seeing an API or permission name in the SDK does not mean an ordinary third-party application can call it. Determining whether a capability is available involves at least: API status, system capability, permission level, signing/profile ACL, application type, product type, and device policy.

## Order of evaluation

1. Does the API exist at the target SDK/API level, and is it deprecated?
2. Do the docs restrict it to system/basic applications, specific products, or non-general-purpose devices?
3. Can the current application type request the manifest permission?
4. Does the profile/certificate actually grant it?
5. Does a real device provide the corresponding system capability?
6. When it is denied, is there a user settings page, a system chooser, or another supported alternative flow?

Don't try to work around platform boundaries via hidden APIs, copied system signatures, or broadened certificate permissions. A core capability that cannot be opened to ordinary applications should be marked blocked/degraded during migration assessment, not left to fail silently at runtime.

## Wi-Fi hotspot case study

The audited `wifiManagerExt.enableHotspot` is deprecated and targeted at non-general-purpose product types; ordinary phone/tablet/2-in-1 applications cannot promise programmatic hotspot creation on that basis. An application can evaluate manual user setup, an existing network, the platform's public nearby/P2P capabilities, or dropping the mode — but whether the alternative is equivalent must be re-verified.

## Adapter boundary

The framework repository keeps the specific feature flags, errors, and user-experience fallbacks; this common knowledge base maintains the method for evaluating permission/product/application type and the confirmed platform boundaries.
