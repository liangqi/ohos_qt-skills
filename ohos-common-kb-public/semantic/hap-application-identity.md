---
id: hap-application-identity
title: HAP application identity and bundleName constraints
status: active
confidence: 0.7
sources: [{type: experience, name: "Troubleshooting Qt/Tauri HAP configuration and signing", date: 2026-08-06}]
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-06
review_by: null
superseded_by: null
tags: [hap, bundle-name, identity, signing, appscope]
refs: [hap-native-project-structure]
summary: "The role bundleName plays in platform identity, its syntax/uniqueness checks, and how it relates to profiles, installation, and framework-generated configuration."
audience: public
---

# HAP application identity and bundleName constraints

`bundleName` is part of the application's identity and participates in installation, launch, signing profiles, and data isolation. It is not a display name you can swap out at the end of a build.

## Constraints

- Use the characters and dotted-segment form that the target SDK schema accepts. In practice, migrations should use a stable reverse-domain-style value of at least three segments made up of letters, digits, underscores, and dots.
- Keep it unique within your organization/device environment so the template's default identity doesn't collide with another application.
- `AppScope/app.json5`, the framework configuration, the generated project, the launch command, and the signing profile must all point at the same identity.
- A framework may convert hyphens to underscores or derive the bundleName from the package id. That is adapter behavior, not platform syntax.

## Troubleshooting

When you hit a configuration-validation, signing, installation, or launch failure, start by collecting the final *generated* `AppScope/app.json5` — don't just read the framework's source configuration. Compare:

1. The final bundleName
2. The product/signingConfig
3. The application identity bound to the profile
4. The bundle used by the install/launch command
5. Whether a conflicting application is already present on the device

The exact character ranges and lengths may change as the SDK schema evolves; when implementing, defer to the target SDK's validation results and the official documentation.
