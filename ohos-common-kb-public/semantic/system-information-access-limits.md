---
id: system-information-access-limits
title: Access boundaries for application access to system information
status: active
confidence: 0.7
sources:
  - type: experience
    name: "System monitor app, OHOS on-device verification"
    date: 2026-08-03
  - type: code
    name: "sysinfo 0.35.2 Linux backend"
    date: 2026-08-03
created: 2026-08-14
updated: 2026-08-14
last_confirmed: 2026-08-03
review_by: null
superseded_by: null
tags: [system-info, procfs, sandbox, cpu, disk, process]
refs: [procfs-system-information-unavailable, application-sandbox-paths]
summary: "An ordinary application cannot assume all of Linux procfs is readable; use platform APIs per metric, and distinguish unsupported, permission-denied, and genuine zero values."
audience: public
---

# Access boundaries for application access to system information

An OHOS target or compatibility layer may cause a third-party library to select the Linux backend, but that does not mean an ordinary application has desktop Linux's level of access to procfs, the mount table, and device statistics.

## Verified boundaries

In verification on a specific device with an ordinary application, `/proc/meminfo` and some `/proc/<pid>` data were readable, while `/proc/stat`, `/proc/mounts`, and `/proc/diskstats` were restricted — leaving CPU and disk/storage metrics empty or zero. This result depends on the device, system version, application type, and permissions, and should not be generalized into a permanent static table covering every product.

## Design rules

- Record the real data source for each metric; "the library supports Linux" is not proof of platform support.
- Prefer the system abilities/APIs that the target system exposes publicly.
- Model unavailable / permission-denied / not-implemented separately from a numeric 0.
- Verify processes, CPU, memory, disk, and network individually — don't infer that everything works because one dimension did.
- Capabilities available to system/basic/privileged applications do not automatically apply to ordinary third-party applications.

## Adapter boundary

How Rust sysinfo, the Qt system APIs, JVM MXBeans, or .NET diagnostics fall back and present results stays in the framework repository. This common knowledge base maintains the platform seam: data sources and permissions must be verified metric by metric.
