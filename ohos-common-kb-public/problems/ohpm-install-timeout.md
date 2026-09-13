---
id: ohpm-install-timeout
title: ohpm install times out or the registry is unreachable
status: active
confidence: 0.9
sources:
  - type: experience
    name: "ohpm install timeout during a Tauri application migration"
    date: 2026-07-15
created: 2026-08-15
updated: 2026-08-15
last_confirmed: 2026-07-30
superseded_by: null
tags: [ohos, ohpm, registry, timeout, network, problem]
refs: [deveco-cli-usage-rules]
summary: "An ohpm install that hangs or times out is usually a registry, proxy, or network reachability problem; diagnose the current configuration first, then switch to a registry that is organization-approved and reachable."
audience: public
error_message: |
  ohpm install times out
  ohpm install hangs for a long time
---

# ohpm install times out or the registry is unreachable

## Symptoms

Running `ohpm install` hangs for a long time, fails to connect, or times out. This is a problem with the OHPM registry and the network path — it is not determined by the higher-level Qt, Tauri, AWT/Swing, or Avalonia framework.

## Diagnosis

1. Record `ohpm --version` and the current registry configuration to confirm which client and source are actually in use.
2. Check DNS, TLS, and proxy reachability for the target registry, distinguishing an unreachable source, a misconfigured proxy, and transient network flakiness.
3. Retry a minimal `ohpm install` in the same terminal — don't paper over the network root cause by deleting lock files or repeatedly clearing caches.
4. If you build through `devecocli`, use its verbose logs to confirm the failure really occurs during the OHPM install phase.

## What to do

Prefer a registry that is organization-approved and reachable from your current network. If the Huawei Cloud mirror is approved for your use, you can run:

```bash
ohpm config set registry https://repo.huaweicloud.com/repository/ohpm/
```

After switching, re-read the registry configuration and run the install to verify. If your organization mandates the official source or an internal proxy, follow that policy instead; don't hard-code a mirror address into a framework template or application source.

## Framework adapter boundary

The framework repository only needs to record where in the generated project `ohpm install` is triggered, how to collect logs, and the framework build regression evidence after a fix. Registry, proxy, and network diagnosis is maintained here.

## Related

- [[../procedural/deveco-cli-usage-rules|deveco-cli usage rules]] — OHPM's role in the DevEco toolchain and the boundary of low-level diagnosis
