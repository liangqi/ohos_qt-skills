---
id: procfs-system-information-unavailable
title: "System information empty or zero: Linux procfs data sources are restricted"
status: active
confidence: 0.7
sources: [{type: experience, name: "System monitor app, on-device verification", date: 2026-08-03}]
created: 2026-08-14
updated: 2026-08-14
last_confirmed: 2026-08-03
superseded_by: null
tags: [problem, procfs, system-info, cpu, disk, sandbox]
refs: [system-information-access-limits]
summary: "After a library selects the Linux backend, reads of /proc/stat, mounts, or diskstats are denied, so CPU/disk metrics come back empty or zero."
audience: public
error_message: |
  /proc/stat: Permission denied
  /proc/mounts: Permission denied
  CPU usage: 0
  disk list: empty
---

# System information empty or zero: Linux procfs data sources are restricted

## Diagnosis

1. Identify the data source behind each specific metric.
2. Check the access result under the application process's own permissions — don't substitute an hdc/root view.
3. Distinguish open/read permission errors, parser errors, empty lists, and genuine zero values.
4. Verify whether the library picked the Linux desktop backend because of an incorrect target cfg.

## Solution

For restricted metrics, use the platform's public APIs or a dedicated OHOS backend. If the platform doesn't expose the capability to ordinary applications, degrade explicitly to "unavailable" — hide/disable the feature or explain the permission restriction. Don't fabricate a zero.

## Prevention

For system-monitor-style applications, build a "metric → data source → permission → device/API → fallback" matrix during the technology-selection phase, and run regression tests on real devices.
